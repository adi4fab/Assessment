#!/bin/bash

# Base directory where logs are searched
SEARCH_DIR="."
# Backup directory where compressed archive will be stored
BACKUP_DIR="./backup"

# Current date in YYYYMMDD format
DATE=$(date +"%Y%m%d")

# Archive name
ARCHIVE_NAME="logs-$DATE.tar.gz"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Find all .log files, compress them into a tar.gz archive
find "$SEARCH_DIR" -type f -name "*.log" -print0 | tar -czf "$ARCHIVE_NAME" --null -T -

# Move archive to backup directory
mv "$ARCHIVE_NAME" "$BACKUP_DIR/"

echo "Logs compressed into $BACKUP_DIR/$ARCHIVE_NAME"
