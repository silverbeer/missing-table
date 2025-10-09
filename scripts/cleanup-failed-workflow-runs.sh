#!/bin/bash
# Cleanup Failed Workflow Runs from Archived Workflows
# This script deletes failed runs from workflows that have been archived

set -e

echo "🧹 GitHub Actions Cleanup - Failed Workflow Runs"
echo "================================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed"
    echo "Install: brew install gh"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI"
    echo "Run: gh auth login"
    exit 1
fi

echo "📊 Fetching failed workflow runs..."
echo ""

# Get all failed runs (limit to 100 due to API)
FAILED_RUNS_JSON=$(gh run list --status failure --limit 100 --json databaseId,name,createdAt,workflowName)

# Filter only archived workflows
ARCHIVED_PATTERN="Secret Detection|API Contract Tests|GCP Deployment|ci-cd-pipeline|security-scan-scheduled|quality-gates-config|Performance Budget|Infrastructure Security"

FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$ARCHIVED_PATTERN" '.[] | select(.name | test($pattern)) | .databaseId')

TOTAL=$(echo "$FAILED_RUNS" | wc -l | tr -d ' ')

if [ "$TOTAL" -eq 0 ]; then
    echo "✅ No failed runs from archived workflows found!"
    echo ""
    echo "Current workflow runs:"
    gh run list --limit 10
    exit 0
fi

echo "Found $TOTAL failed runs from archived workflows:"
echo ""
echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$ARCHIVED_PATTERN" '.[] | select(.name | test($pattern)) | "\(.name) - \(.createdAt)"' | head -20

if [ "$TOTAL" -gt 20 ]; then
    echo "... and $((TOTAL - 20)) more"
fi

echo ""
echo "⚠️  This will DELETE these workflow runs permanently!"
echo ""
read -p "Continue with deletion? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "🗑️  Deleting failed runs..."
echo "---"

CURRENT=0
FAILED_COUNT=0

# Delete each run
for run_id in $FAILED_RUNS; do
    CURRENT=$((CURRENT + 1))
    printf "[$CURRENT/$TOTAL] Deleting run $run_id... "

    if gh api -X DELETE "repos/:owner/:repo/actions/runs/$run_id" 2>/dev/null; then
        echo "✅"
    else
        echo "❌ (permission denied or already deleted)"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi

    # Rate limiting - small delay between deletions
    sleep 0.3
done

echo "---"
echo ""

DELETED=$((TOTAL - FAILED_COUNT))
echo "✅ Cleanup complete!"
echo "   Deleted: $DELETED runs"
if [ $FAILED_COUNT -gt 0 ]; then
    echo "   Failed: $FAILED_COUNT runs"
fi
echo ""

echo "📊 Remaining workflow runs:"
echo ""
gh run list --limit 10

echo ""
echo "🎉 Repository Actions tab should now be clean!"
echo "   View at: https://github.com/silverbeer/missing-table/actions"
