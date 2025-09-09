# Frontend Quality Tools Setup

This document describes the quality tools configured for the frontend to ensure code consistency and catch issues early.

## Tools Installed

### ESLint

- **Version**: ^8.57.1
- **Configuration**: Vue 3 + Prettier integration
- **Purpose**: Linting JavaScript and Vue files for syntax errors and code quality issues

### Prettier

- **Version**: ^3.6.2
- **Purpose**: Code formatting for consistent style across all files
- **Configuration**: `.prettierrc.json` with Vue-friendly settings

### Husky

- **Version**: ^9.1.7
- **Purpose**: Git hooks management
- **Setup**: Pre-commit hook to run quality checks

### lint-staged

- **Version**: ^15.5.2
- **Purpose**: Run linters only on staged files for faster commits

## Available Scripts

```bash
# Linting
npm run lint          # Check for ESLint errors
npm run lint:fix      # Fix auto-fixable ESLint errors

# Formatting
npm run format        # Format all files with Prettier
npm run format:check  # Check if files are properly formatted
```

## Pre-commit Hooks

When you commit changes, the following quality checks run automatically:

1. **ESLint with auto-fix** - Fixes auto-fixable issues and validates code quality
2. **Prettier formatting** - Ensures consistent code formatting

Files that fail these checks will prevent the commit until fixed.

## Configuration Files

- `.prettierrc.json` - Prettier formatting rules
- `.prettierignore` - Files/directories to exclude from formatting
- `package.json` - ESLint configuration in `eslintConfig` section
- `.husky/pre-commit` - Git pre-commit hook script

## Quality Standards

The setup enforces:

- Vue 3 best practices and syntax
- Consistent code formatting (2-space indentation, single quotes, etc.)
- No unused variables or unreachable code
- Proper semicolon usage
- Consistent trailing commas

## Troubleshooting

If quality checks fail:

1. Run `npm run lint:fix` to auto-fix ESLint issues
2. Run `npm run format` to fix formatting issues
3. Manual fixes may be needed for complex ESLint errors

To temporarily bypass hooks (not recommended):

```bash
git commit --no-verify -m "message"
```
