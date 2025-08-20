#!/bin/bash

# Comprehensive Terraform Security Scanning Script
# This script performs multi-layered security scanning of Terraform infrastructure

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}"
RESULTS_DIR="${SCRIPT_DIR}/security-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_PREFIX="security_scan_${TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install security tools if missing
install_security_tools() {
    log "Checking and installing security scanning tools..."
    
    # Install Checkov
    if ! command_exists checkov; then
        log "Installing Checkov..."
        pip3 install checkov
    fi
    
    # Install tfsec
    if ! command_exists tfsec; then
        log "Installing tfsec..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install tfsec
        else
            curl -s https://raw.githubusercontent.com/aquasecurity/tfsec/master/scripts/install_linux.sh | bash
        fi
    fi
    
    # Install Terrascan
    if ! command_exists terrascan; then
        log "Installing Terrascan..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install terrascan
        else
            curl -L "$(curl -s https://api.github.com/repos/tenable/terrascan/releases/latest | grep -o -E "https://.+?_Linux_x86_64.tar.gz")" > terrascan.tar.gz
            tar -xf terrascan.tar.gz terrascan && rm terrascan.tar.gz
            sudo mv terrascan /usr/local/bin
        fi
    fi
    
    # Install Trivy
    if ! command_exists trivy; then
        log "Installing Trivy..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install trivy
        else
            sudo apt-get update && sudo apt-get install wget apt-transport-https gnupg lsb-release
            wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
            echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
            sudo apt-get update && sudo apt-get install trivy
        fi
    fi
    
    success "Security tools installation completed"
}

# Function to run Terraform validation
terraform_validate() {
    log "Running Terraform validation..."
    
    cd "${TERRAFORM_DIR}"
    
    # Initialize Terraform
    if ! terraform init -backend=false -input=false; then
        error "Terraform initialization failed"
        return 1
    fi
    
    # Validate configuration
    if terraform validate; then
        success "Terraform validation passed"
        return 0
    else
        error "Terraform validation failed"
        return 1
    fi
}

# Function to run Terraform plan for security analysis
terraform_plan() {
    log "Generating Terraform plan for security analysis..."
    
    cd "${TERRAFORM_DIR}"
    
    local plan_file="${RESULTS_DIR}/terraform.plan"
    local plan_json="${RESULTS_DIR}/terraform_plan.json"
    
    # Generate plan
    if terraform plan -out="${plan_file}" -input=false; then
        # Convert plan to JSON for analysis
        terraform show -json "${plan_file}" > "${plan_json}"
        success "Terraform plan generated successfully"
        return 0
    else
        error "Terraform plan generation failed"
        return 1
    fi
}

# Function to run Checkov security scan
run_checkov() {
    log "Running Checkov security scan..."
    
    local checkov_results="${RESULTS_DIR}/${REPORT_PREFIX}_checkov"
    
    # Run Checkov with multiple output formats
    checkov \
        --directory "${TERRAFORM_DIR}" \
        --config-file "${TERRAFORM_DIR}/.checkov.yml" \
        --output cli \
        --output json \
        --output sarif \
        --output github_failed_only \
        --output-file-path "${checkov_results}" \
        --download-external-modules true \
        --external-checks-dir "${TERRAFORM_DIR}/security-policies" \
        --framework terraform \
        --framework terraform_plan || true
    
    # Check if any critical issues found
    if [[ -f "${checkov_results}_json.json" ]]; then
        local critical_count=$(jq '.summary.failed' "${checkov_results}_json.json" 2>/dev/null || echo "0")
        if [[ "${critical_count}" -gt 0 ]]; then
            warn "Checkov found ${critical_count} security issues"
        else
            success "Checkov scan completed with no critical issues"
        fi
    fi
}

# Function to run tfsec security scan
run_tfsec() {
    log "Running tfsec security scan..."
    
    local tfsec_results="${RESULTS_DIR}/${REPORT_PREFIX}_tfsec"
    
    # Run tfsec
    tfsec "${TERRAFORM_DIR}" \
        --format json \
        --out "${tfsec_results}.json" \
        --include-ignored \
        --exclude-downloaded-modules || true
    
    # Also generate readable report
    tfsec "${TERRAFORM_DIR}" \
        --format default \
        --out "${tfsec_results}.txt" \
        --include-ignored \
        --exclude-downloaded-modules || true
    
    # Check results
    if [[ -f "${tfsec_results}.json" ]]; then
        local issues_count=$(jq '.results | length' "${tfsec_results}.json" 2>/dev/null || echo "0")
        if [[ "${issues_count}" -gt 0 ]]; then
            warn "tfsec found ${issues_count} security issues"
        else
            success "tfsec scan completed with no issues"
        fi
    fi
}

# Function to run Terrascan security scan
run_terrascan() {
    log "Running Terrascan security scan..."
    
    local terrascan_results="${RESULTS_DIR}/${REPORT_PREFIX}_terrascan"
    
    # Run Terrascan
    terrascan scan \
        --iac-type terraform \
        --iac-dir "${TERRAFORM_DIR}" \
        --policy-type gcp \
        --output json \
        --output-file "${terrascan_results}.json" \
        --verbose || true
    
    # Generate human-readable report
    terrascan scan \
        --iac-type terraform \
        --iac-dir "${TERRAFORM_DIR}" \
        --policy-type gcp \
        --output human \
        --output-file "${terrascan_results}.txt" || true
    
    # Check results
    if [[ -f "${terrascan_results}.json" ]]; then
        local violations_count=$(jq '.results.violations | length' "${terrascan_results}.json" 2>/dev/null || echo "0")
        if [[ "${violations_count}" -gt 0 ]]; then
            warn "Terrascan found ${violations_count} policy violations"
        else
            success "Terrascan scan completed with no violations"
        fi
    fi
}

# Function to run Trivy security scan
run_trivy() {
    log "Running Trivy security scan..."
    
    local trivy_results="${RESULTS_DIR}/${REPORT_PREFIX}_trivy"
    
    # Scan for configuration issues
    trivy config \
        --format json \
        --output "${trivy_results}_config.json" \
        "${TERRAFORM_DIR}" || true
    
    # Generate human-readable config report
    trivy config \
        --format table \
        --output "${trivy_results}_config.txt" \
        "${TERRAFORM_DIR}" || true
    
    # If Dockerfile exists, scan it too
    if [[ -f "${TERRAFORM_DIR}/../Dockerfile" ]]; then
        trivy fs \
            --security-checks vuln,config \
            --format json \
            --output "${trivy_results}_dockerfile.json" \
            "${TERRAFORM_DIR}/../Dockerfile" || true
    fi
    
    success "Trivy scan completed"
}

# Function to run custom security policies
run_custom_policies() {
    log "Running custom security policies..."
    
    local custom_results="${RESULTS_DIR}/${REPORT_PREFIX}_custom_policies"
    
    # Run custom Checkov policies
    if [[ -f "${TERRAFORM_DIR}/security-policies/custom_gcp_policies.py" ]]; then
        python3 "${TERRAFORM_DIR}/security-policies/custom_gcp_policies.py" || true
    fi
    
    # Check for sensitive data in Terraform files
    log "Scanning for sensitive data patterns..."
    grep -r -i \
        -E "(password|secret|key|token|credential)" \
        "${TERRAFORM_DIR}" \
        --include="*.tf" \
        --include="*.tfvars" > "${custom_results}_sensitive.txt" || true
    
    # Check for hardcoded values that should be variables
    grep -r \
        -E "\"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\"" \
        "${TERRAFORM_DIR}" \
        --include="*.tf" > "${custom_results}_hardcoded_ips.txt" || true
    
    success "Custom security policies completed"
}

# Function to generate consolidated security report
generate_consolidated_report() {
    log "Generating consolidated security report..."
    
    local report_file="${RESULTS_DIR}/${REPORT_PREFIX}_consolidated_report.md"
    
    cat > "${report_file}" << EOF
# Infrastructure Security Scan Report

**Scan Date:** $(date)
**Terraform Directory:** ${TERRAFORM_DIR}
**Report ID:** ${REPORT_PREFIX}

## Executive Summary

This report provides a comprehensive security assessment of the Terraform infrastructure code.

## Scan Results Overview

### Tool Results

EOF

    # Add results from each tool
    for tool in checkov tfsec terrascan trivy; do
        echo "#### ${tool^}" >> "${report_file}"
        
        local tool_results="${RESULTS_DIR}/${REPORT_PREFIX}_${tool}"
        if [[ -f "${tool_results}.json" ]]; then
            echo "- JSON Report: \`${tool_results}.json\`" >> "${report_file}"
        fi
        if [[ -f "${tool_results}.txt" ]]; then
            echo "- Text Report: \`${tool_results}.txt\`" >> "${report_file}"
        fi
        echo "" >> "${report_file}"
    done
    
    cat >> "${report_file}" << EOF

### Compliance Status

- **CIS-GCP Benchmark**: See Checkov results
- **NIST 800-53**: See Checkov results
- **SOC 2**: See Checkov results
- **Custom Security Policies**: See custom policy results

### Recommended Actions

1. Review all CRITICAL and HIGH severity findings
2. Implement security controls for failed compliance checks
3. Update Terraform configurations to address security gaps
4. Re-run security scans after implementing fixes

### Files Scanned

\`\`\`
$(find "${TERRAFORM_DIR}" -name "*.tf" -type f | head -20)
\`\`\`

---
*Report generated by infrastructure security scanning pipeline*
EOF

    success "Consolidated report generated: ${report_file}"
}

# Function to check for drift using custom script
run_drift_detection() {
    log "Running infrastructure drift detection..."
    
    if [[ -f "${SCRIPT_DIR}/../drift-detection/drift-monitor.py" ]]; then
        export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-missing-table-dev}"
        export TERRAFORM_DIR="${TERRAFORM_DIR}"
        export ENVIRONMENT="${ENVIRONMENT:-development}"
        
        python3 "${SCRIPT_DIR}/../drift-detection/drift-monitor.py" || warn "Drift detection completed with warnings"
    else
        warn "Drift detection script not found"
    fi
}

# Function to validate security scan results
validate_security_results() {
    log "Validating security scan results..."
    
    local has_critical_issues=false
    
    # Check Checkov results for critical issues
    local checkov_json="${RESULTS_DIR}/${REPORT_PREFIX}_checkov_json.json"
    if [[ -f "${checkov_json}" ]]; then
        local failed_checks=$(jq '.summary.failed' "${checkov_json}" 2>/dev/null || echo "0")
        if [[ "${failed_checks}" -gt 0 ]]; then
            error "Checkov found ${failed_checks} failed security checks"
            has_critical_issues=true
        fi
    fi
    
    # Check tfsec results
    local tfsec_json="${RESULTS_DIR}/${REPORT_PREFIX}_tfsec.json"
    if [[ -f "${tfsec_json}" ]]; then
        local tfsec_issues=$(jq '.results | length' "${tfsec_json}" 2>/dev/null || echo "0")
        if [[ "${tfsec_issues}" -gt 0 ]]; then
            error "tfsec found ${tfsec_issues} security issues"
            has_critical_issues=true
        fi
    fi
    
    if [[ "${has_critical_issues}" == "true" ]]; then
        error "Security scan completed with critical issues. Review the reports before proceeding."
        return 1
    else
        success "Security validation passed"
        return 0
    fi
}

# Function to send notifications
send_notifications() {
    log "Sending security scan notifications..."
    
    # Slack notification (if webhook configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local message="Infrastructure security scan completed for ${TERRAFORM_DIR}. Report: ${REPORT_PREFIX}"
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"${message}\"}" \
            "${SLACK_WEBHOOK_URL}" || warn "Failed to send Slack notification"
    fi
    
    # Email notification could be added here
    # GitHub issue creation could be added here
    
    success "Notifications sent"
}

# Main execution function
main() {
    log "Starting comprehensive Terraform security scan..."
    log "Scan ID: ${REPORT_PREFIX}"
    log "Terraform Directory: ${TERRAFORM_DIR}"
    log "Results Directory: ${RESULTS_DIR}"
    
    # Install required tools
    install_security_tools
    
    # Run Terraform validation
    if ! terraform_validate; then
        error "Terraform validation failed. Fix syntax errors before security scanning."
        exit 1
    fi
    
    # Generate Terraform plan
    terraform_plan
    
    # Run security scans
    run_checkov
    run_tfsec
    run_terrascan
    run_trivy
    run_custom_policies
    
    # Run drift detection
    run_drift_detection
    
    # Generate consolidated report
    generate_consolidated_report
    
    # Validate results and determine exit code
    if validate_security_results; then
        success "Security scan completed successfully"
        send_notifications
        exit 0
    else
        error "Security scan completed with critical issues"
        send_notifications
        exit 1
    fi
}

# Script usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Comprehensive Terraform security scanning script for Missing Table infrastructure.

OPTIONS:
    -h, --help              Show this help message
    -d, --directory DIR     Terraform directory (default: current directory)
    -o, --output DIR        Output directory for results (default: ./security-results)
    --skip-tools-install    Skip automatic tool installation
    --drift-only            Run only drift detection
    --validate-only         Run only Terraform validation

ENVIRONMENT VARIABLES:
    GOOGLE_CLOUD_PROJECT    GCP project ID for drift detection
    ENVIRONMENT            Environment name (development, staging, production)
    SLACK_WEBHOOK_URL      Slack webhook for notifications

EXAMPLES:
    $0                                          # Run full security scan
    $0 -d /path/to/terraform                   # Scan specific directory
    $0 --drift-only                           # Run only drift detection
    $0 --validate-only                        # Run only validation

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -d|--directory)
            TERRAFORM_DIR="$2"
            shift 2
            ;;
        -o|--output)
            RESULTS_DIR="$2"
            shift 2
            ;;
        --skip-tools-install)
            SKIP_TOOLS_INSTALL=true
            shift
            ;;
        --drift-only)
            DRIFT_ONLY=true
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Execute based on flags
if [[ "${VALIDATE_ONLY:-false}" == "true" ]]; then
    terraform_validate
elif [[ "${DRIFT_ONLY:-false}" == "true" ]]; then
    run_drift_detection
else
    main
fi