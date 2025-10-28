#!/bin/bash
# Deployment Health Check Script
# Verifies deployment health across different environments
# Usage: ./scripts/deployment-health-check.sh [environment] [namespace]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-dev}"
NAMESPACE="${2:-missing-table-dev}"
TIMEOUT=300  # 5 minutes

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Deployment Health Check - ${ENVIRONMENT}${NC}"
echo -e "${BLUE}  Namespace: ${NAMESPACE}${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ Error: kubectl not found${NC}"
    echo "Please install kubectl to run health checks"
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo -e "${RED}❌ Error: Namespace '${NAMESPACE}' not found${NC}"
    exit 1
fi

# Function to check pod status
check_pods() {
    echo -e "${BLUE}📦 Checking Pod Status...${NC}"

    # Get all pods in namespace
    PODS=$(kubectl get pods -n "${NAMESPACE}" -o json)

    # Check for CrashLoopBackOff
    CRASH_PODS=$(echo "${PODS}" | jq -r '.items[] | select(.status.phase != "Succeeded") | select(.status.containerStatuses[]? | .state.waiting?.reason == "CrashLoopBackOff") | .metadata.name' 2>/dev/null)

    if [ -n "${CRASH_PODS}" ]; then
        echo -e "${RED}❌ Pods in CrashLoopBackOff:${NC}"
        echo "${CRASH_PODS}"
        return 1
    fi

    # Check for pods not ready
    NOT_READY=$(echo "${PODS}" | jq -r '.items[] | select(.status.phase == "Running") | select(.status.containerStatuses[]? | .ready == false) | .metadata.name' 2>/dev/null)

    if [ -n "${NOT_READY}" ]; then
        echo -e "${YELLOW}⚠️  Pods not ready:${NC}"
        echo "${NOT_READY}"
        echo -e "${YELLOW}Waiting for pods to become ready...${NC}"

        # Wait for pods to be ready
        for pod in ${NOT_READY}; do
            if ! kubectl wait --for=condition=ready pod/"${pod}" -n "${NAMESPACE}" --timeout="${TIMEOUT}s" 2>/dev/null; then
                echo -e "${RED}❌ Pod ${pod} did not become ready within ${TIMEOUT}s${NC}"
                return 1
            fi
        done
    fi

    # Show final pod status
    echo -e "${GREEN}✅ All pods running and ready${NC}"
    kubectl get pods -n "${NAMESPACE}" -o wide
    echo ""
    return 0
}

# Function to check deployments
check_deployments() {
    echo -e "${BLUE}🚀 Checking Deployment Status...${NC}"

    DEPLOYMENTS=$(kubectl get deployments -n "${NAMESPACE}" -o json)

    # Check for failed deployments
    FAILED=$(echo "${DEPLOYMENTS}" | jq -r '.items[] | select(.status.conditions[]? | select(.type == "Progressing" and .status == "False")) | .metadata.name' 2>/dev/null)

    if [ -n "${FAILED}" ]; then
        echo -e "${RED}❌ Failed deployments:${NC}"
        echo "${FAILED}"
        return 1
    fi

    # Check for deployments with unavailable replicas
    UNAVAILABLE=$(echo "${DEPLOYMENTS}" | jq -r '.items[] | select(.status.unavailableReplicas > 0) | .metadata.name' 2>/dev/null)

    if [ -n "${UNAVAILABLE}" ]; then
        echo -e "${YELLOW}⚠️  Deployments with unavailable replicas:${NC}"
        echo "${UNAVAILABLE}"
        return 1
    fi

    echo -e "${GREEN}✅ All deployments healthy${NC}"
    kubectl get deployments -n "${NAMESPACE}"
    echo ""
    return 0
}

# Function to check Helm release status
check_helm_release() {
    echo -e "${BLUE}⎈ Checking Helm Release...${NC}"

    if ! command -v helm &> /dev/null; then
        echo -e "${YELLOW}⚠️  Helm not found, skipping Helm checks${NC}"
        echo ""
        return 0
    fi

    # Get latest Helm release
    RELEASE_STATUS=$(helm list -n "${NAMESPACE}" -o json 2>/dev/null)

    if [ -z "${RELEASE_STATUS}" ] || [ "${RELEASE_STATUS}" == "[]" ]; then
        echo -e "${YELLOW}⚠️  No Helm releases found in namespace${NC}"
        echo ""
        return 0
    fi

    # Check for failed releases
    FAILED_RELEASES=$(echo "${RELEASE_STATUS}" | jq -r '.[] | select(.status != "deployed") | .name + " (" + .status + ")"' 2>/dev/null)

    if [ -n "${FAILED_RELEASES}" ]; then
        echo -e "${RED}❌ Failed Helm releases:${NC}"
        echo "${FAILED_RELEASES}"
        return 1
    fi

    echo -e "${GREEN}✅ Helm release deployed successfully${NC}"
    helm list -n "${NAMESPACE}"
    echo ""
    return 0
}

# Function to check Ingress status
check_ingress() {
    echo -e "${BLUE}🌐 Checking Ingress Status...${NC}"

    INGRESS=$(kubectl get ingress -n "${NAMESPACE}" -o json 2>/dev/null)

    if [ -z "${INGRESS}" ] || [ "$(echo "${INGRESS}" | jq '.items | length')" == "0" ]; then
        echo -e "${YELLOW}⚠️  No Ingress resources found${NC}"
        echo ""
        return 0
    fi

    # Check for Ingress without address
    NO_ADDRESS=$(echo "${INGRESS}" | jq -r '.items[] | select(.status.loadBalancer.ingress == null) | .metadata.name' 2>/dev/null)

    if [ -n "${NO_ADDRESS}" ]; then
        echo -e "${YELLOW}⚠️  Ingress without address (may be syncing):${NC}"
        echo "${NO_ADDRESS}"
        echo ""
    fi

    echo -e "${GREEN}✅ Ingress status:${NC}"
    kubectl get ingress -n "${NAMESPACE}"
    echo ""
    return 0
}

# Function to check service endpoints
check_services() {
    echo -e "${BLUE}🔌 Checking Service Endpoints...${NC}"

    SERVICES=$(kubectl get services -n "${NAMESPACE}" -o json)

    # Check for services without endpoints
    NO_ENDPOINTS=$(echo "${SERVICES}" | jq -r '.items[] | select(.spec.type != "ExternalName") | .metadata.name' 2>/dev/null | while read -r svc; do
        ENDPOINTS=$(kubectl get endpoints "${svc}" -n "${NAMESPACE}" -o json 2>/dev/null)
        if [ "$(echo "${ENDPOINTS}" | jq '.subsets | length')" == "0" ] || [ "$(echo "${ENDPOINTS}" | jq '.subsets')" == "null" ]; then
            echo "${svc}"
        fi
    done)

    if [ -n "${NO_ENDPOINTS}" ]; then
        echo -e "${YELLOW}⚠️  Services without endpoints:${NC}"
        echo "${NO_ENDPOINTS}"
        echo ""
    fi

    echo -e "${GREEN}✅ Service status:${NC}"
    kubectl get services -n "${NAMESPACE}"
    echo ""
    return 0
}

# Function to check recent events
check_events() {
    echo -e "${BLUE}📋 Checking Recent Events...${NC}"

    # Get warning events from last 10 minutes
    WARNING_EVENTS=$(kubectl get events -n "${NAMESPACE}" --field-selector type=Warning --sort-by='.lastTimestamp' 2>/dev/null | tail -n 20)

    if [ -n "${WARNING_EVENTS}" ] && [ "$(echo "${WARNING_EVENTS}" | wc -l)" -gt 1 ]; then
        echo -e "${YELLOW}⚠️  Recent warning events:${NC}"
        echo "${WARNING_EVENTS}"
        echo ""
    else
        echo -e "${GREEN}✅ No recent warning events${NC}"
        echo ""
    fi

    return 0
}

# Function to test HTTP endpoints
check_http_endpoints() {
    echo -e "${BLUE}🌍 Checking HTTP Endpoints...${NC}"

    case "${ENVIRONMENT}" in
        dev)
            URL="https://dev.missingtable.com"
            ;;
        prod)
            URL="https://missingtable.com"
            ;;
        *)
            echo -e "${YELLOW}⚠️  Unknown environment, skipping HTTP checks${NC}"
            echo ""
            return 0
            ;;
    esac

    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        echo -e "${YELLOW}⚠️  curl not found, skipping HTTP checks${NC}"
        echo ""
        return 0
    fi

    # Test main URL
    echo "Testing ${URL}..."
    if HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${URL}" --max-time 10); then
        if [ "${HTTP_CODE}" == "200" ]; then
            echo -e "${GREEN}✅ ${URL}: HTTP ${HTTP_CODE}${NC}"
        else
            echo -e "${YELLOW}⚠️  ${URL}: HTTP ${HTTP_CODE}${NC}"
        fi
    else
        echo -e "${RED}❌ ${URL}: Connection failed${NC}"
    fi

    # Test API health endpoint
    echo "Testing ${URL}/api/health..."
    if HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${URL}/api/health" --max-time 10); then
        if [ "${HTTP_CODE}" == "200" ]; then
            echo -e "${GREEN}✅ ${URL}/api/health: HTTP ${HTTP_CODE}${NC}"
        else
            echo -e "${YELLOW}⚠️  ${URL}/api/health: HTTP ${HTTP_CODE}${NC}"
        fi
    else
        echo -e "${RED}❌ ${URL}/api/health: Connection failed${NC}"
    fi

    echo ""
    return 0
}

# Function to check resource usage
check_resources() {
    echo -e "${BLUE}💻 Checking Resource Usage...${NC}"

    # Get pod metrics if metrics-server is available
    if kubectl top pods -n "${NAMESPACE}" &> /dev/null; then
        echo "Pod resource usage:"
        kubectl top pods -n "${NAMESPACE}"
        echo ""
    else
        echo -e "${YELLOW}⚠️  Metrics server not available, skipping resource checks${NC}"
        echo ""
    fi

    return 0
}

# Main health check execution
main() {
    local exit_code=0

    # Run all checks
    check_pods || exit_code=1
    check_deployments || exit_code=1
    check_helm_release || exit_code=1
    check_ingress || exit_code=1
    check_services || exit_code=1
    check_events || exit_code=1
    check_http_endpoints || exit_code=1
    check_resources || exit_code=1

    # Final summary
    echo -e "${BLUE}================================================${NC}"
    if [ ${exit_code} -eq 0 ]; then
        echo -e "${GREEN}✅ Deployment Health Check: PASSED${NC}"
        echo -e "${GREEN}All systems operational in ${ENVIRONMENT} environment${NC}"
    else
        echo -e "${RED}❌ Deployment Health Check: FAILED${NC}"
        echo -e "${RED}Issues detected in ${ENVIRONMENT} environment${NC}"
    fi
    echo -e "${BLUE}================================================${NC}"

    exit ${exit_code}
}

# Run main function
main
