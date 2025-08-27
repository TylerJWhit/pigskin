# Makefile for Pigskin Auction Draft Tool

.PHONY: setup install test clean help run-tests format lint

# Default target
help:
	@echo "Pigskin Auction Draft Tool - Available commands:"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  setup     - Run the full setup script"
	@echo "  install   - Install Python dependencies only"
	@echo ""
	@echo "Testing:"
	@echo "  test      - Run all tests"
	@echo "  test-unit - Run unit tests only"
	@echo "  test-integration - Run integration tests"
	@echo ""
	@echo "Development:"
	@echo "  format    - Format code with black"
	@echo "  lint      - Run linting checks"
	@echo "  clean     - Clean up cache and temporary files"
	@echo ""
	@echo "Usage Examples:"
	@echo "  bid       - Example bid recommendation"
	@echo "  mock      - Example mock draft"
	@echo "  tournament - Example tournament"

# Setup
setup:
	@echo "Running setup script..."
	./setup.sh

# Install dependencies
install:
	@echo "Installing dependencies..."
	python3 -m pip install -r requirements.txt

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
		flake8 --max-line-length=100 --ignore=E203,W503 .; \
	else \
		echo "Flake8 not installed. Run: pip install flake8"; \
	fi

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
