#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.env"

BACKUP_DIR="${SCRIPT_DIR}/backups"
LOG_FILE="/var/log/pg_backup.log"
CRON_JOB="0 2 */3 * * ${SCRIPT_DIR}/pg_backup.sh >> ${LOG_FILE} 2>&1"

# === CREATE BACKUP DIRECTORY ===
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# === CREATE LOG FILE ===
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

# === INSTALL CRON JOB ===
( crontab -l 2>/dev/null | grep -v "$SCRIPT_DIR/pg_backup.sh" ; echo "$CRON_JOB" ) | crontab -

echo "Setup complete."
echo "- Backups stored in: $BACKUP_DIR"
echo "- Logs stored in: $LOG_FILE"
echo "- Cron job: every 3 days at 2 AM"