#!/usr/bin/env bash
#
# Merge Cloudflare R2 credentials from a 1Password item into the
# `missing-table-app-secrets` AWS Secrets Manager secret (a JSON blob), which
# External Secrets Operator syncs into the k8s `missing-table-secrets` used by
# the backend. Fixes the prod 503 ("Cloudflare R2 is not configured") that
# breaks match-photo upload + Android APK download (SB-326).
#
#   ./scripts/set-r2-aws-secret.sh
#
# Reads these fields from the 1Password item (same item as the android release
# secrets): r2_account_id · r2_access_key_id · r2_secret_access_key
# r2_bucket defaults to mt-match-photos.
#
# Env overrides:
#   OP_VAULT       default: Personal
#   OP_ITEM        default: mt-android-release
#   AWS_SECRET_ID  default: missing-table-app-secrets
#   AWS_REGION     default: us-east-2
#   R2_BUCKET      default: mt-match-photos
set -euo pipefail

VAULT="${OP_VAULT:-Personal}"
ITEM="${OP_ITEM:-mt-android-release}"
SECRET_ID="${AWS_SECRET_ID:-missing-table-app-secrets}"
REGION="${AWS_REGION:-us-east-2}"
BUCKET="${R2_BUCKET:-mt-match-photos}"

for c in op aws jq; do
  command -v "$c" >/dev/null || { echo "✗ missing command: $c" >&2; exit 1; }
done
op whoami >/dev/null 2>&1 || eval "$(op signin)"
aws sts get-caller-identity >/dev/null 2>&1 || { echo "✗ aws not authenticated" >&2; exit 1; }

field() {
  op read "op://${VAULT}/${ITEM}/$1" 2>/dev/null ||
    { echo "✗ couldn't read '$1' from op://${VAULT}/${ITEM}" >&2; exit 1; }
}

echo "→ reading R2 creds from 1Password item: ${ITEM}"
r2_account="$(field r2_account_id)"
r2_key="$(field r2_access_key_id)"
r2_secret="$(field r2_secret_access_key)"

# Temp file (0600) so the full secret JSON never lands in process args or history.
tmp="$(mktemp)"
chmod 600 "$tmp"
trap 'rm -f "$tmp"' EXIT

echo "→ merging r2_* into AWS Secrets Manager: ${SECRET_ID} (${REGION})"
aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
  --query SecretString --output text |
  jq --arg a "$r2_account" --arg k "$r2_key" --arg s "$r2_secret" --arg b "$BUCKET" \
    '. + {r2_account_id:$a, r2_access_key_id:$k, r2_secret_access_key:$s, r2_bucket:$b}' \
    > "$tmp"

aws secretsmanager put-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
  --secret-string "file://${tmp}" >/dev/null

echo "✓ done. keys now: $(jq -r 'keys | join(", ")' "$tmp")"
cat <<'NOTE'

Next (ESO → k8s → backend):
  1. If the ExternalSecret uses per-key mapping (not dataFrom), add these to it:
       r2-account-id ← r2_account_id
       r2-access-key-id ← r2_access_key_id
       r2-secret-access-key ← r2_secret_access_key
       r2-bucket ← r2_bucket
     (If it uses dataFrom with an underscore→hyphen rewrite, nothing to change.)
  2. Force a sync + restart the backend so it picks up the new env:
       kubectl annotate externalsecret <name> -n missing-table force-sync=$(date +%s) --overwrite
       kubectl rollout restart deployment/missing-table-backend -n missing-table
  3. Verify: authed GET /api/android/apk-url returns { download_url }.
NOTE
