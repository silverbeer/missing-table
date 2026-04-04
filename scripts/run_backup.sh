#!/bin/bash
# Daily backup runner — designed to be called from cron.
# Runs APP_ENV=prod backup, stores to ~/backups/missing-table/,
# and logs output to ~/logs/missing-table-backup.log.
#
# Retention defaults (override via env vars):
#   BACKUP_KEEP_DAYS    — daily backups to keep (default: 30)
#   BACKUP_NO_MONTHLY   — set to 1 to disable monthly archives
#
# Cron entry (3 AM daily):
#   0 3 * * * /Users/silverbeer/gitrepos/missing-table/scripts/run_backup.sh

set -euo pipefail

REPO_DIR="/Users/silverbeer/gitrepos/missing-table"
BACKUP_DIR="${HOME}/backups/missing-table"
LOG_DIR="${HOME}/logs"
LOG_FILE="${LOG_DIR}/missing-table-backup.log"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
UV=$(command -v uv || echo "${HOME}/.cargo/bin/uv")

mkdir -p "${BACKUP_DIR}" "${LOG_DIR}"

echo "======================================" >> "${LOG_FILE}"
echo "Backup started: $(date '+%Y-%m-%d %H:%M:%S')" >> "${LOG_FILE}"

MONTHLY_FLAG=""
if [ "${BACKUP_NO_MONTHLY:-0}" = "1" ]; then
    MONTHLY_FLAG="--no-monthly"
fi

cd "${REPO_DIR}/backend"

APP_ENV=prod "${UV}" run python ../scripts/backup_database.py \
    --backup-dir "${BACKUP_DIR}" \
    --keep-days "${KEEP_DAYS}" \
    ${MONTHLY_FLAG} \
    >> "${LOG_FILE}" 2>&1

EXIT_CODE=$?

if [ "${EXIT_CODE}" -eq 0 ]; then
    echo "Backup finished successfully: $(date '+%Y-%m-%d %H:%M:%S')" >> "${LOG_FILE}"
else
    echo "Backup FAILED (exit ${EXIT_CODE}): $(date '+%Y-%m-%d %H:%M:%S')" >> "${LOG_FILE}"
fi

echo "" >> "${LOG_FILE}"
exit "${EXIT_CODE}"
