---
name: commit-pr
description: Create commits and PRs with GitOps deployment awareness. Use when committing code or creating pull requests.
allowed-tools: Bash, Read, Grep
---

Follows the standard cppp commit/PR workflow. Additionally, be aware of the Missing Table deployment pipeline below.

## Missing Table Deployment Pipeline

**Merging a PR to main triggers automatic deployment — no manual steps needed:**

1. GitHub Actions builds Docker images → pushes to GHCR (~2 min)
2. GHA updates `helm/missing-table/values-prod.yaml` with new image tags
3. Argo CD detects helm changes → syncs to production cluster (~1-2 min)

**Never run `./build-and-push.sh` after merging** — that is for local dev only.

## Verify deployment

```bash
kubectl get pods -n missing-table
kubectl get applications -n argocd missing-table
```

## Force Argo CD refresh if deployment stalls

```bash
kubectl -n argocd patch application missing-table --type=merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

## Check current image versions

```bash
kubectl get pods -n missing-table \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
```
