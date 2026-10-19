#!/usr/bin/env bash
#
# Rotate SERVICE_ACCOUNT_SECRET end to end (SB-1356).
#
# One secret signs three kinds of token: legacy service-account JWTs (the
# scraper's, with manage_matches), SB-1145 API-account tokens (MT AI eval, mt-mcp
# machine clients) and password-reset links. Rotating it means touching every
# place that holds the secret or a token signed with it:
#
#   AWS Secrets Manager  missing-table-app-secrets.service_account_secret
#                        → ESO → k8s missing-table-secrets → prod backend (LKE)
#   home k3s             missing-table-worker-prod-secrets.SERVICE_ACCOUNT_SECRET (celery worker)
#   home k3s             match-scraper-agent-secret.AGENT_MISSING_TABLE_API_KEY (scraper token)
#   ~/.config/mt         ai_eval_real / ai_eval_test prod tokens
#   backend/.env.*       local copies
#   GitHub               PROD_SERVICE_ACCOUNT_SECRET (stale, read by no workflow — deleted)
#
#   ./scripts/rotate-service-account-secret.sh check    # read-only: does local .env.prod hold prod's value?
#   ./scripts/rotate-service-account-secret.sh verify   # read-only: do AWS, k8s, the pod and the worker agree?
#   ./scripts/rotate-service-account-secret.sh rotate   # the whole rotation; asks once before writing
#
# Nothing here prints a secret or puts one in a process's arguments: values live
# in 0600 files under a private temp dir and reach aws/kubectl/jq by path. Output
# is 12-character SHA-256 prefixes only.
#
# The scraper gets 401s from the backend restart until its secret is patched a
# minute later. A failed run is safe to re-run: it starts a fresh rotation.
#
# Env overrides:
#   AWS_SECRET_ID   default: missing-table-app-secrets
#   AWS_REGION      default: us-east-2 (the ClusterSecretStore's region)
#   PROD_CONTEXT    default: lke560651-ctx      PROD_NS  default: missing-table
#   HOME_CONTEXT    default: rancher-desktop    HOME_NS  default: match-scraper
#   MT_TOKEN_DIR    default: ~/.config/mt
#   MT_REPO_ROOT    default: this script's checkout (set it when running from a worktree)
set -euo pipefail

SECRET_ID="${AWS_SECRET_ID:-missing-table-app-secrets}"
REGION="${AWS_REGION:-us-east-2}"
PROD_CONTEXT="${PROD_CONTEXT:-lke560651-ctx}"
PROD_NS="${PROD_NS:-missing-table}"
HOME_CONTEXT="${HOME_CONTEXT:-rancher-desktop}"
HOME_NS="${HOME_NS:-match-scraper}"
TOKEN_DIR="${MT_TOKEN_DIR:-$HOME/.config/mt}"

AWS_KEY="service_account_secret"
PROD_SECRET="missing-table-secrets"  # pragma: allowlist secret
PROD_KEY="service-account-secret"
BACKEND="deploy/missing-table-backend"
POD_PY="/app/.venv/bin/python"
WORKER_SECRET="missing-table-worker-prod-secrets"  # pragma: allowlist secret
WORKER_KEY="SERVICE_ACCOUNT_SECRET"
SCRAPER_SECRET="match-scraper-agent-secret"  # pragma: allowlist secret
SCRAPER_KEY="AGENT_MISSING_TABLE_API_KEY"
EVAL_ACCOUNTS="ai_eval_real ai_eval_test"
GH_REPO="silverbeer/missing-table"
GH_STALE="PROD_SERVICE_ACCOUNT_SECRET"

# The checkout whose backend/.env.* to read and rewrite (a worktree has none).
REPO_ROOT="${MT_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

WORK="$(mktemp -d)"
chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT

die() { echo "✗ $*" >&2; exit 1; }
step() { echo; echo "── $*"; }

# SHA-256 prefix of stdin, trailing newline ignored. "absent" for empty input.
fp() {
  local v
  v="$(cat)"
  [ -n "$v" ] || { echo "absent"; return; }
  printf '%s' "$v" | shasum -a 256 | cut -c1-12
}

pk() { kubectl --context "$PROD_CONTEXT" -n "$PROD_NS" "$@"; }
hk() { kubectl --context "$HOME_CONTEXT" -n "$HOME_NS" "$@"; }

# Value of one key of a k8s secret, decoded, on stdout. Empty if absent.
k8s_secret_value() {  # <kubectl-fn> <secret> <key>
  "$1" get secret "$2" -o json | jq -r --arg k "$3" '.data[$k] // empty | @base64d'
}

aws_value() {
  aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
    --query SecretString --output text | jq -r --arg k "$AWS_KEY" '.[$k] // empty'
}

local_value() {  # <env file>
  [ -f "$1" ] || return 0
  sed -n 's/^SERVICE_ACCOUNT_SECRET=//p' "$1" | tail -1
}

# Deployments whose pod spec reads <secret> (any key via envFrom, or <key> via env).
deployments_using() {  # <kubectl-fn> <secret> <key>
  "$1" get deploy -o json | jq -r --arg s "$2" --arg k "$3" '
    .items[]
    | select([.spec.template.spec.containers[]
              | ((.envFrom // [])[] | .secretRef.name? == $s),
                ((.env // [])[] | .valueFrom.secretKeyRef? | select(. != null) | .name == $s and .key == $k)]
             | any)
    | .metadata.name'
}

# Patch one key of a k8s secret from a file; the value never touches argv.
patch_secret_from_file() {  # <kubectl-fn> <secret> <key> <value-file>
  local patch="$WORK/patch.json"
  jq -n --arg k "$3" --rawfile v "$4" '{stringData: {($k): ($v | rtrimstr("\n"))}}' > "$patch"
  "$1" patch secret "$2" --type merge --patch-file "$patch" >/dev/null
  rm -f "$patch"
}

# Restart each deployment named on stdin (one per line) and wait for it.
restart_all() {  # <kubectl-fn>
  local d n=0
  while read -r d; do
    [ -n "$d" ] || continue
    "$1" rollout restart "deploy/$d" >/dev/null
    "$1" rollout status "deploy/$d" --timeout=300s >/dev/null
    echo "  ✓ restarted $d"
    n=$((n + 1))
  done
  [ "$n" -gt 0 ] || echo "  - no deployment reads it"
}

preflight() {
  local c
  for c in aws jq kubectl shasum; do
    command -v "$c" >/dev/null || die "missing command: $c"
  done
  aws sts get-caller-identity >/dev/null 2>&1 || die "aws not authenticated"
  pk get "$BACKEND" >/dev/null 2>&1 || die "cannot reach $BACKEND in $PROD_CONTEXT/$PROD_NS"
  hk get secret "$WORKER_SECRET" >/dev/null 2>&1 || die "cannot read $WORKER_SECRET in $HOME_CONTEXT/$HOME_NS"
  hk get secret "$SCRAPER_SECRET" >/dev/null 2>&1 || die "cannot read $SCRAPER_SECRET in $HOME_CONTEXT/$HOME_NS"
}

report() {
  printf '  %-34s %s\n' "AWS $SECRET_ID" "$(aws_value | fp)"
  printf '  %-34s %s\n' "k8s $PROD_SECRET" "$(k8s_secret_value pk "$PROD_SECRET" "$PROD_KEY" | fp)"
  printf '  %-34s %s\n' "backend pod env" "$(pk exec "$BACKEND" -- printenv SERVICE_ACCOUNT_SECRET 2>/dev/null | fp)"
  printf '  %-34s %s\n' "worker $WORKER_SECRET" "$(k8s_secret_value hk "$WORKER_SECRET" "$WORKER_KEY" | fp)"
  printf '  %-34s %s\n' "backend/.env.prod" "$(local_value "$REPO_ROOT/backend/.env.prod" | fp)"
  printf '  %-34s %s\n' "backend/.env.dev" "$(local_value "$REPO_ROOT/backend/.env.dev" | fp)"
}

cmd_check() {
  local local_fp pod_fp
  local_fp="$(local_value "$REPO_ROOT/backend/.env.prod" | fp)"
  pod_fp="$(pk exec "$BACKEND" -- printenv SERVICE_ACCOUNT_SECRET | fp)"
  echo "backend/.env.prod  $local_fp"
  echo "prod backend pod   $pod_fp"
  if [ "$local_fp" = "$pod_fp" ]; then
    echo "→ SAME: a leak of the local file is a leak of prod. Run: $0 rotate"
  else
    echo "→ different: the local file does not hold prod's value"
  fi
}

cmd_verify() {
  preflight
  echo "SERVICE_ACCOUNT_SECRET fingerprints (want: AWS = k8s = pod = worker = .env.prod; .env.dev different):"
  report
}

cmd_rotate() {
  local yes="${1:-}"
  preflight

  step "current fingerprints"
  report

  cat <<EOF

This will:
  1. write a new $AWS_KEY to AWS $SECRET_ID ($REGION)
  2. force ESO to sync it into $PROD_CONTEXT/$PROD_NS $PROD_SECRET
  3. restart every prod deployment that reads it   ← old tokens and reset links die here
  4. mint a new match-scraper token in the pod; patch $HOME_CONTEXT/$HOME_NS $SCRAPER_SECRET
  5. patch $WORKER_SECRET; restart the home deployments that read either secret
  6. re-mint $EVAL_ACCOUNTS into $TOKEN_DIR
  7. rewrite backend/.env.prod (new value) and backend/.env.dev (its own value)
  8. delete the stale GitHub secret $GH_STALE (if present)
EOF
  if [ "$yes" != "--yes" ]; then
    [ -t 0 ] || die "needs a terminal to confirm (or pass --yes)"
    read -r -p "Type ROTATE to continue: " answer
    [ "$answer" = "ROTATE" ] || die "aborted"
  fi

  local new="$WORK/new"
  python3 -c 'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(48))' > "$new"
  chmod 600 "$new"
  local want
  want="$(fp < "$new")"
  echo "  new fingerprint: $want"

  step "1/8 AWS Secrets Manager"
  local blob="$WORK/blob.json"
  aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
    --query SecretString --output text |
    jq --arg k "$AWS_KEY" --rawfile v "$new" '. + {($k): $v}' > "$blob"
  aws secretsmanager put-secret-value --secret-id "$SECRET_ID" --region "$REGION" \
    --secret-string "file://$blob" >/dev/null
  rm -f "$blob"
  [ "$(aws_value | fp)" = "$want" ] || die "AWS readback does not match"
  echo "  ✓ $SECRET_ID.$AWS_KEY"

  step "2/8 ESO sync"
  pk annotate externalsecret missing-table-app-secrets "force-sync=$(date +%s)" --overwrite >/dev/null
  local i
  for i in $(seq 1 36); do
    [ "$(k8s_secret_value pk "$PROD_SECRET" "$PROD_KEY" | fp)" = "$want" ] && break
    [ "$i" = 36 ] && die "ESO did not sync within 3 minutes; check: kubectl -n $PROD_NS describe externalsecret missing-table-app-secrets"
    sleep 5
  done
  echo "  ✓ $PROD_SECRET synced"

  step "3/8 restart prod"
  deployments_using pk "$PROD_SECRET" "$PROD_KEY" | grep -qx "${BACKEND#deploy/}" ||
    die "${BACKEND#deploy/} does not read $PROD_SECRET.$PROD_KEY; refusing to guess"
  deployments_using pk "$PROD_SECRET" "$PROD_KEY" | restart_all pk
  [ "$(pk exec "$BACKEND" -- printenv SERVICE_ACCOUNT_SECRET | fp)" = "$want" ] || die "backend pod env does not match"
  echo "  ✓ backend runs the new secret"

  step "4/8 scraper token"
  local tok="$WORK/scraper.jwt"
  pk exec "$BACKEND" -- "$POD_PY" scripts/utilities/create_service_account_token.py \
    --service-name match-scraper --permissions manage_matches --output-file /dev/stdout > "$tok" ||
    die "scraper token mint failed in the pod (the script prints no reason); the backend already runs the new secret — re-run rotate"
  chmod 600 "$tok"
  [ "$(wc -c < "$tok")" -gt 100 ] || die "token mint produced $(wc -c < "$tok") bytes"
  patch_secret_from_file hk "$SCRAPER_SECRET" "$SCRAPER_KEY" "$tok"
  rm -f "$tok"
  echo "  ✓ $SCRAPER_SECRET.$SCRAPER_KEY"

  step "5/8 worker secret + home restarts"
  patch_secret_from_file hk "$WORKER_SECRET" "$WORKER_KEY" "$new"
  [ "$(k8s_secret_value hk "$WORKER_SECRET" "$WORKER_KEY" | fp)" = "$want" ] || die "worker secret readback does not match"
  echo "  ✓ $WORKER_SECRET.$WORKER_KEY"
  { deployments_using hk "$WORKER_SECRET" "$WORKER_KEY"
    deployments_using hk "$SCRAPER_SECRET" "$SCRAPER_KEY"; } | sort -u | restart_all hk
  echo "  (CronJobs pick the new token up on their next run)"

  step "6/8 MT AI eval tokens"
  mkdir -p "$TOKEN_DIR"
  local a out
  for a in $EVAL_ACCOUNTS; do
    out="$TOKEN_DIR/$a.prod.jwt"
    (umask 077; pk exec "$BACKEND" -- "$POD_PY" scripts/manage_ai_users.py token "$a" --out - > "$out") ||
      die "$a token mint failed (stderr above)"
    [ "$(wc -c < "$out")" -gt 100 ] || die "$a token mint produced $(wc -c < "$out") bytes"
    echo "  ✓ $out"
  done

  step "7/8 local env files"
  python3 - "$new" "$REPO_ROOT/backend/.env.prod" "$REPO_ROOT/backend/.env.dev" <<'EOF'
import re, secrets, sys
from pathlib import Path
new = Path(sys.argv[1]).read_text()
for path, value in ((sys.argv[2], new), (sys.argv[3], secrets.token_urlsafe(48))):
    p = Path(path)
    if not p.exists():
        print(f"  - {p.name} absent, skipped")
        continue
    text = p.read_text()
    line = "SERVICE_ACCOUNT_SECRET=" + value
    text, n = re.subn(r"(?m)^SERVICE_ACCOUNT_SECRET=.*$", lambda _: line, text)
    if n == 0:
        text = text.rstrip("\n") + "\n" + line + "\n"
    p.write_text(text)
    print(f"  ✓ {p.name}")
EOF

  step "8/8 stale GitHub secret"
  if ! command -v gh >/dev/null; then
    echo "  - gh not installed; delete $GH_STALE in $GH_REPO by hand"
  elif gh secret list -R "$GH_REPO" | awk '{print $1}' | grep -qx "$GH_STALE"; then
    gh secret delete "$GH_STALE" -R "$GH_REPO"
    echo "  ✓ deleted $GH_STALE"
  else
    echo "  - $GH_STALE not present"
  fi

  step "done — fingerprints"
  report
  cat <<EOF

Still to check by hand:
  - next scraper run ingests without 401s   (mt --env prod ingest failures)
  - a password reset completes end to end
EOF
}

case "${1:-}" in
  check) cmd_check ;;
  verify) cmd_verify ;;
  rotate) cmd_rotate "${2:-}" ;;
  *) sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
