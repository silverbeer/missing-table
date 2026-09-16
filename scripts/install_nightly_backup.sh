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
# not matter.
#
# It also retires the old run_backup.sh crontab entry, after saving a copy of
# the crontab — but only if it can. On macOS `crontab -` from a process with no
# terminal waits on a permission prompt nobody can see: it hung for ten minutes
# during the SB-1070 install, and `set -e` then reported the whole install as
# failed even though both jobs were already loaded (SB-1077). Now that step is
# skipped when there is no terminal, watchdogged when there is, and never fatal
# — the command to run by hand is printed instead.
#
# Settings (environment, all optional):
#   MT_CRONTAB_CMD      the crontab command to use          (crontab)
#   MT_CRONTAB_TIMEOUT  seconds to wait for a crontab write (10)
#   MT_CRONTAB_FORCE    1 to attempt the write with no terminal

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
RUNNER_DIR="${MT_BACKUP_RUNNER:-$HOME/.local/share/missing-table-backup}"
SECRETS_DIR="${MT_ALERT_SECRETS_DIR:-$HOME/.config/cycle-runner}"
AGENTS_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
LABELS="io.silverbeer.mt.backup io.silverbeer.mt.backupcheck"
CRONTAB_CMD="${MT_CRONTAB_CMD:-crontab}"
CRONTAB_TIMEOUT="${MT_CRONTAB_TIMEOUT:-10}"

unload() {
    launchctl bootout "$DOMAIN/$1" 2> /dev/null || true
}

cron_instructions() {
    echo "  Run this in a terminal to retire it:"
    echo "    crontab -l | grep -v 'scripts/run_backup.sh' | crontab -"
    echo "  The jobs above already replace it; left alone it just fails at 03:00 as before."
}

# 0 removed (or nothing to remove), 2 skipped (no terminal), 3 the write hung.
# Never exits: the jobs are the install, this is tidying up after cron.
retire_cron_entry() {
    local current filtered saved pid waited

    current="$("$CRONTAB_CMD" -l 2> /dev/null || true)"
    case "$current" in
        *scripts/run_backup.sh*) ;;
        *) return 0 ;;
    esac

    if [ "${MT_CRONTAB_FORCE:-0}" != "1" ] && { [ ! -t 0 ] || [ ! -t 1 ]; }; then
        return 2
    fi

    saved="$HOME/.local/share/crontab.before-sb-1070.$(date +%Y%m%d%H%M%S)"
    mkdir -p "$(dirname "$saved")"
    printf '%s\n' "$current" > "$saved"
    filtered="$(printf '%s\n' "$current" | grep -v 'scripts/run_backup.sh' || true)"

    printf '%s\n' "$filtered" | "$CRONTAB_CMD" - &
    pid=$!
    waited=0
    while kill -0 "$pid" 2> /dev/null && [ "$waited" -lt "$CRONTAB_TIMEOUT" ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if kill -0 "$pid" 2> /dev/null; then
        # SIGTERM first, but bash defers it while a foreground child runs, so
        # escalate: otherwise `wait` blocks for as long as the write would have.
        kill "$pid" 2> /dev/null || true
        sleep 1
        kill -9 "$pid" 2> /dev/null || true
        wait "$pid" 2> /dev/null || true
        return 3
    fi
    wait "$pid" || return 3

    echo "✓ Removed the old run_backup.sh crontab entry (previous crontab saved to $saved)"
    return 0
}

print_summary() {
    local cron_status="$1" label
    echo ""
    echo "Installed. Both jobs are loaded:"
    for label in $LABELS; do
        echo "  $label"
    done
    case "$cron_status" in
        0) ;;
        2)
            echo ""
            echo "⚠ Left the old run_backup.sh cron entry alone: this was not run from a terminal."
            cron_instructions
            ;;
        *)
            echo ""
            echo "⚠ Could not retire the old cron entry: the crontab write did not finish in ${CRONTAB_TIMEOUT}s."
            echo "  macOS may be waiting on a permission prompt that only appears in an interactive session."
            cron_instructions
            ;;
    esac
    cat << EOF

Next:
  bash "$SCRIPT_DIR/run_backup.sh" --test-alert                    # confirm alerts reach you
  launchctl kickstart "$DOMAIN/io.silverbeer.mt.backup"            # run a backup now
  tail -f ~/Library/Logs/missing-table-backup.log
EOF
}

main() {
    if [ "${1:-}" = "--uninstall" ]; then
        for label in $LABELS; do
            unload "$label"
            rm -f "$AGENTS_DIR/$label.plist"
            echo "✓ Removed $label"
        done
        echo "Backups in ~/backups/missing-table are untouched."
        echo "The runner checkout is still at $RUNNER_DIR; remove it with:"
        echo "  git -C \"$REPO_DIR\" worktree remove --force \"$RUNNER_DIR\""
        return 0
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

    cron_status=0
    retire_cron_entry || cron_status=$?
    print_summary "$cron_status"
}

# Sourced by the tests to exercise retire_cron_entry on its own; run directly it
# installs.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
