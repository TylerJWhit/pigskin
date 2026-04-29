# Makefile for Pigskin Auction Draft Tool

.PHONY: setup install dev-install test clean help run-tests format lint typecheck coverage security audit ci standup lab-bench lab-gate

# Default target
help:
	@echo "Pigskin Auction Draft Tool - Available commands:"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  setup       - Run the full setup script"
	@echo "  install     - Install Python dependencies only"
	@echo "  dev-install - Install all three packages (core/app/lab) in editable mode (Sprint 5+)"
	@echo ""
	@echo "Testing:"
	@echo "  test        - Run all tests"
	@echo "  test-unit   - Run unit tests only"
	@echo "  test-integration - Run integration tests"
	@echo "  coverage    - Run tests with coverage report (gate: 85%)"
	@echo ""
	@echo "Code Quality:"
	@echo "  format      - Format code with black"
	@echo "  lint        - Run flake8 linting"
	@echo "  typecheck   - Run mypy type checking"
	@echo "  security    - Run bandit security scan"
	@echo "  audit       - Run pip-audit CVE scan"
	@echo "  ci          - Run all CI checks (lint + typecheck + security + coverage)"
	@echo ""
	@echo "Operations:"
	@echo "  standup     - Print daily standup summary (git log + project board)"
	@echo "  clean       - Clean up cache and temporary files"
	@echo ""
	@echo "Lab (pigskin-lab — ADR-001/Sprint 5 migration required):"
	@echo "  lab-bench   - Run simulation benchmark batch (STRATEGY=all or STRATEGY=<name>)"
	@echo "  lab-gate    - Run promotion gate evaluation (STRATEGY=<name> required)"
	@echo ""
	@echo "Usage Examples:"
	@echo "  bid         - Example bid recommendation"
	@echo "  mock        - Example mock draft"
	@echo "  tournament  - Example tournament"

# Setup
setup:
	@echo "Running setup script..."
	./setup.sh

# Install dependencies
install:
	@echo "Installing dependencies..."
	python3 -m pip install -r requirements.txt

# Install all three mono-repo packages in editable mode (ADR-001 Sprint 5 migration required)
# Requires core/, app/, lab/ directories to each contain a valid pyproject.toml.
# Until the Sprint 5 migration is complete, use `make install` instead.
dev-install:
	@echo "Installing all packages in editable (dev) mode..."
	@if [ -f "core/pyproject.toml" ] && [ -f "app/pyproject.toml" ] && [ -f "lab/pyproject.toml" ]; then \
		pip install -e core/ -e app/ -e lab/; \
		echo "dev-install complete. pigskin-core, pigskin-app, pigskin-lab are active."; \
	else \
		echo "dev-install requires the ADR-001 Sprint 5 mono-repo migration to be complete."; \
		echo "Expected: core/pyproject.toml, app/pyproject.toml, lab/pyproject.toml"; \
		exit 1; \
	fi

# Testing
test:
	@echo "Running all tests..."
	cd tests && python run_tests.py
	cd tests && python test_project.py

test-unit:
	@echo "Running unit tests..."
	cd tests && python run_tests.py

test-integration:
	@echo "Running integration tests..."
	cd tests && python test_project.py

# Development
format:
	@echo "Formatting code..."
	@if command -v black >/dev/null 2>&1; then \
		black --line-length 100 .; \
	else \
		echo "Black not installed. Run: pip install black"; \
	fi

lint:
	@echo "Running linting..."
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 --max-line-length=120 --exclude=venv,pigskin_auction_draft.egg-info --count --show-source --statistics .; \
	else \
		echo "Flake8 not installed. Run: pip install flake8"; \
	fi

typecheck:
	@echo "Running type checks..."
	@if command -v mypy >/dev/null 2>&1; then \
		mypy . --ignore-missing-imports --exclude venv; \
	else \
		echo "mypy not installed. Run: pip install mypy"; \
	fi

coverage:
	@echo "Running tests with coverage report..."
	@if command -v pytest >/dev/null 2>&1; then \
		pytest tests/ -q --timeout=60 --cov=. --cov-fail-under=85 \
			--cov-report=term-missing --cov-omit="venv/*,tests/*,setup.py"; \
	else \
		echo "pytest not installed. Run: pip install pytest pytest-cov"; \
	fi

security:
	@echo "Running security scan..."
	@if command -v bandit >/dev/null 2>&1; then \
		bandit -r . -ll --exclude ./venv,./tests,./pigskin_auction_draft.egg-info; \
	else \
		echo "bandit not installed. Run: pip install bandit"; \
	fi

audit:
	@echo "Running dependency CVE audit..."
	@if command -v pip-audit >/dev/null 2>&1; then \
		pip-audit -r requirements.txt; \
	else \
		echo "pip-audit not installed. Run: pip install pip-audit"; \
	fi

ci: lint typecheck security coverage
	@echo "All CI checks passed."

# Lab targets (pigskin-lab — requires ADR-001 Sprint 5 migration: lab/ directory must exist)
# Usage:
#   make lab-bench                    # benchmark all candidate strategies
#   make lab-bench STRATEGY=enhanced_vor_v3  # benchmark a specific strategy
#   make lab-gate STRATEGY=enhanced_vor_v3   # run promotion gate for a strategy

STRATEGY ?= all
EXPERIMENT_ID ?=

lab-bench:
	@echo "Running lab simulation benchmark (strategy=$(STRATEGY))..."
	@if [ -f "lab/simulation/runner.py" ]; then \
		python lab/simulation/runner.py \
			--strategy "$(STRATEGY)" \
			$(if $(EXPERIMENT_ID),--experiment "$(EXPERIMENT_ID)",); \
	else \
		echo "lab/simulation/runner.py not found."; \
		echo "The lab/ structure requires the ADR-001 Sprint 5 migration to be complete."; \
		exit 1; \
	fi

lab-gate:
	@if [ -z "$(STRATEGY)" ] || [ "$(STRATEGY)" = "all" ]; then \
		echo "Error: STRATEGY is required for lab-gate."; \
		echo "Usage: make lab-gate STRATEGY=<strategy_name>"; \
		exit 1; \
	fi
	@echo "Running promotion gate evaluation for strategy: $(STRATEGY)..."
	@if [ -f "lab/promotion/gate.py" ]; then \
		python lab/promotion/gate.py \
			--strategy "$(STRATEGY)" \
			$(if $(EXPERIMENT_ID),--experiment "$(EXPERIMENT_ID)",); \
	else \
		echo "lab/promotion/gate.py not found."; \
		echo "The lab/ structure requires the ADR-001 Sprint 5 migration to be complete."; \
		exit 1; \
	fi

standup:
	@echo "=== Daily Standup — $$(date +%Y-%m-%d) ==="
	@echo ""
	@echo "--- Recent commits (last 24h) ---"
	@git log --since="24 hours ago" --oneline --no-merges 2>/dev/null || echo "(none)"
	@echo ""
	@echo "--- In Progress issues ---"
	@gh project item-list 2 --owner TylerJWhit --format json --limit 200 2>/dev/null \
		| jq -r '.items[] | select(.status == "In Progress") | "  #\(.content.number) \(.content.title)"' \
		|| echo "  (gh CLI not configured)"
	@echo ""
	@echo "--- In Review issues ---"
	@gh project item-list 2 --owner TylerJWhit --format json --limit 200 2>/dev/null \
		| jq -r '.items[] | select(.status == "In Review") | "  #\(.content.number) \(.content.title)"' \
		|| echo "  (gh CLI not configured)"
	@echo ""
	@echo "--- Test status ---"
	@pytest tests/ -q --timeout=60 2>&1 | tail -3 || echo "  (pytest not available)"

clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# Usage examples
bid:
	@echo "Example: Bid recommendation for Josh Allen at $25"
	./pigskin bid "Josh Allen" 25

mock:
	@echo "Example: Mock draft with value strategy, 8 teams"
	./pigskin mock value 8

tournament:
	@echo "Example: Quick tournament with 2 rounds, 6 teams"
	./pigskin tournament 2 6

# Check if in virtual environment
check-venv:
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "Warning: Not in a virtual environment. Run 'source venv/bin/activate'"; \
	else \
		echo "Virtual environment active: $$VIRTUAL_ENV"; \
	fi
