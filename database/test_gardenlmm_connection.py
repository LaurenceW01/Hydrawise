#!/usr/bin/env python3
"""
Test connection to GardenLMM hydrawise-database bucket

This script verifies that you can connect to your existing Google Cloud Storage
bucket and tests the basic sync functionality.

Run this after setting up your authentication to verify everything works.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.cloud_storage_sync import CloudStorageSync

def test_gardenlmm_connection():
    """Test connection to GardenLMM hydrawise-database bucket"""
    
    print("[SYMBOL] Testing GardenLMM Google Cloud Storage Connection")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Use your specific bucket configuration
    bucket_name = "hydrawise-database"
    project_id = "gardenllm"
    
    print(f"[SYMBOL] Bucket: {bucket_name}")
    print(f"[SYMBOL][SYMBOL]  Project: {project_id}")
    print(f"[SYMBOL] Auth: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'Application Default Credentials')}")
    print()
    
    try:
        # Initialize cloud sync with your bucket
        print("[PERIODIC] Initializing CloudStorageSync...")
        sync = CloudStorageSync(
            bucket_name=bucket_name,
            credentials_path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        )
        print("[OK] CloudStorageSync initialized successfully")
        
        # Test bucket access
        print("\n[TEST] Testing bucket access...")
        status = sync.get_sync_status()
        print(f"[OK] Bucket '{bucket_name}' is accessible")
        print(f"   Sync status: {status}")
        
        # List existing backups
        print("\n[LOG] Listing existing backups...")
        backups = sync.list_backups(days=30)
        if backups:
            print(f"[OK] Found {len(backups)} existing backups:")
            for backup in backups[:5]:  # Show first 5
                print(f"   [SYMBOL] {backup['date']}: {backup['size']:,} bytes")
                print(f"      Path: {backup['path']}")
        else:
            print("[SYMBOL] No existing backups found (this is normal for first setup)")
            
        # Test upload capability (create a small test file)
        print("\n[TEST] Testing upload capability...")
        import tempfile
        test_file = os.path.join(tempfile.gettempdir(), "hydrawise_test.txt")
        test_content = f"Hydrawise test file created at {datetime.now()}\nGardenLMM Project Integration Test"
        
        with open(test_file, 'w') as f:
            f.write(test_content)
            
        # Upload test file
        test_blob_name = f"test/connection_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        blob = sync.bucket.blob(test_blob_name)
        blob.upload_from_filename(test_file)
        
        print(f"[OK] Test upload successful: gs://{bucket_name}/{test_blob_name}")
        
        # Clean up test file
        blob.delete()
        os.remove(test_file)
        print("[SYMBOL] Test file cleaned up")
        
        # Show folder structure that will be created
        print(f"\n[SYMBOL] Folder structure in gs://{bucket_name}/:")
        print("   latest/")
        print("   [SYMBOL][SYMBOL][SYMBOL] irrigation_data.db.gz (always current version)")
        print("   backups/")
        print("   [SYMBOL][SYMBOL][SYMBOL] 20250822/")
        print("   [SYMBOL]   [SYMBOL][SYMBOL][SYMBOL] irrigation_data_20250822_143022.db.gz")
        print("   [SYMBOL][SYMBOL][SYMBOL] 20250823/")
        print("       [SYMBOL][SYMBOL][SYMBOL] irrigation_data_20250823_091505.db.gz")
        
        print(f"\n[SUCCESS] SUCCESS: Ready to use GardenLMM bucket '{bucket_name}'!")
        print("\n[LOG] Next steps:")
        print("   1. Add these settings to your .env file:")
        print(f"      GCS_BUCKET_NAME={bucket_name}")
        print(f"      GOOGLE_CLOUD_PROJECT={project_id}")
        print("   2. Run your irrigation data collection")
        print("   3. Database will automatically sync to your bucket")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Connection test failed: {e}")
        print("\n[SYMBOL] Troubleshooting:")
        print("   1. Verify Google Cloud SDK is installed")
        print("   2. Run: gcloud auth application-default login")
        print("   3. Select your GardenLMM account")
        print("   4. Verify bucket 'hydrawise-database' exists in project 'gardenlmm'")
        print("   5. Check IAM permissions for Storage Object Admin role")
        
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    try:
        success = test_gardenlmm_connection()
        
        if success:
            print("\n[COMPLETE] All tests passed! Your GardenLMM integration is ready.")
        else:
            print("\n[SYMBOL] Tests failed. Please check the troubleshooting steps above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n[SYMBOL] Test interrupted by user")
    except Exception as e:
        print(f"\n[SYMBOL] Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
