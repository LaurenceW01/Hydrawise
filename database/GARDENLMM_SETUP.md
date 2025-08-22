# GardenLMM Google Cloud Storage Setup

This guide configures the Hydrawise irrigation monitoring system to store data in your existing GardenLMM Google Cloud project's `hydrawise-database` bucket.

## 🎯 Quick Setup

### 1. Add to your `.env` file:

```bash
# Google Cloud Storage Configuration for GardenLMM Project
GCS_BUCKET_NAME=hydrawise-database
GOOGLE_CLOUD_PROJECT=gardenllm
DB_SYNC_ENABLED=true
DB_SYNC_DAILY=true
DB_BACKUP_RETENTION_DAYS=90
```

### 2. Authenticate with Google Cloud:

**Option A: Application Default Credentials (Recommended)**
```bash
# Install Google Cloud SDK if not already installed
# Download from: https://cloud.google.com/sdk/docs/install

# Authenticate with your GardenLMM account
gcloud auth application-default login

# Set default project
gcloud config set project gardenlmm
```

**Option B: Service Account Key**
```bash
# Download service account key from Google Cloud Console
# IAM & Admin > Service Accounts > Create/Download key
# Add to .env file:
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gardenlmm-service-account-key.json
```

### 3. Test the connection:

```bash
python database/test_gardenlmm_connection.py
```

## 📁 Storage Structure

Your `hydrawise-database` bucket will contain:

```
gs://hydrawise-database/
├── latest/
│   └── irrigation_data.db.gz           # Always current version
└── backups/
    ├── 20250822/
    │   └── irrigation_data_20250822_143022.db.gz
    ├── 20250823/
    │   └── irrigation_data_20250823_091505.db.gz
    └── ...
```

## 🔧 Usage

### Automatic Sync
Once configured, the database will automatically sync to your GardenLMM bucket when:
- Database content changes significantly
- 24 hours have passed since last sync
- Manual upload is triggered

### Manual Operations

**Upload current database:**
```python
from database.cloud_storage_sync import CloudStorageSync

sync = CloudStorageSync('hydrawise-database')
result = sync.upload_database(force=True)
print(f"Upload result: {result}")
```

**Download latest database:**
```python
sync.download_database(target_path='database/irrigation_data.db')
```

**List recent backups:**
```python
backups = sync.list_backups(days=30)
for backup in backups:
    print(f"{backup['date']}: {backup['size']:,} bytes")
```

## 💰 Cost Management

- **Compression**: Databases are gzipped (typically 80%+ reduction)
- **Smart Sync**: Only uploads when content actually changes
- **Automatic Cleanup**: Old backups deleted after 90 days (configurable)
- **Regional Storage**: Use same region as your compute for lower costs

## 🔐 Security & Permissions

Required IAM permissions for your account/service account:
- `storage.objects.create`
- `storage.objects.delete`
- `storage.objects.get`
- `storage.objects.list`

Or use the predefined role: **Storage Object Admin**

## 🚨 Disaster Recovery

**Restore from backup:**
```python
# List available backups
sync = CloudStorageSync('hydrawise-database')
backups = sync.list_backups(days=90)

# Download specific backup
backup_path = 'backups/20250822/irrigation_data_20250822_143022.db.gz'
sync.download_database(
    target_path='database/irrigation_data_restored.db',
    version=backup_path
)
```

## 📊 Integration with Data Collection

The cloud sync is integrated into the data collection pipeline:

```python
from database.data_collection_pipeline import DataCollectionPipeline

# Initialize with your credentials
pipeline = DataCollectionPipeline(username, password)

# Run daily collection - automatically syncs to GardenLMM bucket
results = pipeline.collect_daily_data()

# Database now available at:
# - Local: database/irrigation_data.db
# - Cloud: gs://hydrawise-database/latest/irrigation_data.db.gz
```

## 🔍 Monitoring

Check sync status:
```python
from database.cloud_storage_sync import CloudStorageSync

sync = CloudStorageSync('hydrawise-database')
status = sync.get_sync_status()
print(f"Last sync: {status['last_sync']}")
print(f"Should sync: {status['should_sync']}")
```

## 🆘 Troubleshooting

**"Bucket not found" error:**
- Verify bucket name: `hydrawise-database`
- Check project: `gardenlmm`
- Confirm you have access to the bucket

**Authentication errors:**
```bash
# Re-authenticate
gcloud auth application-default login

# Check current account
gcloud auth list

# Check active project
gcloud config get-value project
```

**Permission errors:**
- Verify IAM role includes Storage Object Admin
- Check bucket-level permissions
- Ensure service account has correct roles

---

🎉 **Ready to go!** Your Hydrawise data will now be safely stored and backed up in your GardenLMM Google Cloud Storage bucket.
