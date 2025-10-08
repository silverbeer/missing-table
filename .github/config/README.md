# GitHub Actions Configuration Files

This directory contains configuration files used by GitHub Actions workflows.

## Files

### quality-gates-config.yml

**Purpose**: Defines quality thresholds and requirements for the CI/CD pipeline

**What it contains**:
- Code quality requirements (linting, type checking, formatting)
- Security scanning thresholds (vulnerability limits)
- Testing requirements (coverage minimums)
- Infrastructure requirements (security policies)
- Performance requirements (Lighthouse scores, load testing)
- Deployment requirements (strategies, monitoring)
- Notification settings
- Compliance and audit requirements

**Used by**:
- `ci-cd-pipeline.yml` - Main CI/CD workflow (when functional)
- Future workflows that need quality gate definitions

**How to use**:
Workflows can reference this configuration file to determine quality thresholds:

```yaml
# Example: Read thresholds from config
- name: Load quality gates config
  run: |
    MIN_COVERAGE=$(yq '.testing.coverage.backend.minimum_line_coverage' .github/config/quality-gates-config.yml)
    echo "Minimum coverage: $MIN_COVERAGE%"
```

**Modifying thresholds**:
1. Edit `quality-gates-config.yml`
2. Commit and push changes
3. Workflows will use new thresholds on next run

**Note**: This is a configuration file, not a workflow. It should never be placed in `.github/workflows/` as GitHub Actions will try to run it as a workflow.

---

## Adding New Configuration Files

When adding new configuration files:
1. Place them in this directory
2. Use descriptive names (e.g., `lighthouse-budgets.yml`, `security-policies.yml`)
3. Add documentation to this README
4. Reference from workflows using relative paths: `.github/config/filename.yml`
