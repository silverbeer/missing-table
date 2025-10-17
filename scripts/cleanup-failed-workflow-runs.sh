#!/bin/bash
# Cleanup Failed Workflow Runs
# This script deletes failed workflow runs to keep Actions tab clean

set -e

# Parse arguments
MODE="${1:-interactive}"
LIMIT="${2:-100}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 GitHub Actions Cleanup - Failed Workflow Runs${NC}"
echo "================================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed${NC}"
    echo "Install: brew install gh"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Show usage
if [ "$MODE" = "--help" ] || [ "$MODE" = "-h" ]; then
    echo "Usage: $0 [MODE] [LIMIT]"
    echo ""
    echo "Modes:"
    echo "  interactive  - Select which workflows to clean (default)"
    echo "  all          - Clean all failed runs"
    echo "  archived     - Clean only archived/old workflows"
    echo "  production   - Clean 'Deploy to Production' failures only"
    echo "  dev          - Clean 'Deploy to Dev' failures only"
    echo ""
    echo "Limit: Max number of runs to fetch (default: 100)"
    echo ""
    echo "Examples:"
    echo "  $0                      # Interactive mode"
    echo "  $0 all                  # Clean all failed runs"
    echo "  $0 production           # Clean production deployment failures"
    echo "  $0 all 200              # Clean all, fetch up to 200 runs"
    exit 0
fi

echo -e "${YELLOW}📊 Fetching failed workflow runs (limit: $LIMIT)...${NC}"
echo ""

# Get all failed runs
FAILED_RUNS_JSON=$(gh run list --status failure --limit "$LIMIT" --json databaseId,name,createdAt,workflowName)

# Define patterns
ARCHIVED_PATTERN="Secret Detection|API Contract Tests|GCP Deployment|ci-cd-pipeline|security-scan-scheduled|quality-gates-config|Performance Budget|Infrastructure Security"
PROD_PATTERN="Deploy to Production"
DEV_PATTERN="Deploy to Dev"

# Filter based on mode
case "$MODE" in
    all)
        echo -e "${YELLOW}Mode: Cleaning ALL failed runs${NC}"
        FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r '.[].databaseId')
        ;;
    archived)
        echo -e "${YELLOW}Mode: Cleaning archived workflows only${NC}"
        FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$ARCHIVED_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
        ;;
    production)
        echo -e "${YELLOW}Mode: Cleaning 'Deploy to Production' failures${NC}"
        FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$PROD_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
        ;;
    dev)
        echo -e "${YELLOW}Mode: Cleaning 'Deploy to Dev' failures${NC}"
        FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$DEV_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
        ;;
    interactive)
        echo -e "${YELLOW}Mode: Interactive - Choose workflows to clean${NC}"
        echo ""
        echo "Available workflows with failed runs:"
        echo ""

        # Get unique workflow names
        WORKFLOWS=$(echo "$FAILED_RUNS_JSON" | jq -r '.[].workflowName' | sort -u)

        # Count runs per workflow
        echo "$WORKFLOWS" | while read -r workflow; do
            COUNT=$(echo "$FAILED_RUNS_JSON" | jq -r --arg wf "$workflow" '[.[] | select(.workflowName == $wf)] | length')
            echo "  [$COUNT] $workflow"
        done

        echo ""
        echo "Select workflows to clean:"
        echo "  1) All workflows"
        echo "  2) Deploy to Production"
        echo "  3) Deploy to Dev"
        echo "  4) Archived workflows only"
        echo "  5) Custom (enter pattern)"
        echo ""
        read -p "Enter choice (1-5): " -r CHOICE

        case "$CHOICE" in
            1)
                FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r '.[].databaseId')
                ;;
            2)
                FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$PROD_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
                ;;
            3)
                FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$DEV_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
                ;;
            4)
                FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$ARCHIVED_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
                ;;
            5)
                echo ""
                read -p "Enter workflow name pattern (regex): " -r CUSTOM_PATTERN
                FAILED_RUNS=$(echo "$FAILED_RUNS_JSON" | jq -r --arg pattern "$CUSTOM_PATTERN" '.[] | select(.workflowName | test($pattern)) | .databaseId')
                ;;
            *)
                echo -e "${RED}Invalid choice${NC}"
                exit 1
                ;;
        esac
        ;;
    *)
        echo -e "${RED}❌ Invalid mode: $MODE${NC}"
        echo "Run with --help for usage"
        exit 1
        ;;
esac

TOTAL=$(echo "$FAILED_RUNS" | wc -l | tr -d ' ')

if [ "$TOTAL" -eq 0 ]; then
    echo -e "${GREEN}✅ No failed runs found matching criteria!${NC}"
    echo ""
    echo "Current workflow runs:"
    gh run list --limit 10
    exit 0
fi

echo ""
echo -e "${YELLOW}Found $TOTAL failed runs:${NC}"
echo ""
echo "$FAILED_RUNS_JSON" | jq -r --argjson ids "$(echo "$FAILED_RUNS" | jq -R . | jq -s .)" '.[] | select([.databaseId | tostring] | inside($ids)) | "\(.workflowName) - \(.createdAt)"' | head -20

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
