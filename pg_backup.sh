#!/bin/bash

# === LOAD ENVIRONMENT VARIABLES ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.env"

# === CONFIGURATION ===
RETENTION_DAYS=30
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="${SCRIPT_DIR}/backups"
BACKUP_FILE="${BACKUP_DIR}/${DATABASE_NAME}_${DATE}.sql.gz"

# === ENSURE BACKUP DIRECTORY EXISTS ===
mkdir -p "$BACKUP_DIR"

# === ENSURE .pgpass FILE EXISTS FOR NON-INTERACTIVE AUTH ===
PGPASS_FILE="$HOME/.pgpass"
if ! grep -q "${DATABASE_HOST}:${DATABASE_PORT}:${DATABASE_NAME}:${DATABASE_USER}:${DATABASE_PASSWORD}" "$PGPASS_FILE" 2>/dev/null; then
    echo "${DATABASE_HOST}:${DATABASE_PORT}:${DATABASE_NAME}:${DATABASE_USER}:${DATABASE_PASSWORD}" >> "$PGPASS_FILE"
    chmod 600 "$PGPASS_FILE"
fi

# === PERFORM BACKUP ===
PGPASSWORD="$DATABASE_PASSWORD" pg_dump \
    -U "$DATABASE_USER" \
    -h "$DATABASE_HOST" \
    -p "$DATABASE_PORT" \
    "$DATABASE_NAME" | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup successful: $BACKUP_FILE"
else
    echo "[$(date)] Backup failed!"
    exit 1
fi

# === DELETE OLD BACKUPS ===
find "$BACKUP_DIR" -type f -name "${DATABASE_NAME}_*.sql.gz" -mtime +$RETENTION_DAYS -exec rm {} \;

exit 0