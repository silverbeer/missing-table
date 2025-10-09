# 🧹 Cleanup Failed Workflow Runs

> **Date**: 2025-10-08
> **Purpose**: Clean up failed workflow runs from archived workflows to keep repository tidy

---

## 📊 Current State

### Failed Runs Summary
Based on analysis of the last 100 workflow runs:

| Workflow | Failed Runs |
|----------|-------------|
| Secret Detection | 15 |
| .github/workflows/security-scan-scheduled.yml | 14 |
| .github/workflows/ci-cd-pipeline.yml | 14 |
| API Contract Tests | 11 |
| .github/workflows/quality-gates-config.yml | 11 |
| GCP Deployment with Security Scanning | 7 |
| Security Scanning | 4 |
| Performance Budget Validation | 1 |
| Infrastructure Security Scanning | 1 |
| **TOTAL** | **78** |

### Current Active Workflow
- ✅ **Security Scanning** - All recent runs successful
- This is the only workflow that should be running

---

## 🎯 Why Clean Up?

1. **Public Repository**: Want clean workflow history for visitors
2. **Historical Failures**: All failures are from archived workflows
3. **Misleading Metrics**: 78 failed runs make the repo look unstable
4. **Fresh Start**: Now that workflows are fixed, clean slate is appropriate

---

## 🔧 How to Clean Up

### Option 1: Automated Script (Recommended)

We've provided a script to automate the cleanup:

```bash
# Run the cleanup script
./scripts/cleanup-failed-workflow-runs.sh
```

**What it does**:
- Finds all failed runs from archived workflows
- Shows you the count
- Asks for confirmation before deleting
- Deletes each run with rate limiting
- Shows remaining runs when complete

**Requirements**:
- GitHub CLI (`gh`) installed and authenticated
- Repository write permissions
- Owner or admin access to delete runs

### Option 2: Manual Deletion via GitHub UI

If you prefer the UI or don't have permissions for bulk delete:

1. Go to **Actions** tab: https://github.com/silverbeer/missing-table/actions
2. Click on a failed workflow run
3. Click the **...** menu (top right)
4. Select **Delete workflow run**
5. Repeat for each failed run

**Tip**: Filter by workflow name to delete in batches:
- Click workflow name in left sidebar
- Delete all runs for that workflow
- Move to next workflow

### Option 3: GitHub API (Advanced)

Delete individual runs via API:

```bash
# Get run ID
gh run list --status failure --limit 1 --json databaseId,name

# Delete specific run
gh api -X DELETE "repos/silverbeer/missing-table/actions/runs/<RUN_ID>"
```

---

## 📋 Cleanup Checklist

- [ ] **Backup**: Ensure all workflows are properly archived
- [ ] **Documentation**: Verify workflow-audit.md is complete
- [ ] **Confirm**: Only delete runs from archived workflows
- [ ] **Run Script**: Execute cleanup script or manual deletion
- [ ] **Verify**: Check Actions tab shows clean history
- [ ] **Monitor**: Ensure Security Scanning workflow continues to pass

---

## ⚠️ Important Notes

### What to DELETE ✅
Failed runs from these archived workflows:
- ❌ Secret Detection
- ❌ API Contract Tests
- ❌ GCP Deployment with Security Scanning
- ❌ ci-cd-pipeline.yml
- ❌ security-scan-scheduled.yml
- ❌ quality-gates-config.yml
- ❌ Performance Budget Validation
- ❌ Infrastructure Security Scanning

### What to KEEP ✅
- ✅ **Security Scanning** - Active workflow (keep all runs)
- ✅ Any other successful runs

---

## 🔮 After Cleanup

### Expected State
- **Actions tab**: Clean history with only Security Scanning runs
- **Failed runs**: 0 (or minimal from recent testing)
- **Success rate**: ~100% visible
- **Public view**: Professional, maintained repository

### Ongoing Maintenance
- Security Scanning will continue to run daily
- Failed runs should be rare (only real issues)
- Archive grows as workflows are properly documented
- No need for regular cleanup with only 1 active workflow

---

## 📊 Verification

After cleanup, verify with:

```bash
# Check for remaining failed runs
gh run list --status failure --limit 20

# Check successful runs
gh run list --status success --limit 20

# View Actions tab
open https://github.com/silverbeer/missing-table/actions
```

**Expected results**:
- Few or no failed runs listed
- Mostly Security Scanning successful runs
- Clean, professional Actions tab

---

## 🔗 Related Documentation

- **[Workflow Audit](workflow-audit.md)** - Complete workflow analysis
- **[Phase 2 Complete](workflow-phase2-complete.md)** - Simplification summary
- **[Archive README](../../.github/workflows/archive/README.md)** - Archived workflows

---

<div align="center">

**Status**: Ready for cleanup
**Impact**: Purely cosmetic - improves repository presentation

[⬆ Back to CI/CD Documentation](README.md)

</div>
