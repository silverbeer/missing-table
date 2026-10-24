#!/usr/bin/env bash
#
# Merge the App Store Connect API key (TestFlight beta invites, SB-1314) from a
# 1Password item into the `missing-table-app-secrets` AWS Secrets Manager secret
# (a JSON blob), which External Secrets Operator syncs into the k8s
# `missing-table-secrets` the backend reads ASC_* from (SB-1414).
#
# Usage: scripts/set-asc-aws-secret.sh <external-beta-group-id>
#
# The group id is not secret: list the app's groups with the same key in App
# Store Connect -> TestFlight, or via GET /v1/apps/{id}/betaGroups. It must be
# the EXTERNAL group: invited users are not App Store Connect team members.
#
# Values never touch the terminal or argv: they go op -> env -> jq -> a 0600
# temp file -> aws.
set -euo pipefail

SECRET_ID="${AWS_SECRET_ID:-missing-table-app-secrets}"
REGION="${AWS_REGION:-us-east-2}"
OP_ITEM="${OP_ITEM:-op://agents/mt-ios-asc}"

GROUP_ID="${1:-}"
[[ "$GROUP_ID" =~ ^[0-9a-f-]{36}$ ]] || { echo "usage: $0 <external-beta-group-id (uuid)>" >&2; exit 1; }

for c in aws jq op; do
  command -v "$c" >/dev/null || { echo "✗ missing command: $c" >&2; exit 1; }
done
aws sts get-caller-identity >/dev/null 2>&1 || { echo "✗ aws not authenticated" >&2; exit 1; }

MT_ASC_KEY_ID="$(op read "${OP_ITEM}/key_id")"
MT_ASC_ISSUER_ID="$(op read "${OP_ITEM}/issuer_id")"
MT_ASC_PRIVATE_KEY="$(op read "${OP_ITEM}/private_key")"
MT_ASC_EXTERNAL_GROUP_ID="$GROUP_ID"
export MT_ASC_KEY_ID MT_ASC_ISSUER_ID MT_ASC_PRIVATE_KEY MT_ASC_EXTERNAL_GROUP_ID

[ ${#MT_ASC_KEY_ID} -eq 10 ] || { echo "✗ key_id is not 10 characters" >&2; exit 1; }
[ ${#MT_ASC_ISSUER_ID} -eq 36 ] || { echo "✗ issuer_id is not a uuid" >&2; exit 1; }
case "$MT_ASC_PRIVATE_KEY" in
  "-----BEGIN PRIVATE KEY-----"*) ;; # pragma: allowlist secret - the PEM header, not a key
  *) echo "✗ private_key is not a PEM (.p8 contents)" >&2; exit 1 ;;
esac

tmp="$(mktemp)"
chmod 600 "$tmp"
trap 'rm -f "$tmp"; unset MT_ASC_KEY_ID MT_ASC_ISSUER_ID MT_ASC_PRIVATE_KEY MT_ASC_EXTERNAL_GROUP_ID' EXIT

echo "→ merging asc_* into AWS Secrets Manager: ${SECRET_ID} (${REGION})"
aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
  --query SecretString --output text |
  jq '. + {
    asc_key_id: env.MT_ASC_KEY_ID,
    asc_issuer_id: env.MT_ASC_ISSUER_ID,
    asc_private_key: env.MT_ASC_PRIVATE_KEY,
    asc_external_group_id: env.MT_ASC_EXTERNAL_GROUP_ID
  }' > "$tmp"

aws secretsmanager put-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
  --secret-string "file://${tmp}" >/dev/null

echo "✓ done. keys now: $(jq -r 'keys | join(", ")' "$tmp")"
echo "  The ExternalSecret must map asc-* (missingtable-platform-bootstrap). ESO refreshes hourly; to sync now:"
echo "  kubectl --context lke560651-ctx annotate externalsecret missing-table-app-secrets -n missing-table force-sync=\$(date +%s) --overwrite"
echo "  then: kubectl --context lke560651-ctx -n missing-table rollout restart deploy/missing-table-backend"
