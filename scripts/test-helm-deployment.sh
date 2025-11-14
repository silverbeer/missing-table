#!/bin/bash
# Test Helm deployment without waiting for GitHub Actions
# Usage: ./scripts/test-helm-deployment.sh [dev|prod|local]

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CHART_DIR="./helm/missing-table"
NAMESPACE=""
VALUES_FILE=""
CONTEXT=""
ENV="${1:-dev}"

# Set environment-specific values
case "$ENV" in
  prod)
    echo -e "${YELLOW}⚠️  Note: 'prod' now deploys to missing-table-dev (consolidated environment)${NC}"
    NAMESPACE="missing-table-dev"
    VALUES_FILE="$CHART_DIR/values-dev.yaml"
    CONTEXT="gke_missing-table_us-central1_missing-table-dev"
    ;;
  dev)
    NAMESPACE="missing-table-dev"
    VALUES_FILE="$CHART_DIR/values-dev.yaml"
    CONTEXT="gke_missing-table_us-central1_missing-table-dev"
    ;;
  local)
    NAMESPACE="missing-table"
    VALUES_FILE="$CHART_DIR/values.yaml"
    CONTEXT="rancher-desktop"
    ;;
  *)
    echo -e "${RED}Error: Invalid environment '$ENV'. Use: dev, prod, or local${NC}"
    exit 1
    ;;
esac

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Testing Helm Deployment for $ENV${NC}"
echo -e "${BLUE}======================================${NC}\n"

# Step 1: Lint
echo -e "${YELLOW}Step 1: Linting Helm chart...${NC}"
if helm lint "$CHART_DIR"; then
  echo -e "${GREEN}✓ Lint passed${NC}\n"
else
  echo -e "${RED}✗ Lint failed${NC}"
  exit 1
fi

# Step 2: Template rendering
echo -e "${YELLOW}Step 2: Rendering templates...${NC}"
TEMP_FILE=$(mktemp)
if helm template missing-table "$CHART_DIR" \
  --values "$VALUES_FILE" \
  --namespace "$NAMESPACE" > "$TEMP_FILE" 2>&1; then
  echo -e "${GREEN}✓ Templates rendered successfully${NC}"
  echo -e "${BLUE}Template output saved to: $TEMP_FILE${NC}\n"
else
  echo -e "${RED}✗ Template rendering failed${NC}"
  cat "$TEMP_FILE"
  rm "$TEMP_FILE"
  exit 1
fi

# Step 3: Check values file
echo -e "${YELLOW}Step 3: Checking values file...${NC}"
if [[ ! -f "$VALUES_FILE" ]]; then
  echo -e "${RED}✗ Values file not found: $VALUES_FILE${NC}"
  echo -e "${YELLOW}Hint: Copy from example file:${NC}"
  echo -e "  cp $VALUES_FILE.example $VALUES_FILE"
  exit 1
fi
echo -e "${GREEN}✓ Values file exists${NC}\n"

# Step 4: Validate against Kubernetes (if context available)
if kubectl config get-contexts "$CONTEXT" &> /dev/null; then
  echo -e "${YELLOW}Step 4: Validating against Kubernetes ($CONTEXT)...${NC}"

  # Switch context
  kubectl config use-context "$CONTEXT" &> /dev/null

  # Dry-run
  if helm upgrade missing-table "$CHART_DIR" \
    --install \
    --namespace "$NAMESPACE" \
    --values "$VALUES_FILE" \
    --dry-run --debug 2>&1 | head -n 50; then
    echo -e "${GREEN}✓ Kubernetes validation passed${NC}\n"
  else
    echo -e "${RED}✗ Kubernetes validation failed${NC}"
    exit 1
  fi
else
  echo -e "${YELLOW}Step 4: Skipping Kubernetes validation (context not available)${NC}\n"
fi

# Summary
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}All tests passed! ✓${NC}"
echo -e "${BLUE}======================================${NC}\n"

echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Review rendered template: ${BLUE}less $TEMP_FILE${NC}"
echo -e "2. Deploy to $ENV cluster:"
if [[ "$ENV" == "local" ]]; then
  echo -e "   ${BLUE}helm upgrade missing-table $CHART_DIR \\${NC}"
  echo -e "   ${BLUE}  --install --namespace $NAMESPACE \\${NC}"
  echo -e "   ${BLUE}  --values $VALUES_FILE --wait${NC}"
else
  echo -e "   ${BLUE}Push to GitHub to trigger deployment workflow${NC}"
fi
echo -e "3. Manual deploy (if needed):"
echo -e "   ${BLUE}kubectl config use-context $CONTEXT${NC}"
echo -e "   ${BLUE}helm upgrade missing-table $CHART_DIR \\${NC}"
echo -e "   ${BLUE}  --install --namespace $NAMESPACE \\${NC}"
echo -e "   ${BLUE}  --values $VALUES_FILE --wait${NC}"

echo -e "\n${YELLOW}Template output location: $TEMP_FILE${NC}"
echo -e "${YELLOW}(File will be deleted when you close terminal)${NC}\n"
