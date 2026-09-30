#!/usr/bin/env bash
#
# Merge the Gemini API key used by MT AI into the `missing-table-app-secrets`
# AWS Secrets Manager secret (a JSON blob), under `google_api_key`. External
# Secrets Operator maps it into k8s `missing-table-secrets` as `google-api-key`,
# which the backend reads as GOOGLE_API_KEY (SB-1144).
#
#   ./scripts/set-google-api-key-aws-secret.sh
#
# Run it in a real terminal: it prompts for the key with echo off. The key never
# appears on screen, in shell history, or in any process's arguments — it goes
# prompt → environment → jq → a 0600 temp file → AWS.
#
# Use a key from a BILLING-ENABLED Google project. On the free tier Google may
# use prompts and responses to improve its products; MT AI's questions come
# from parents about their children's teams.
#
# Env overrides:
#   AWS_SECRET_ID  default: missing-table-app-secrets
#   AWS_REGION     default: us-east-2
set -euo pipefail

SECRET_ID="${AWS_SECRET_ID:-missing-table-app-secrets}"
REGION="${AWS_REGION:-us-east-2}"

for c in aws jq; do
  command -v "$c" >/dev/null || { echo "✗ missing command: $c" >&2; exit 1; }
done
[ -t 0 ] || { echo "✗ needs a terminal: the key is read with echo off" >&2; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || { echo "✗ aws not authenticated" >&2; exit 1; }

read -r -s -p "Gemini API key (input hidden): " MT_GOOGLE_API_KEY
echo
[ -n "$MT_GOOGLE_API_KEY" ] || { echo "✗ no key entered" >&2; exit 1; }
case "$MT_GOOGLE_API_KEY" in
  AIza*) ;;
  *) echo "ℹ key does not start with 'AIza' — fine for newer keys (e.g. 53 chars); older ones do" >&2 ;;
esac
export MT_GOOGLE_API_KEY

tmp="$(mktemp)"
chmod 600 "$tmp"
trap 'rm -f "$tmp"; unset MT_GOOGLE_API_KEY' EXIT

echo "→ merging google_api_key into AWS Secrets Manager: ${SECRET_ID} (${REGION})"
aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
  --query SecretString --output text |
  jq '. + {google_api_key: env.MT_GOOGLE_API_KEY}' > "$tmp"

aws secretsmanager put-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
  --secret-string "file://${tmp}" >/dev/null

echo "✓ done. keys now: $(jq -r 'keys | join(", ")' "$tmp")"
echo "  ESO refreshes hourly; to sync now:"
echo "  kubectl annotate externalsecret missing-table-app-secrets -n missing-table force-sync=\$(date +%s) --overwrite"
