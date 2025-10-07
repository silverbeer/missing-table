#!/bin/bash
# Install git hooks for API contract testing

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOK_DIR="$REPO_ROOT/.git/hooks"

echo "📝 Installing API contract testing hooks..."

# Create pre-commit hook
cat > "$HOOK_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Pre-commit hook for API contract testing

set -e

# Check if backend files changed
if git diff --cached --name-only | grep -q "^backend/"; then
    echo "🔍 Backend files changed, checking API contract coverage..."

    cd backend

    # Export latest OpenAPI schema
    echo "📋 Exporting OpenAPI schema..."
    uv run python scripts/export_openapi.py

    # Check coverage (warning only, don't fail)
    echo "📊 Checking API test coverage..."
    if ! uv run python scripts/check_api_coverage.py --threshold 70; then
        echo "⚠️  Warning: API test coverage is below 70%"
        echo "   Consider adding contract tests for new endpoints"
        echo ""
        read -p "Continue with commit? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    cd ..
fi

echo "✅ Pre-commit checks passed"
EOF

chmod +x "$HOOK_DIR/pre-commit"

echo "✅ Hooks installed successfully!"
echo ""
echo "Installed hooks:"
echo "  - pre-commit: Checks API contract coverage"
echo ""
echo "To skip hooks, use: git commit --no-verify"
