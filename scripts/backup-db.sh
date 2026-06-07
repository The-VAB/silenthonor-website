#!/bin/bash
# Silent Honor Foundation - Database Backup Script
# Run this regularly via cron to backup MongoDB

set -e

# Configuration
BACKUP_DIR="/var/backups/silenthonor"
MONGODB_URI="${MONGODB_URI:-mongodb://localhost:27017}"
DB_NAME="${MONGODB_DB:-silenthonor}"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.gz"

echo "Starting backup of $DB_NAME..."

# Create backup using mongodump
mongodump --uri="$MONGODB_URI" --db="$DB_NAME" --archive="$BACKUP_FILE" --gzip

# Verify backup was created
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup created successfully: $BACKUP_FILE ($SIZE)"
else
    echo "ERROR: Backup file was not created!"
    exit 1
fi

# Remove backups older than retention period
echo "Removing backups older than $RETENTION_DAYS days..."
find $BACKUP_DIR -name "${DB_NAME}_*.gz" -mtime +$RETENTION_DAYS -delete

# List current backups
echo ""
echo "Current backups:"
ls -lh $BACKUP_DIR/${DB_NAME}_*.gz 2>/dev/null || echo "No backups found"

echo ""
echo "Backup complete!"
