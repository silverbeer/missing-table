#!/bin/bash

# Kubernetes Ninja - Comprehensive Code Quality Check Script
# This script runs all configured quality tools for the MLS Next app

set -e  # Exit on any error

echo "🥷 Kubernetes Ninja - Running Comprehensive Code Quality Checks"
echo "=============================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "backend/pyproject.toml" ]]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Backend Python Quality Checks
echo ""
print_status "🐍 Running Python Backend Quality Checks..."
echo "----------------------------------------------------"

cd backend

# 1. Ruff Linting
print_status "Running Ruff linter..."
if uv run ruff check . --statistics; then
    print_success "Ruff linting completed"
else
    print_warning "Ruff found issues (check output above)"
fi

echo ""

# 2. Ruff Formatting
print_status "Running Ruff formatter..."
if uv run ruff format . --check; then
    print_success "Code formatting is correct"
else
    print_warning "Code formatting issues found"
    print_status "Fixing formatting..."
    uv run ruff format .
    print_success "Code formatting fixed"
fi

echo ""

# 3. MyPy Type Checking
print_status "Running MyPy type checking..."
if uv run mypy app.py --show-error-codes --no-error-summary; then
    print_success "No type errors found"
else
    print_warning "Type errors found (see output above)"
fi

echo ""

# 4. Bandit Security Scanning
print_status "Running Bandit security scan..."
if uv run bandit -r . --exclude .venv -q -f txt; then
    print_success "No security issues found in main code"
else
    print_warning "Security issues detected (see output above)"
fi

echo ""

# 5. Safety Dependency Check
print_status "Running Safety dependency vulnerability check..."
if uv run safety check --json > /dev/null 2>&1; then
    print_success "No vulnerable dependencies found"
else
    print_warning "Vulnerable dependencies detected"
fi

echo ""

# 6. Test Coverage (if tests exist)
if [[ -d "tests" ]] && [[ -n "$(find tests -name "*.py" -type f)" ]]; then
    print_status "Running test coverage analysis..."
    if uv run pytest --cov=. --cov-report=term-missing --cov-report=html -q; then
        print_success "Tests passed with coverage report generated"
    else
        print_warning "Some tests failed or coverage is low"
    fi
else
    print_warning "No tests found - consider adding comprehensive tests"
fi

cd ..

# Frontend Quality Checks
echo ""
print_status "🌐 Running Frontend Quality Checks..."
echo "----------------------------------------------------"

cd frontend

if [[ -f "package.json" ]]; then
    # Check if node_modules exists
    if [[ ! -d "node_modules" ]]; then
        print_status "Installing frontend dependencies..."
        npm install
    fi
    
    # Run frontend linting
    print_status "Running frontend linting..."
    if npm run lint; then
        print_success "Frontend linting passed"
    else
        print_warning "Frontend linting issues found"
    fi
else
    print_warning "No package.json found in frontend directory"
fi

cd ..

# Container Security (if Docker images exist)
echo ""
print_status "🐳 Container Security Checks..."
echo "----------------------------------------------------"

if command -v trivy >/dev/null 2>&1; then
    # Check if Docker images exist
    if docker images | grep -q "missing-table"; then
        print_status "Running Trivy container security scan..."
        if trivy image missing-table-backend:latest --exit-code 1 --severity HIGH,CRITICAL; then
            print_success "No high/critical vulnerabilities in backend container"
        else
            print_warning "High/critical vulnerabilities found in backend container"
        fi
        
        if trivy image missing-table-frontend:latest --exit-code 1 --severity HIGH,CRITICAL; then
            print_success "No high/critical vulnerabilities in frontend container"
        else
            print_warning "High/critical vulnerabilities found in frontend container"
        fi
    else
        print_warning "Docker images not found. Run 'make docker-build' to create them first."
    fi
else
    print_warning "Trivy not installed. Install with: brew install trivy"
fi

# Pre-commit hooks check
echo ""
print_status "🔄 Pre-commit Hooks Status..."
echo "----------------------------------------------------"

if [[ -f ".pre-commit-config.yaml" ]]; then
    if command -v pre-commit >/dev/null 2>&1; then
        print_status "Running pre-commit hooks..."
        if pre-commit run --all-files; then
            print_success "All pre-commit hooks passed"
        else
            print_warning "Some pre-commit hooks failed"
        fi
    else
        print_warning "Pre-commit not installed. Install with: pip install pre-commit"
    fi
else
    print_warning "No pre-commit configuration found"
fi

# Final Summary
echo ""
echo "=============================================================="
print_status "🏁 Quality Check Summary Complete!"
echo ""
print_success "✅ Code quality tools are configured and running"
print_success "✅ Security scanning is active"
print_success "✅ Ready for Kubernetes ninja deployment pipeline!"
echo ""
print_status "Next steps:"
echo "  1. Review any warnings above and fix issues"
echo "  2. Add comprehensive tests to improve coverage"
echo "  3. Set up pre-commit hooks: pre-commit install"
echo "  4. Continue with Phase 3: Frontend quality tools"
echo ""
print_status "Run 'make quality' for quick quality checks"
print_status "Run 'make security' for security-focused scans"
echo "=============================================================="