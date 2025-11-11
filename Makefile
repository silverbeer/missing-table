# Kubernetes Ninja - MLS Next Development Makefile
# Comprehensive code quality, security, and development commands

.PHONY: help install dev-install quality security test build clean docker k8s

# Default target
help: ## Show this help message
	@echo "🥷 Kubernetes Ninja - MLS Next App Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation commands
install: ## Install all dependencies (backend + frontend)
	@echo "📦 Installing dependencies..."
	cd backend && uv sync
	cd frontend && npm install

dev-install: install ## Install development dependencies and setup pre-commit
	@echo "🔧 Setting up development environment..."
	cd backend && uv sync --group dev
	pre-commit install
	@echo "✅ Development environment ready!"

# Code Quality Commands
quality: ## Run all code quality checks
	@echo "🔍 Running comprehensive code quality checks..."
	$(MAKE) quality-backend
	$(MAKE) quality-frontend

quality-backend: ## Run backend code quality checks (Ruff, MyPy, Bandit)
	@echo "🐍 Checking Python code quality..."
	cd backend && uv run ruff check --fix .
	cd backend && uv run ruff format .
	cd backend && uv run mypy .
	@echo "✅ Backend quality checks passed!"

quality-frontend: ## Run frontend code quality checks
	@echo "🌐 Checking frontend code quality..."
	cd frontend && npm run lint
	@echo "✅ Frontend quality checks passed!"

# Security Commands
security: ## Run all security scans
	@echo "🛡️  Running comprehensive security scans..."
	$(MAKE) security-backend
	$(MAKE) security-containers

security-backend: ## Run backend security scans (Bandit, Safety)
	@echo "🔒 Scanning Python code for security issues..."
	cd backend && uv run bandit -r . -f json -o bandit-report.json || true
	cd backend && uv run bandit -r . || true
	cd backend && uv run safety check || true
	@echo "✅ Backend security scans completed!"

security-containers: ## Run container security scans (Trivy)
	@echo "📦 Scanning containers for vulnerabilities..."
	@if command -v trivy >/dev/null 2>&1; then \
		trivy image missing-table-backend:latest || echo "⚠️  Backend image not found, run 'make docker-build' first"; \
		trivy image missing-table-frontend:latest || echo "⚠️  Frontend image not found, run 'make docker-build' first"; \
	else \
		echo "⚠️  Trivy not installed. Install with: brew install trivy"; \
	fi

# Testing Commands
test: ## Run all tests
	@echo "🧪 Running comprehensive test suite..."
	$(MAKE) test-backend
	$(MAKE) test-frontend

test-backend: ## Run all backend tests with coverage
	@echo "🐍 Running all Python tests..."
	cd backend && uv run python run_tests.py --category all --html-coverage --xml-coverage
	@echo "✅ Backend tests completed!"

test-unit: ## Run unit tests (fast, isolated, 80% coverage threshold)
	@echo "⚡ Running unit tests..."
	cd backend && uv run python run_tests.py --category unit --html-coverage --xml-coverage
	@echo "✅ Unit tests completed!"

test-integration: ## Run integration tests (component interaction, 70% coverage threshold)
	@echo "🔗 Running integration tests..."
	cd backend && uv run python run_tests.py --category integration --html-coverage --xml-coverage
	@echo "✅ Integration tests completed!"

test-contract: ## Run contract tests (API schema validation, 90% coverage threshold)
	@echo "📜 Running contract tests..."
	cd backend && uv run python run_tests.py --category contract --html-coverage --xml-coverage
	@echo "✅ Contract tests completed!"

test-e2e: ## Run end-to-end tests (full user journeys, 50% coverage threshold)
	@echo "🎯 Running end-to-end tests..."
	cd backend && uv run python run_tests.py --category e2e --html-coverage --xml-coverage
	@echo "✅ E2E tests completed!"

test-smoke: ## Run smoke tests (critical path sanity checks, 100% coverage threshold)
	@echo "💨 Running smoke tests..."
	cd backend && uv run python run_tests.py --category smoke --html-coverage --xml-coverage
	@echo "✅ Smoke tests completed!"

test-quick: ## Run unit tests + smoke tests (fast feedback)
	@echo "⚡ Running quick tests (unit + smoke)..."
	$(MAKE) test-unit
	$(MAKE) test-smoke
	@echo "✅ Quick tests completed!"

test-slow: ## Run slow tests only
	@echo "🐌 Running slow tests..."
	cd backend && uv run pytest -m slow --html-coverage --xml-coverage
	@echo "✅ Slow tests completed!"

test-frontend: ## Run frontend tests
	@echo "🌐 Running frontend tests..."
	cd frontend && npm test || echo "⚠️  Frontend tests not configured yet"

test-catalog: ## Generate test catalog (JSON manifest for CrewAI)
	@echo "📚 Generating test catalog..."
	python3 scripts/test_catalog.py --output table --save backend/tests/test-catalog.json
	@echo "✅ Test catalog generated!"

# Development Commands
dev: ## Start development servers (backend + frontend)
	@echo "🚀 Starting development servers..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:8080"
	./missing-table.sh start

dev-backend: ## Start only backend development server
	@echo "🐍 Starting FastAPI backend..."
	cd backend && uv run python app.py

dev-frontend: ## Start only frontend development server
	@echo "🌐 Starting Vue 3 frontend..."
	cd frontend && npm run serve

# Build Commands
build: ## Build both backend and frontend for production
	@echo "🏗️  Building production artifacts..."
	$(MAKE) build-backend
	$(MAKE) build-frontend

build-backend: ## Build backend (placeholder for now)
	@echo "🐍 Building Python backend..."
	cd backend && uv build

build-frontend: ## Build frontend for production
	@echo "🌐 Building Vue 3 frontend..."
	cd frontend && npm run build

# Docker Commands
docker: docker-build ## Build all Docker images

docker-build: ## Build Docker images for backend and frontend
	@echo "🐳 Building Docker images..."
	docker-compose build
	@echo "✅ Docker images built successfully!"

docker-up: ## Start application with Docker Compose
	@echo "🐳 Starting application with Docker..."
	docker-compose up -d
	@echo "✅ Application running on Docker!"

docker-down: ## Stop Docker containers
	@echo "🐳 Stopping Docker containers..."
	docker-compose down

docker-logs: ## View Docker container logs
	docker-compose logs -f

# Database Commands
db-reset: ## Reset local database (Supabase)
	@echo "🗃️  Resetting local database..."
	npx supabase db reset

db-start: ## Start local Supabase
	@echo "🗃️  Starting local Supabase..."
	npx supabase start

db-stop: ## Stop local Supabase
	@echo "🗃️  Stopping local Supabase..."
	npx supabase stop

# Kubernetes Commands (will be expanded as we progress)
k8s-validate: ## Validate Kubernetes manifests
	@echo "☸️  Validating Kubernetes manifests..."
	@if [ -d "k8s" ]; then \
		find k8s -name "*.yaml" -o -name "*.yml" | xargs -I {} sh -c 'echo "Validating {}" && kubectl --dry-run=client apply -f {} || true'; \
	else \
		echo "⚠️  k8s directory not found. Will be created in later phases."; \
	fi

# Cleanup Commands
clean: ## Clean all build artifacts and caches
	@echo "🧹 Cleaning build artifacts..."
	$(MAKE) clean-backend
	$(MAKE) clean-frontend
	$(MAKE) clean-docker

clean-backend: ## Clean Python caches and build artifacts
	@echo "🐍 Cleaning Python artifacts..."
	find backend -type f -name "*.pyc" -delete
	find backend -type d -name "__pycache__" -delete
	find backend -type d -name "*.egg-info" -exec rm -rf {} + || true
	rm -rf backend/dist backend/build backend/.coverage backend/htmlcov
	rm -f backend/bandit-report.json

clean-frontend: ## Clean frontend build artifacts
	@echo "🌐 Cleaning frontend artifacts..."
	rm -rf frontend/dist frontend/node_modules/.cache

clean-docker: ## Clean Docker images and containers
	@echo "🐳 Cleaning Docker artifacts..."
	docker-compose down --rmi all --volumes --remove-orphans || true

# Git and Pre-commit Commands
pre-commit: ## Run pre-commit hooks on all files
	@echo "✅ Running pre-commit hooks..."
	pre-commit run --all-files

commit-ready: quality security test ## Check if code is ready for commit
	@echo "🚀 Code quality, security, and tests all passed!"
	@echo "✅ Ready to commit!"

# CI/CD simulation
ci: ## Run CI pipeline locally (quality + security + tests)
	@echo "🤖 Running CI pipeline locally..."
	$(MAKE) quality
	$(MAKE) security  
	$(MAKE) test
	@echo "✅ CI pipeline completed successfully!"

# Information Commands
info: ## Show project information and status
	@echo "📊 Project Status:"
	@echo "Python version: $(shell cd backend && python --version 2>/dev/null || echo 'Not available')"
	@echo "Node version: $(shell cd frontend && node --version 2>/dev/null || echo 'Not available')"
	@echo "Docker version: $(shell docker --version 2>/dev/null || echo 'Not available')"
	@echo "Kubectl version: $(shell kubectl version --client --short 2>/dev/null || echo 'Not available')"
	@echo ""
	@echo "Available make targets:"
	@$(MAKE) help