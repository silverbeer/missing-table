#!/usr/bin/env bash
# Match of the Week ranking: tests, and the table on real data.
#
#   scripts/motw.sh test                    scoring unit tests, no network
#   scripts/motw.sh rank                    this checkout's ranking on prod data, read-only
#     [--week YYYY-MM-DD] [--top N] [--rematches] [--env local] [--pool pathway] [--age-group U16]
#   scripts/motw.sh live [--since 24h]      the last ranking prod actually ran, from its logs
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-lke560651-ctx}"
cmd="${1:-}"
[ $# -gt 0 ] && shift

case "$cmd" in
test)
    cd "$ROOT/backend"
    exec uv run pytest tests/unit/mt_ai/test_motw_candidates.py -q -n0 --no-cov "$@"
    ;;
rank)
    cd "$ROOT/backend"
    exec uv run python scripts/utilities/motw_rank.py "$@"
    ;;
live)
    since=24h
    if [ "${1:-}" = "--since" ]; then since="$2"; fi
    line="$(kubectl --context "$CONTEXT" -n missing-table logs deploy/missing-table-backend \
        -c backend --since="$since" | grep motw_candidates_scored | tail -1 || true)"
    if [ -z "$line" ]; then
        echo "No ranking in the last $since of backend logs. Logs reset on each deploy." >&2
        exit 1
    fi
    echo "$line" | jq -r '"#\tTOTAL\tQUAL\tCLOSE\tSTAKES\tFORM\tAGE\tMATCH\tFLAGS",
        (.candidates | to_entries[] | [.key+1, .value.total, .value.quality, .value.closeness,
         .value.stakes, .value.form, .value.age_group, .value.fixture,
         (.value.flags | join(","))] | @tsv)' | column -t -s $'\t'
    ;;
*)
    sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
