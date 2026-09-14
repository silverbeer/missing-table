#!/bin/bash
# Nightly production backup for Missing Table (SB-1070).
#
#   run_backup.sh               back up prod, apply retention, alert on failure
#   run_backup.sh --check       alert when the newest usable backup is too old
#   run_backup.sh --prepare     create or refresh the runner checkout, nothing else
#   run_backup.sh --test-alert  send a test alert
#
# Scheduled by launchd — scripts/launchd/, installed by
# scripts/install_nightly_backup.sh: the backup at 03:00, the check at 09:00.
# The check is what notices a backup that never ran at all.
#
# This used to run from cron, from the dev checkout, looking for uv in
# ~/.cargo/bin. uv lives in ~/.local/bin, so it failed every night from
# 2026-04-05 to 2026-09-14, and set -e exited before the failure was logged.
#
# It now runs from its own checkout of origin/main (MT_BACKUP_RUNNER), refreshed
# on every run, so whichever branch the dev checkout has cannot decide which
# backup code runs.
#
# Settings (environment, all optional):
#   MT_REPO_DIR           dev checkout holding backend/.env.prod  (~/gitrepos/missing-table)
#   MT_BACKUP_RUNNER      checkout the job runs from              (~/.local/share/missing-table-backup)
#   MT_BACKUP_REF         what that checkout is moved to           (origin/main)
#   BACKUP_DIR            where backups are written                (~/backups/missing-table)
#   BACKUP_LOG            log file                                 (~/Library/Logs/missing-table-backup.log)
#   BACKUP_KEEP_DAYS      days of daily backups to keep            (30)
#   BACKUP_NO_MONTHLY     1 disables the monthly archive
#   BACKUP_MAX_AGE_HOURS  --check alerts beyond this age           (26)
#   MT_ALERT_SECRETS_DIR  holds telegram-token, telegram-chat-id   (~/.config/cycle-runner)

# No `set -e`: every failure here is handled explicitly, because an unhandled
# one exits silently — which is how this job failed unnoticed for five months.
set -uo pipefail

REPO_DIR="${MT_REPO_DIR:-$HOME/gitrepos/missing-table}"
RUNNER_DIR="${MT_BACKUP_RUNNER:-$HOME/.local/share/missing-table-backup}"
BACKUP_REF="${MT_BACKUP_REF:-origin/main}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/missing-table}"
LOG_FILE="${BACKUP_LOG:-$HOME/Library/Logs/missing-table-backup.log}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-26}"
SECRETS_DIR="${MT_ALERT_SECRETS_DIR:-$HOME/.config/cycle-runner}"
HOST="$(hostname -s 2>/dev/null || echo unknown-host)"
UV=""

mkdir -p "$BACKUP_DIR" "$(dirname "$LOG_FILE")"

log() {
    printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

notify_macos() {
    # Title and message reach AppleScript as arguments, so quotes in them are harmless.
    osascript - "$1" "$2" > /dev/null 2>&1 <<'APPLESCRIPT' || true
on run argv
    display notification (item 2 of argv) with title (item 1 of argv)
end run
APPLESCRIPT
}

# Send $1 to Telegram, falling back to a macOS notification. Never fails the caller.
alert() {
    local text="$1"
    local first_line="${text%%$'\n'*}"
    local token_file="$SECRETS_DIR/telegram-token"
    local chat_file="$SECRETS_DIR/telegram-chat-id"
    log "ALERT: $first_line"

    if [ -r "$token_file" ] && [ -r "$chat_file" ]; then
        # The token travels on stdin as curl config — never on a command line,
        # where ps could show it.
        if printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$(tr -d '[:space:]' < "$token_file")" |
            curl --silent --show-error --fail --max-time 20 --config - \
                --data-urlencode "chat_id=$(tr -d '[:space:]' < "$chat_file")" \
                --data-urlencode "text=$text" \
                --output /dev/null 2>> "$LOG_FILE"; then
            return 0
        fi
        log "Telegram alert could not be sent; falling back to a macOS notification"
    else
        log "No Telegram credentials in $SECRETS_DIR; falling back to a macOS notification"
    fi
    notify_macos "Missing Table backup" "$first_line"
}

find_uv() {
    local candidate
    for candidate in "$(command -v uv 2> /dev/null)" "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv "$HOME/.cargo/bin/uv"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

# Bring the runner checkout to $BACKUP_REF (origin/main). If GitHub cannot be reached, carry
# on with the runner's last checkout rather than skip a backup.
refresh_runner() {
    if [ ! -e "$RUNNER_DIR/.git" ]; then
        log "Creating runner checkout at $RUNNER_DIR"
        git -C "$REPO_DIR" fetch --quiet origin main >> "$LOG_FILE" 2>&1 || return 1
        mkdir -p "$(dirname "$RUNNER_DIR")"
        git -C "$REPO_DIR" worktree add --quiet --detach "$RUNNER_DIR" "$BACKUP_REF" >> "$LOG_FILE" 2>&1 || return 1
    elif git -C "$REPO_DIR" fetch --quiet origin main >> "$LOG_FILE" 2>&1; then
        git -C "$RUNNER_DIR" checkout --quiet --force --detach "$BACKUP_REF" >> "$LOG_FILE" 2>&1 || return 1
    else
        log "WARNING: could not fetch origin/main; using the runner's last checkout"
    fi

    # Credentials are gitignored, so the runner borrows the dev checkout's copy.
    if [ ! -f "$REPO_DIR/backend/.env.prod" ]; then
        log "$REPO_DIR/backend/.env.prod not found"
        return 1
    fi
    ln -sfn "$REPO_DIR/backend/.env.prod" "$RUNNER_DIR/backend/.env.prod" || return 1
    log "Runner at $(git -C "$RUNNER_DIR" rev-parse --short HEAD)"
}

# Run backup_database.py from the runner, writing its output to the file in $1.
# A fresh checkout builds its own environment: backend/.python-version pins
# Python 3.13 (psycopg2-binary has no 3.14 wheel, and uv would otherwise pick
# the newest interpreter), and --frozen keeps the job from rewriting uv.lock.
backup_py() {
    local output="$1"
    shift
    (cd "$RUNNER_DIR/backend" && "$UV" run --quiet --frozen python ../scripts/backup_database.py "$@") > "$output" 2>&1
}

do_backup() {
    local output code monthly_flag=""
    [ "${BACKUP_NO_MONTHLY:-0}" = "1" ] && monthly_flag="--no-monthly"
    output="$(mktemp)"
    log "Backup started"

    # $monthly_flag is unquoted on purpose: empty means no argument at all.
    if backup_py "$output" --env prod --backup-dir "$BACKUP_DIR" --keep-days "$KEEP_DAYS" $monthly_flag; then
        code=0
    else
        code=$?
    fi
    cat "$output" >> "$LOG_FILE"

    if [ "$code" -eq 0 ]; then
        log "Backup finished successfully"
        # A table created outside the migrations (Studio, a hand-run script) is
        # invisible to the CI coverage test; only this run-time check sees it.
        if grep -q "NOT in backup list" "$output"; then
            alert "⚠️ Missing Table backup on $HOST succeeded, but prod has tables nothing backs up:
$(sed -n '/NOT in backup list/,/Add these/p' "$output" | grep -E '^[[:space:]]+- ')

Add each to TABLES_TO_BACKUP or EXCLUDED_TABLES in scripts/backup_database.py."
        fi
    else
        log "Backup FAILED (exit $code)"
        alert "❌ Missing Table nightly prod backup FAILED (exit $code) on $HOST

$(tail -n 20 "$output" | cut -c1-300)

Log: $LOG_FILE"
    fi
    rm -f "$output"
    return "$code"
}

do_check() {
    local output code
    output="$(mktemp)"
    if backup_py "$output" --check-fresh "$MAX_AGE_HOURS" --backup-dir "$BACKUP_DIR"; then
        code=0
    else
        code=$?
    fi
    log "Freshness check (exit $code): $(tail -n 1 "$output")"

    if [ "$code" -ne 0 ]; then
        alert "⚠️ Missing Table backups on $HOST are stale

$(tail -n 5 "$output" | cut -c1-300)

The 03:00 backup has not produced a usable backup. Log: $LOG_FILE"
    fi
    rm -f "$output"
    return "$code"
}

main() {
    local mode
    case "${1:-}" in
        "") mode=backup ;;
        --check) mode=check ;;
        --prepare) mode=prepare ;;
        --test-alert)
            alert "🧪 Missing Table backup alert test from $HOST. If you can read this, failures will reach you."
            return 0
            ;;
        -h | --help)
            sed -n '2,30p' "$0"
            return 0
            ;;
        *)
            echo "Unknown argument: $1 (try --help)" >&2
            return 2
            ;;
    esac

    if ! UV="$(find_uv)"; then
        alert "❌ Missing Table backup ($mode) on $HOST could not start: uv not found on PATH, in ~/.local/bin, /opt/homebrew/bin or /usr/local/bin"
        return 1
    fi

    if ! refresh_runner; then
        alert "❌ Missing Table backup ($mode) on $HOST could not start: the runner checkout at $RUNNER_DIR could not be prepared. Log: $LOG_FILE"
        return 1
    fi

    case "$mode" in
        prepare) return 0 ;;
        check) do_check ;;
        *) do_backup ;;
    esac
}

# One line, on purpose: this script runs from the checkout it updates, and bash
# reads a script as it goes. Parsing `exit` together with `main` means nothing
# after it is read from a file that may have just changed on disk.
main "$@"; exit "$?"
