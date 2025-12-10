#!/bin/bash
set -e

# Security scanning script using Trivy
# This script performs comprehensive security scanning of containers, filesystem, and configurations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
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

# Check if Trivy is installed
check_trivy() {
    if ! command -v trivy &> /dev/null; then
        error "Trivy is not installed. Installing..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install aquasecurity/trivy/trivy
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin
        else
            error "Please install Trivy manually: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
            exit 1
        fi
    fi
    success "Trivy is available"
}

# Scan Docker images
scan_images() {
    log "Scanning Docker images for vulnerabilities..."

    # Build images first using build-and-push.sh (local mode, no push)
    cd "${PROJECT_ROOT}"
    ./build-and-push.sh all local

    # Define image names (matches build-and-push.sh local tags)
    BACKEND_IMAGE="us-central1-docker.pkg.dev/missing-table/missing-table/backend:local"
    FRONTEND_IMAGE="us-central1-docker.pkg.dev/missing-table/missing-table/frontend:local"

    log "Scanning backend image: $BACKEND_IMAGE"
    trivy image \
        --config "${SECURITY_DIR}/trivy-config.yaml" \
        --output "${RESULTS_DIR}/backend-image-scan.sarif" \
        --format sarif \
        --severity CRITICAL,HIGH,MEDIUM \
        "$BACKEND_IMAGE" || warn "Backend image scan failed or not found"

    # Also generate human-readable report
    trivy image \
        --format table \
        --output "${RESULTS_DIR}/backend-image-scan.txt" \
        --severity CRITICAL,HIGH,MEDIUM \
        "$BACKEND_IMAGE" || true

    log "Scanning frontend image: $FRONTEND_IMAGE"
    trivy image \
        --config "${SECURITY_DIR}/trivy-config.yaml" \
        --output "${RESULTS_DIR}/frontend-image-scan.sarif" \
        --format sarif \
        --severity CRITICAL,HIGH,MEDIUM \
        "$FRONTEND_IMAGE" || warn "Frontend image scan failed or not found"

    # Also generate human-readable report
    trivy image \
        --format table \
        --output "${RESULTS_DIR}/frontend-image-scan.txt" \
        --severity CRITICAL,HIGH,MEDIUM \
        "$FRONTEND_IMAGE" || true
}

# Scan filesystem for vulnerabilities and secrets
scan_filesystem() {
    log "Scanning filesystem for vulnerabilities and secrets..."
    
    # Vulnerability scan
    trivy fs \
        --config "${SECURITY_DIR}/trivy-config.yaml" \
        --output "${RESULTS_DIR}/filesystem-vuln-scan.sarif" \
        --format sarif \
        --severity CRITICAL,HIGH,MEDIUM \
        "${PROJECT_ROOT}"
    
    # Human-readable vulnerability report
    trivy fs \
        --format table \
        --output "${RESULTS_DIR}/filesystem-vuln-scan.txt" \
        --severity CRITICAL,HIGH,MEDIUM \
        "${PROJECT_ROOT}"
    
    # Secret scan
    trivy fs \
        --scanners secret \
        --format table \
        --output "${RESULTS_DIR}/filesystem-secret-scan.txt" \
        "${PROJECT_ROOT}"
}

# Scan configuration files
scan_configs() {
    log "Scanning configuration files..."

    # Scan Dockerfiles
    find "${PROJECT_ROOT}" -name "Dockerfile" -type f | while read dockerfile; do
        dirname=$(basename "$(dirname "$dockerfile")")
        trivy config \
            --format table \
            --output "${RESULTS_DIR}/${dirname}-Dockerfile-scan.txt" \
            "$dockerfile"
    done

    # Scan Helm charts
    if [ -d "${PROJECT_ROOT}/helm" ]; then
        trivy config \
            --format table \
            --output "${RESULTS_DIR}/helm-scan.txt" \
            "${PROJECT_ROOT}/helm"
    fi

    # Scan Terraform files if they exist
    if [ -d "${PROJECT_ROOT}/terraform" ]; then
        trivy config \
            --format table \
            --output "${RESULTS_DIR}/terraform-scan.txt" \
            "${PROJECT_ROOT}/terraform"
    fi
}

# Generate summary report
generate_summary() {
    log "Generating security scan summary..."
    
    SUMMARY_FILE="${RESULTS_DIR}/security-summary.md"
    
    cat > "$SUMMARY_FILE" << EOF
# Security Scan Summary

Generated on: $(date)

## Scan Results

### Docker Images
EOF

    if [ -f "${RESULTS_DIR}/backend-image-scan.txt" ]; then
        echo "- ✅ Backend image scanned" >> "$SUMMARY_FILE"
    fi
    
    if [ -f "${RESULTS_DIR}/frontend-image-scan.txt" ]; then
        echo "- ✅ Frontend image scanned" >> "$SUMMARY_FILE"
    fi

    cat >> "$SUMMARY_FILE" << EOF

### Filesystem Scans
- ✅ Vulnerability scan completed
- ✅ Secret scan completed

### Configuration Scans
- ✅ Dockerfile scans completed
- ✅ Helm chart scans completed
EOF

    if [ -f "${RESULTS_DIR}/terraform-scan.txt" ]; then
        echo "- ✅ Terraform scan completed" >> "$SUMMARY_FILE"
    fi

    cat >> "$SUMMARY_FILE" << EOF

## Critical Issues

Check individual scan results in the \`security/results/\` directory for detailed findings.

### Files Scanned
- Docker images: Backend, Frontend
- Source code: Full repository
- Configurations: Dockerfiles, Helm charts, Terraform

### Next Steps
1. Review all CRITICAL and HIGH severity findings
2. Update vulnerable dependencies
3. Fix configuration issues
4. Implement security best practices
5. Re-run scans after fixes

EOF

    success "Summary report generated at: $SUMMARY_FILE"
}

# Main execution
main() {
    log "Starting comprehensive security scan..."
    
    check_trivy
    scan_images
    scan_filesystem
    scan_configs
    generate_summary
    
    success "Security scan completed! Check results in: ${RESULTS_DIR}"
    
    # Quick stats
    echo ""
    log "Quick Statistics:"
    echo "📁 Results directory: ${RESULTS_DIR}"
    echo "📄 Files generated: $(ls -1 "${RESULTS_DIR}" | wc -l)"
    echo "📊 Summary report: ${RESULTS_DIR}/security-summary.md"
}

# Run with error handling
if ! main "$@"; then
    error "Security scan failed!"
    exit 1
fi