#!/bin/bash
# Install, or remove, the nightly Missing Table backup as launchd jobs (SB-1070).
#
#   scripts/install_nightly_backup.sh              install or reinstall
#   scripts/install_nightly_backup.sh --uninstall  remove the jobs (backups are kept)
#
# Installs two jobs from scripts/launchd/:
#   io.silverbeer.mt.backup        03:00  back up production, apply retention, alert on failure
#   io.silverbeer.mt.backupcheck   09:00  alert if the newest usable backup is over 26h old
#
# Both run scripts/run_backup.sh from a dedicated checkout of origin/main at
# ~/.local/share/missing-table-backup, so the branch this checkout is on does
# not matter. The old crontab entry for run_backup.sh is removed, after saving
# a copy of the crontab.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
RUNNER_DIR="${MT_BACKUP_RUNNER:-$HOME/.local/share/missing-table-backup}"
SECRETS_DIR="${MT_ALERT_SECRETS_DIR:-$HOME/.config/cycle-runner}"
AGENTS_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
LABELS="io.silverbeer.mt.backup io.silverbeer.mt.backupcheck"

unload() {
    launchctl bootout "$DOMAIN/$1" 2> /dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
    for label in $LABELS; do
        unload "$label"
        rm -f "$AGENTS_DIR/$label.plist"
        echo "✓ Removed $label"
    done
    echo "Backups in ~/backups/missing-table are untouched."
    echo "The runner checkout is still at $RUNNER_DIR; remove it with:"
    echo "  git -C \"$REPO_DIR\" worktree remove --force \"$RUNNER_DIR\""
    exit 0
fi

if [ ! -f "$REPO_DIR/backend/.env.prod" ]; then
    echo "❌ $REPO_DIR/backend/.env.prod not found — the backup needs production credentials." >&2
    exit 1
fi

if [ -r "$SECRETS_DIR/telegram-token" ] && [ -r "$SECRETS_DIR/telegram-chat-id" ]; then
    echo "✓ Telegram alert credentials found in $SECRETS_DIR"
else
    echo "⚠ No Telegram credentials in $SECRETS_DIR — alerts will be macOS notifications only."
fi

echo "Preparing the runner checkout at $RUNNER_DIR ..."
if ! MT_REPO_DIR="$REPO_DIR" MT_BACKUP_RUNNER="$RUNNER_DIR" bash "$SCRIPT_DIR/run_backup.sh" --prepare; then
    echo "❌ Could not prepare the runner checkout; see ~/Library/Logs/missing-table-backup.log" >&2
    exit 1
fi
echo "✓ Runner at $(git -C "$RUNNER_DIR" rev-parse --short HEAD) (origin/main)"

mkdir -p "$AGENTS_DIR"
for label in $LABELS; do
    dest="$AGENTS_DIR/$label.plist"
    sed "s#/Users/USERNAME#$HOME#g" "$SCRIPT_DIR/launchd/$label.plist" > "$dest"
    plutil -lint -s "$dest"
    unload "$label"
    launchctl bootstrap "$DOMAIN" "$dest"
    echo "✓ Loaded $label"
done

if crontab -l 2> /dev/null | grep -q 'scripts/run_backup.sh'; then
    saved="$HOME/.local/share/crontab.before-sb-1070.$(date +%Y%m%d%H%M%S)"
    mkdir -p "$(dirname "$saved")"
    crontab -l > "$saved"
    { crontab -l | grep -v 'scripts/run_backup.sh' || true; } | crontab -
    echo "✓ Removed the old run_backup.sh crontab entry (previous crontab saved to $saved)"
fi

cat << EOF

Installed. Next:
  bash "$SCRIPT_DIR/run_backup.sh" --test-alert                    # confirm alerts reach you
  launchctl kickstart "$DOMAIN/io.silverbeer.mt.backup"            # run a backup now
  tail -f ~/Library/Logs/missing-table-backup.log
EOF
