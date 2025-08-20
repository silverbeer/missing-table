#!/bin/bash
set -e

# Terraform Security Scanning Script
# This script performs comprehensive security scanning of Terraform infrastructure code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"
SECURITY_DIR="${PROJECT_ROOT}/security"
RESULTS_DIR="${SECURITY_DIR}/results"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Check if required tools are installed
check_tools() {
    local tools=("terraform" "checkov" "terrascan" "tfsec" "trivy")
    local missing_tools=()
    
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        error "Missing required tools: ${missing_tools[*]}"
        echo "Please install the missing tools:"
        echo "  - Terraform: https://www.terraform.io/downloads.html"
        echo "  - Checkov: pip install checkov"
        echo "  - Terrascan: https://runterrascan.io/docs/getting-started/"
        echo "  - TFSec: https://aquasecurity.github.io/tfsec/latest/guides/installation/"
        echo "  - Trivy: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        exit 1
    fi
    
    success "All required tools are installed"
}

# Initialize Terraform
init_terraform() {
    log "Initializing Terraform..."
    cd "${TERRAFORM_DIR}"
    
    # Skip backend initialization for security scanning
    terraform init -backend=false
    
    success "Terraform initialized"
}

# Validate Terraform configuration
validate_terraform() {
    log "Validating Terraform configuration..."
    cd "${TERRAFORM_DIR}"
    
    if terraform validate; then
        success "Terraform configuration is valid"
    else
        error "Terraform configuration is invalid"
        return 1
    fi
}

# Format check Terraform code
format_check_terraform() {
    log "Checking Terraform formatting..."
    cd "${TERRAFORM_DIR}"
    
    if terraform fmt -check -recursive; then
        success "Terraform code is properly formatted"
    else
        warn "Terraform code formatting issues found. Run 'terraform fmt -recursive' to fix."
    fi
}

# Run Checkov scan
run_checkov() {
    log "Running Checkov security scan..."
    cd "${PROJECT_ROOT}"
    
    checkov \
        --config-file "${SECURITY_DIR}/terraform/checkov-config.yaml" \
        --directory "${TERRAFORM_DIR}" \
        --output sarif \
        --output-file-path "${RESULTS_DIR}/terraform-checkov-results.sarif" \
        --compact \
        --quiet
    
    # Also generate human-readable report
    checkov \
        --directory "${TERRAFORM_DIR}" \
        --output cli \
        --compact > "${RESULTS_DIR}/terraform-checkov-results.txt" || true
    
    success "Checkov scan completed"
}

# Run Terrascan
run_terrascan() {
    log "Running Terrascan security scan..."
    cd "${TERRAFORM_DIR}"
    
    terrascan scan \
        --config-path "${SECURITY_DIR}/terraform/terrascan-config.toml" \
        --iac-type terraform \
        --output sarif \
        --output-file "${RESULTS_DIR}/terraform-terrascan-results.sarif" \
        .
    
    # Also generate human-readable report
    terrascan scan \
        --iac-type terraform \
        --output human \
        . > "${RESULTS_DIR}/terraform-terrascan-results.txt" || true
    
    success "Terrascan scan completed"
}

# Run TFSec scan
run_tfsec() {
    log "Running TFSec security scan..."
    cd "${TERRAFORM_DIR}"
    
    tfsec \
        --format sarif \
        --out "${RESULTS_DIR}/terraform-tfsec-results.sarif" \
        .
    
    # Also generate human-readable report
    tfsec \
        --format default \
        . > "${RESULTS_DIR}/terraform-tfsec-results.txt" || true
    
    success "TFSec scan completed"
}

# Run Trivy configuration scan
run_trivy_config() {
    log "Running Trivy configuration scan..."
    cd "${PROJECT_ROOT}"
    
    trivy config \
        --format sarif \
        --output "${RESULTS_DIR}/terraform-trivy-results.sarif" \
        --severity CRITICAL,HIGH,MEDIUM \
        "${TERRAFORM_DIR}"
    
    # Also generate human-readable report
    trivy config \
        --format table \
        --output "${RESULTS_DIR}/terraform-trivy-results.txt" \
        --severity CRITICAL,HIGH,MEDIUM \
        "${TERRAFORM_DIR}"
    
    success "Trivy configuration scan completed"
}

# Generate Terraform plan for analysis
generate_plan() {
    log "Generating Terraform plan for analysis..."
    cd "${TERRAFORM_DIR}"
    
    # Create a plan file for advanced scanning
    terraform plan \
        -out="${RESULTS_DIR}/terraform.tfplan" \
        -var-file="terraform.tfvars.example" \
        -input=false
    
    # Convert plan to JSON for analysis
    terraform show \
        -json "${RESULTS_DIR}/terraform.tfplan" > "${RESULTS_DIR}/terraform-plan.json"
    
    success "Terraform plan generated"
}

# Scan Terraform plan with Checkov
scan_plan_checkov() {
    log "Scanning Terraform plan with Checkov..."
    cd "${PROJECT_ROOT}"
    
    if [ -f "${RESULTS_DIR}/terraform.tfplan" ]; then
        checkov \
            --file "${RESULTS_DIR}/terraform.tfplan" \
            --output sarif \
            --output-file-path "${RESULTS_DIR}/terraform-plan-checkov-results.sarif" \
            --compact
        
        success "Terraform plan scan with Checkov completed"
    else
        warn "Terraform plan not found, skipping plan scan"
    fi
}

# Generate comprehensive security report
generate_security_report() {
    log "Generating comprehensive security report..."
    
    REPORT_FILE="${RESULTS_DIR}/terraform-security-report.md"
    
    cat > "$REPORT_FILE" << EOF
# Terraform Security Scan Report

Generated on: $(date)

## Executive Summary

This report contains the results of comprehensive security scanning of the Missing Table application's Terraform infrastructure code.

## Scans Performed

### 1. Checkov
- **Purpose**: Policy as Code security scanning
- **Results**: See \`terraform-checkov-results.sarif\` and \`terraform-checkov-results.txt\`

### 2. Terrascan
- **Purpose**: Infrastructure as Code security validation
- **Results**: See \`terraform-terrascan-results.sarif\` and \`terraform-terrascan-results.txt\`

### 3. TFSec
- **Purpose**: Terraform static analysis
- **Results**: See \`terraform-tfsec-results.sarif\` and \`terraform-tfsec-results.txt\`

### 4. Trivy
- **Purpose**: Configuration vulnerability scanning
- **Results**: See \`terraform-trivy-results.sarif\` and \`terraform-trivy-results.txt\`

## Security Findings Summary

EOF

    # Count findings from SARIF files
    if command -v jq &> /dev/null; then
        for tool in checkov terrascan tfsec trivy; do
            sarif_file="${RESULTS_DIR}/terraform-${tool}-results.sarif"
            if [ -f "$sarif_file" ]; then
                critical=$(jq '.runs[0].results | map(select(.level == "error")) | length' "$sarif_file" 2>/dev/null || echo "0")
                warning=$(jq '.runs[0].results | map(select(.level == "warning")) | length' "$sarif_file" 2>/dev/null || echo "0")
                echo "### $tool" >> "$REPORT_FILE"
                echo "- Critical/High: $critical" >> "$REPORT_FILE"
                echo "- Medium/Warning: $warning" >> "$REPORT_FILE"
                echo "" >> "$REPORT_FILE"
            fi
        done
    fi

    cat >> "$REPORT_FILE" << EOF
## Remediation Recommendations

1. **Review Critical Issues**: Address all critical and high-severity findings immediately
2. **Implement Security Best Practices**: Follow AWS security best practices
3. **Enable Encryption**: Ensure all data is encrypted at rest and in transit
4. **Network Security**: Implement proper network segmentation and security groups
5. **Access Control**: Use least privilege principle for IAM policies
6. **Monitoring**: Enable logging and monitoring for all resources

## Files Generated

- \`terraform-checkov-results.sarif\` - Checkov SARIF results
- \`terraform-checkov-results.txt\` - Checkov human-readable results
- \`terraform-terrascan-results.sarif\` - Terrascan SARIF results
- \`terraform-terrascan-results.txt\` - Terrascan human-readable results
- \`terraform-tfsec-results.sarif\` - TFSec SARIF results
- \`terraform-tfsec-results.txt\` - TFSec human-readable results
- \`terraform-trivy-results.sarif\` - Trivy SARIF results
- \`terraform-trivy-results.txt\` - Trivy human-readable results
- \`terraform-plan.json\` - Terraform plan in JSON format
- \`terraform-plan-checkov-results.sarif\` - Checkov plan scan results

## Next Steps

1. Import SARIF results into your IDE or security dashboard
2. Prioritize fixes based on severity and business impact
3. Implement security controls in infrastructure code
4. Set up automated security scanning in CI/CD pipeline
5. Regular security reviews and updates

EOF

    success "Comprehensive security report generated at: $REPORT_FILE"
}

# Main execution
main() {
    log "Starting Terraform security scanning..."
    
    check_tools
    init_terraform
    validate_terraform
    format_check_terraform
    
    # Run all security scans
    run_checkov
    run_terrascan
    run_tfsec
    run_trivy_config
    
    # Generate and scan plan if possible
    if [ -f "${TERRAFORM_DIR}/terraform.tfvars.example" ]; then
        generate_plan
        scan_plan_checkov
    else
        warn "terraform.tfvars.example not found, skipping plan generation"
    fi
    
    generate_security_report
    
    success "Terraform security scanning completed!"
    
    # Summary
    echo ""
    log "Scan Summary:"
    echo "📁 Results directory: ${RESULTS_DIR}"
    echo "📄 Files generated: $(ls -1 "${RESULTS_DIR}" | grep terraform | wc -l)"
    echo "📊 Security report: ${RESULTS_DIR}/terraform-security-report.md"
    echo ""
    echo "Next steps:"
    echo "1. Review the security report"
    echo "2. Address critical and high-severity findings"
    echo "3. Import SARIF files into your security dashboard"
}

# Run with error handling
if ! main "$@"; then
    error "Terraform security scan failed!"
    exit 1
fi