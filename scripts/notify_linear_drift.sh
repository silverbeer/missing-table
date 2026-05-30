#!/usr/bin/env bash
# Schema-drift guard notifier (SB-79).
#
# Called by .github/workflows/migration-drift.yml when the drift check fails.
# Files a Linear issue describing the drift, or — if an open one already exists
# — adds a comment instead of duplicating. Idempotent across daily runs.
#
# Env:
#   LINEAR_API_KEY  (required) Linear personal API key
#   LINEAR_TEAM_KEY (default SB) team key to file under
# Args:
#   $1  path to the drift report text file
set -euo pipefail

REPORT_FILE="${1:?usage: notify_linear_drift.sh <report-file>}"
TEAM_KEY="${LINEAR_TEAM_KEY:-SB}"
TITLE="[drift-guard] Prod migration drift detected"
API="https://api.linear.app/graphql"

if [[ -z "${LINEAR_API_KEY:-}" ]]; then
  echo "LINEAR_API_KEY not set — skipping Linear notification (drift still failed the build)."
  exit 0
fi

report_body="$(cat "$REPORT_FILE")"
# Body: fenced report so it renders in Linear.
body="$(printf 'Automated drift check failed. See \`scripts/check_migration_drift.py\` (SB-79).\n\n```\n%s\n```\n\nFix via the prod-reconciliation ticket (SB-80).' "$report_body")"

gql() {
  # $1 = query, $2 = variables JSON
  curl -fsS -X POST "$API" \
    -H "Authorization: ${LINEAR_API_KEY}" \
    -H "Content-Type: application/json" \
    --data "$(jq -n --arg q "$1" --argjson v "$2" '{query:$q, variables:$v}')"
}

team_id="$(gql 'query($k:String!){ teams(filter:{key:{eq:$k}}){ nodes{ id } } }' \
  "$(jq -n --arg k "$TEAM_KEY" '{k:$k}')" | jq -r '.data.teams.nodes[0].id // empty')"
if [[ -z "$team_id" ]]; then
  echo "Could not resolve Linear team '$TEAM_KEY'." >&2
  exit 1
fi

# Existing open issue with our marker title?
existing="$(gql 'query($t:String!){ issues(filter:{ title:{ eq:$t }, completedAt:{ null:true }, canceledAt:{ null:true } }){ nodes{ id identifier url } } }' \
  "$(jq -n --arg t "$TITLE" '{t:$t}')")"
issue_id="$(echo "$existing" | jq -r '.data.issues.nodes[0].id // empty')"

if [[ -n "$issue_id" ]]; then
  url="$(echo "$existing" | jq -r '.data.issues.nodes[0].url')"
  gql 'mutation($i:String!,$b:String!){ commentCreate(input:{issueId:$i, body:$b}){ success } }' \
    "$(jq -n --arg i "$issue_id" --arg b "$body" '{i:$i,b:$b}')" >/dev/null
  echo "Drift still open — commented on existing issue: $url"
else
  created="$(gql 'mutation($t:String!,$d:String!,$tm:String!){ issueCreate(input:{title:$t, description:$d, teamId:$tm}){ issue{ identifier url } } }' \
    "$(jq -n --arg t "$TITLE" --arg d "$body" --arg tm "$team_id" '{t:$t,d:$d,tm:$tm}')")"
  echo "Filed new Linear issue: $(echo "$created" | jq -r '.data.issueCreate.issue.url')"
fi
