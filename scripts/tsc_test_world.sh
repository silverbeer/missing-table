#!/usr/bin/env bash
#
# TSC test-world manager (SB-592).
#
# The TSC world is the self-contained set of is_test teams, rosters and fixtures
# the Android app is rehearsed against. Dry runs dirty it (scores, clock state),
# so it needs a repeatable seed and reset rather than hand-clicked rows.
#
#   ./scripts/tsc_test_world.sh verify           # read-only: what exists, what leaks
#   ./scripts/tsc_test_world.sh seed             # idempotent seed / roll fixtures forward
#   ./scripts/tsc_test_world.sh reset            # delete dry-run fixtures, then reseed
#
# Target database comes from $DATABASE_URL. Against anything that is not
# localhost you must also pass --yes, and the script prints what it is about to
# touch first.
#
#   set -a && . ./backend/.env.prod && set +a
#   ./scripts/tsc_test_world.sh seed --yes
#
# Everything it writes is is_test content. The seed transaction aborts itself if
# any fixture it created would be visible to a real viewer (SB-591 partition).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEED_SQL="${REPO_ROOT}/scripts/seed_tsc_test_world.sql"

CMD="${1:-}"
shift || true
ASSUME_YES=false
for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES=true ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "error: DATABASE_URL is not set." >&2
    echo "  local: set -a && . ./backend/.env.local && set +a" >&2
    echo "  prod:  set -a && . ./backend/.env.prod  && set +a" >&2
    exit 1
fi

# Redact credentials before anything is echoed.
SAFE_URL="$(printf '%s' "$DATABASE_URL" | sed -E 's#://([^:]+):[^@]+@#://\1:***@#')"

IS_LOCAL=false
if [[ "$DATABASE_URL" == *"127.0.0.1"* || "$DATABASE_URL" == *"localhost"* ]]; then
    IS_LOCAL=true
fi

psql_q() { psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 "$@"; }

confirm_if_remote() {
    if [[ "$IS_LOCAL" == true ]]; then
        return
    fi
    echo "  target is NOT local: ${SAFE_URL}"
    if [[ "$ASSUME_YES" != true ]]; then
        echo
        echo "refusing to write to a non-local database without --yes." >&2
        echo "re-run with --yes once you have checked the target above." >&2
        exit 1
    fi
    echo "  --yes given; proceeding."
}

show_state() {
    psql_q -c "
SELECT '--- TSC teams ---' AS section;
SELECT t.id, t.name,
       (c.is_test IS TRUE) AS club_is_test,
       (l.is_test IS TRUE) AS league_is_test,
       (SELECT count(*) FROM players p
          WHERE p.team_id = t.id AND p.is_active) AS players
  FROM teams t
  LEFT JOIN clubs   c ON c.id = t.club_id
  LEFT JOIN leagues l ON l.id = t.league_id
 WHERE t.name LIKE 'TSC %'
 ORDER BY t.name;

SELECT '--- dry-run fixtures ---' AS section;
SELECT m.match_id, m.match_date, m.scheduled_kickoff, m.match_status,
       h.name AS home, a.name AS away, m.is_test,
       (m.scheduled_kickoff <= now()) AS kickoff_passed
  FROM public.matches_with_test m
  JOIN teams h ON h.id = m.home_team_id
  JOIN teams a ON a.id = m.away_team_id
 WHERE m.match_id LIKE 'TSC-DRYRUN-%'
 ORDER BY m.scheduled_kickoff;

SELECT '--- leak check: any TSC content visible to a real viewer? ---' AS section;
SELECT count(*) AS leaking_matches
  FROM public.matches_with_test m
  JOIN teams h ON h.id = m.home_team_id
 WHERE h.name LIKE 'TSC %' AND NOT m.is_test;
"
}

case "$CMD" in
    verify)
        echo "== TSC test world: ${SAFE_URL}"
        show_state
        ;;

    seed)
        echo "== seeding TSC test world"
        confirm_if_remote
        psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f "$SEED_SQL"
        echo "== seeded. state now:"
        show_state
        ;;

    reset)
        echo "== resetting TSC test world (deletes TSC-DRYRUN-* fixtures, then reseeds)"
        confirm_if_remote
        # Scoped precisely: only matches this script created. Child rows first.
        psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -c "
BEGIN;
CREATE TEMP TABLE doomed ON COMMIT DROP AS
    SELECT id FROM matches WHERE match_id LIKE 'TSC-DRYRUN-%';

DELETE FROM match_events      WHERE match_id IN (SELECT id FROM doomed);
DELETE FROM match_lineups     WHERE match_id IN (SELECT id FROM doomed);
DELETE FROM player_match_stats WHERE match_id IN (SELECT id FROM doomed);
DELETE FROM matches           WHERE id IN (SELECT id FROM doomed);
COMMIT;
"
        psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f "$SEED_SQL"
        echo "== reset. state now:"
        show_state
        ;;

    *)
        echo "usage: $0 {verify|seed|reset} [--yes]" >&2
        exit 2
        ;;
esac
