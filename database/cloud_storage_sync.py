#!/usr/bin/env python3
"""
Google Cloud Storage Sync Module for Hydrawise Database

Handles automatic backup and sync of SQLite database to Google Cloud Storage
with versioning, compression, and smart upload strategies.

Features:
- Automatic daily database backups to GCS
- Versioned storage with date-stamped files
- Compression to reduce storage costs
- Smart sync (only upload if database changed significantly)
- Download capabilities for multi-location access
- Disaster recovery support

Author: AI Assistant
Date: 2025
"""

import os
import sys
import gzip
import hashlib
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import shutil

try:
    from google.cloud import storage
    from google.oauth2 import service_account
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    logging.warning("Google Cloud Storage libraries not available. Install with: pip install google-cloud-storage")

logger = logging.getLogger(__name__)

class CloudStorageSync:
    """Manages SQLite database synchronization with Google Cloud Storage"""
    
    def __init__(self, bucket_name: str, credentials_path: str = None, local_db_path: str = "database/irrigation_data.db"):
        """
        Initialize cloud storage sync
        
        Args:
            bucket_name: Google Cloud Storage bucket name
            credentials_path: Path to GCS service account JSON file
            local_db_path: Path to local SQLite database file
        """
        if not GCS_AVAILABLE:
            raise ImportError("Google Cloud Storage libraries not installed. Run: pip install google-cloud-storage")
            
        self.bucket_name = bucket_name
        self.local_db_path = local_db_path
        self.credentials_path = credentials_path
        
        # Initialize GCS client
        self._init_gcs_client()
        
        # Metadata tracking
        self.sync_metadata_file = "database/sync_metadata.json"
        self.metadata = self._load_sync_metadata()
        
    def _init_gcs_client(self):
        """Initialize Google Cloud Storage client with credentials"""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                # Use service account credentials
                credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
                self.client = storage.Client(credentials=credentials)
                logger.info(f"Initialized GCS client with service account: {self.credentials_path}")
            else:
                # Use default credentials (Application Default Credentials)
                self.client = storage.Client()
                logger.info("Initialized GCS client with default credentials")
                
            # Verify bucket exists
            self.bucket = self.client.bucket(self.bucket_name)
            if not self.bucket.exists():
                logger.error(f"Bucket '{self.bucket_name}' does not exist")
                raise ValueError(f"Bucket '{self.bucket_name}' not found")
                
            logger.info(f"Connected to GCS bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise
            
    def _load_sync_metadata(self) -> Dict[str, Any]:
        """Load sync metadata from local file"""
        if os.path.exists(self.sync_metadata_file):
            try:
                with open(self.sync_metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load sync metadata: {e}")
                
        # Default metadata
        return {
            'last_sync': None,
            'last_hash': None,
            'last_size': 0,
            'sync_count': 0,
            'last_error': None
        }
        
    def _save_sync_metadata(self):
        """Save sync metadata to local file"""
        try:
            os.makedirs(os.path.dirname(self.sync_metadata_file), exist_ok=True)
            with open(self.sync_metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save sync metadata: {e}")
            
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file for change detection"""
        if not os.path.exists(file_path):
            return ""
            
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
        
    def _should_sync(self) -> bool:
        """Determine if database should be synced based on changes"""
        if not os.path.exists(self.local_db_path):
            logger.warning(f"Local database not found: {self.local_db_path}")
            return False
            
        current_hash = self._get_file_hash(self.local_db_path)
        current_size = os.path.getsize(self.local_db_path)
        
        # Always sync if never synced before
        if not self.metadata.get('last_sync'):
            logger.info("First sync - uploading database")
            return True
            
        # Sync if hash changed (content changed)
        if current_hash != self.metadata.get('last_hash'):
            logger.info("Database content changed - sync required")
            return True
            
        # Sync if significant size change (>1MB difference)
        size_diff = abs(current_size - self.metadata.get('last_size', 0))
        if size_diff > 1024 * 1024:  # 1MB
            logger.info(f"Significant size change ({size_diff} bytes) - sync required")
            return True
            
        # Sync if last sync was more than 24 hours ago
        last_sync = self.metadata.get('last_sync')
        if last_sync:
            last_sync_date = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            if (datetime.now() - last_sync_date).total_seconds() > 24 * 3600:
                logger.info("Daily sync required (>24 hours since last sync)")
                return True
                
        logger.info("No sync required - database unchanged")
        return False
        
    def compress_database(self, source_path: str, compressed_path: str) -> int:
        """Compress database file with gzip for cloud storage"""
        try:
            with open(source_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    
            compressed_size = os.path.getsize(compressed_path)
            original_size = os.path.getsize(source_path)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            logger.info(f"Compressed database: {original_size:,} -> {compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
            return compressed_size
            
        except Exception as e:
            logger.error(f"Failed to compress database: {e}")
            raise
            
    def upload_database(self, force: bool = False) -> Dict[str, Any]:
        """
        Upload database to Google Cloud Storage
        
        Args:
            force: Force upload even if no changes detected
            
        Returns:
            Dict with upload results
        """
        if not force and not self._should_sync():
            return {
                'uploaded': False,
                'reason': 'No changes detected',
                'last_sync': self.metadata.get('last_sync')
            }
            
        logger.info("Starting database upload to Google Cloud Storage...")
        start_time = datetime.now()
        
        try:
            # Generate filenames
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            date_str = datetime.now().strftime('%Y%m%d')
            
            # Compressed file paths  
            import tempfile
            temp_compressed = os.path.join(tempfile.gettempdir(), f"irrigation_data_{timestamp}.db.gz")
            
            # Cloud storage paths
            latest_path = "latest/irrigation_data.db.gz"
            versioned_path = f"backups/{date_str}/irrigation_data_{timestamp}.db.gz"
            
            # Compress database
            compressed_size = self.compress_database(self.local_db_path, temp_compressed)
            
            # Upload latest version (always overwrites)
            latest_blob = self.bucket.blob(latest_path)
            latest_blob.upload_from_filename(temp_compressed)
            logger.info(f"Uploaded latest version: gs://{self.bucket_name}/{latest_path}")
            
            # Upload versioned backup
            versioned_blob = self.bucket.blob(versioned_path)
            versioned_blob.upload_from_filename(temp_compressed)
            logger.info(f"Uploaded versioned backup: gs://{self.bucket_name}/{versioned_path}")
            
            # Set metadata on blobs
            metadata = {
                'sync_timestamp': datetime.now().isoformat(),
                'original_size': str(os.path.getsize(self.local_db_path)),
                'compressed_size': str(compressed_size),
                'db_hash': self._get_file_hash(self.local_db_path)
            }
            
            latest_blob.metadata = metadata
            latest_blob.patch()
            
            versioned_blob.metadata = metadata
            versioned_blob.patch()
            
            # Update local metadata
            self.metadata.update({
                'last_sync': datetime.now().isoformat(),
                'last_hash': self._get_file_hash(self.local_db_path),
                'last_size': os.path.getsize(self.local_db_path),
                'sync_count': self.metadata.get('sync_count', 0) + 1,
                'last_error': None
            })
            self._save_sync_metadata()
            
            # Cleanup temp file
            if os.path.exists(temp_compressed):
                os.remove(temp_compressed)
                
            duration = (datetime.now() - start_time).total_seconds()
            
            result = {
                'uploaded': True,
                'duration_seconds': duration,
                'compressed_size': compressed_size,
                'latest_path': latest_path,
                'versioned_path': versioned_path,
                'metadata': metadata
            }
            
            logger.info(f"Database upload completed successfully in {duration:.1f} seconds")
            return result
            
        except Exception as e:
            error_msg = f"Failed to upload database: {e}"
            logger.error(error_msg)
            
            self.metadata['last_error'] = error_msg
            self._save_sync_metadata()
            
            # Cleanup temp file on error
            if 'temp_compressed' in locals() and os.path.exists(temp_compressed):
                os.remove(temp_compressed)
                
            raise
            
    def download_database(self, target_path: str = None, version: str = "latest") -> str:
        """
        Download database from Google Cloud Storage
        
        Args:
            target_path: Local path to save database (defaults to configured path)
            version: "latest" or specific backup path like "backups/20250822/..."
            
        Returns:
            Path to downloaded database file
        """
        if target_path is None:
            target_path = self.local_db_path
            
        logger.info(f"Downloading database from GCS (version: {version})...")
        
        try:
            # Determine source path
            if version == "latest":
                source_path = "latest/irrigation_data.db.gz"
            else:
                source_path = version
                
            # Download compressed file
            blob = self.bucket.blob(source_path)
            if not blob.exists():
                raise FileNotFoundError(f"Database backup not found: gs://{self.bucket_name}/{source_path}")
                
            import tempfile
            temp_compressed = os.path.join(tempfile.gettempdir(), "downloaded_irrigation_data.db.gz")
            blob.download_to_filename(temp_compressed)
            
            # Decompress to target location
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with gzip.open(temp_compressed, 'rb') as f_in:
                with open(target_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    
            # Get file info
            downloaded_size = os.path.getsize(target_path)
            
            # Cleanup temp file
            if os.path.exists(temp_compressed):
                os.remove(temp_compressed)
                
            logger.info(f"Database downloaded successfully: {downloaded_size:,} bytes -> {target_path}")
            return target_path
            
        except Exception as e:
            logger.error(f"Failed to download database: {e}")
            
            # Cleanup temp file on error
            if 'temp_compressed' in locals() and os.path.exists(temp_compressed):
                os.remove(temp_compressed)
                
            raise
            
    def list_backups(self, days: int = 30) -> List[Dict[str, Any]]:
        """List available database backups from the last N days"""
        try:
            blobs = self.client.list_blobs(self.bucket, prefix="backups/")
            
            backups = []
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for blob in blobs:
                if blob.name.endswith('.db.gz'):
                    # Extract date from path like "backups/20250822/irrigation_data_20250822_143022.db.gz"
                    parts = blob.name.split('/')
                    if len(parts) >= 3:
                        try:
                            date_str = parts[1]  # "20250822"
                            backup_date = datetime.strptime(date_str, '%Y%m%d')
                            
                            if backup_date >= cutoff_date:
                                backup_info = {
                                    'path': blob.name,
                                    'date': backup_date.date(),
                                    'size': blob.size,
                                    'created': blob.time_created,
                                    'metadata': blob.metadata or {}
                                }
                                backups.append(backup_info)
                                
                        except ValueError:
                            continue  # Skip malformed dates
                            
            # Sort by date (newest first)
            backups.sort(key=lambda x: x['date'], reverse=True)
            
            logger.info(f"Found {len(backups)} backups from last {days} days")
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
            
    def cleanup_old_backups(self, keep_days: int = 90) -> int:
        """Delete old database backups to manage storage costs"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            deleted_count = 0
            
            blobs = self.client.list_blobs(self.bucket, prefix="backups/")
            
            for blob in blobs:
                if blob.name.endswith('.db.gz'):
                    # Check if blob is older than cutoff
                    if blob.time_created and blob.time_created.replace(tzinfo=None) < cutoff_date:
                        logger.info(f"Deleting old backup: {blob.name}")
                        blob.delete()
                        deleted_count += 1
                        
            logger.info(f"Cleaned up {deleted_count} old backups (older than {keep_days} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
            return 0
            
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status"""
        return {
            'last_sync': self.metadata.get('last_sync'),
            'sync_count': self.metadata.get('sync_count', 0),
            'last_error': self.metadata.get('last_error'),
            'database_exists': os.path.exists(self.local_db_path),
            'database_size': os.path.getsize(self.local_db_path) if os.path.exists(self.local_db_path) else 0,
            'should_sync': self._should_sync() if os.path.exists(self.local_db_path) else False,
            'bucket_name': self.bucket_name
        }

def main():
    """Test cloud storage sync functionality"""
    print("Google Cloud Storage Sync Test")
    print("=" * 50)
    
    # Load configuration from environment
    bucket_name = os.getenv('GCS_BUCKET_NAME', 'hydrawise-irrigation-data')
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not credentials_path:
        print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set")
        print("Using default credentials (gcloud auth application-default login)")
        
    try:
        # Initialize sync
        sync = CloudStorageSync(bucket_name, credentials_path)
        
        # Get status
        status = sync.get_sync_status()
        print(f"Sync Status: {status}")
        
        # List recent backups
        backups = sync.list_backups(7)
        print(f"Recent backups: {len(backups)}")
        for backup in backups[:3]:
            print(f"  {backup['date']}: {backup['size']:,} bytes")
            
        # Test upload (if database exists)
        if status['database_exists']:
            print("Testing upload...")
            result = sync.upload_database()
            print(f"Upload result: {result}")
        else:
            print("No local database found - skipping upload test")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
