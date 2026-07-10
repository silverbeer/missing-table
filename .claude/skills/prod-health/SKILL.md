---
name: prod-health
description: One-shot production health check for missingtable.com — pods, ArgoCD sync, endpoints, version/image drift, TLS expiry, DB connectivity. Use when the user asks "is prod healthy", "prod status", after a deploy, or when investigating an incident.
allowed-tools: Bash
---

# MT Production Health Check

Run ALL checks below (they are independent — run in parallel where possible),
then emit the traffic-light report. Do not stop at the first failure; the value
is the complete picture.

Production runs on LKE (kube context `lke560651-ctx`, namespace
`missing-table`), deployed by ArgoCD watching `helm/missing-table/values-prod.yaml`.

**All commands here are read-only.** Never restart, delete, or patch anything
from this skill. If a check fails, report it and suggest the fix — the user
decides whether to act.

Note: a Claude Code hook rewrites bare `kubectl` to `rtk kubectl`, which
rejects `--context`. Always invoke as `command kubectl`.

## Checks

### 1. Pods

```bash
command kubectl --context lke560651-ctx get pods -n missing-table
```

Healthy = every pod `1/1 Running`. Flag: restarts > 0 in last 24h (check
`kubectl get pods` RESTARTS + AGE), Pending/CrashLoopBackOff/Evicted.

### 2. ArgoCD sync

```bash
command kubectl --context lke560651-ctx get application -n argocd missing-table \
  -o jsonpath='{.status.sync.status} {.status.health.status} {.status.sync.revision}'
```

Healthy = `Synced Healthy`. If `OutOfSync` or `Degraded`, get detail with
`-o jsonpath='{.status.conditions}'` and suggest the hard-refresh annotation
(in CLAUDE.md / cppp skill) — do not apply it yourself.

### 3. Public endpoints

```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}s" --max-time 10 https://missingtable.com
curl -s -o /dev/null -w "%{http_code} %{time_total}s" --max-time 10 https://www.missingtable.com
curl -s --max-time 10 https://api.missingtable.com/health
curl -s --max-time 10 https://api.missingtable.com/health/full
```

Healthy = 200s, `/health/full` reports every sub-check healthy (includes DB
connectivity — this is the Supabase probe). Flag response time > 2s.

### 4. Version / image drift

```bash
curl -s --max-time 10 https://api.missingtable.com/api/version
command grep -A1 "backend:\|frontend:" helm/missing-table/values-prod.yaml | command grep "tag:"
command kubectl --context lke560651-ctx get pods -n missing-table \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
```

Healthy = the `commit_sha` from `/api/version` matches the image tag in
`values-prod.yaml` AND the running pod images. Mismatch = deploy in flight or
stuck — cross-check with ArgoCD status. Also report `version` + `build_id` so
the user knows what's live. (Run the grep/kubectl from the repo root on the
latest `main` — `git fetch origin main -q` first if the working tree is on a
branch, and read the file from `origin/main` with `git show origin/main:helm/missing-table/values-prod.yaml`.)

### 5. TLS certificate expiry

```bash
for h in missingtable.com api.missingtable.com; do
  echo -n "$h: "
  echo | openssl s_client -connect $h:443 -servername $h 2>/dev/null \
    | openssl x509 -noout -enddate
done
```

Healthy = > 21 days out. Warn ≤ 21, red ≤ 7 (cert-manager should renew ~30
days out; anything inside 21 means renewal is failing).

### 6. Recent pod events (only if something above is off)

```bash
command kubectl --context lke560651-ctx get events -n missing-table \
  --sort-by=.lastTimestamp | tail -15
```

## Report format

Emit exactly this shape (keep it scannable):

```
## MT Prod Health — <YYYY-MM-DD HH:MM local>

| Check       | Status | Detail                                  |
|-------------|--------|-----------------------------------------|
| Pods        | 🟢/🟡/🔴 | 3/3 Running, 0 restarts                |
| ArgoCD      | 🟢/🟡/🔴 | Synced + Healthy @ <short-sha>         |
| Frontend    | 🟢/🟡/🔴 | 200 in 0.1s (www + apex)               |
| Backend API | 🟢/🟡/🔴 | /health/full all healthy               |
| Version     | 🟢/🟡/🔴 | v1.10.5.1176 · sha 6b4c294 · no drift  |
| TLS         | 🟢/🟡/🔴 | expires <date> (<N> days)              |

**Verdict:** <one sentence — "all green" or the single most important problem
and the suggested next command>.
```

🟡 = degraded but serving (slow, restarts, cert < 21d, sync in progress).
🔴 = user-visible breakage or imminent failure.

If anything is 🔴, append a short "Suggested next steps" list (commands only,
do not run mutating commands).
