.PHONY: help install fmt lint type test check schemas run clean

help:
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Sync the workspace, including dev dependencies
	uv sync --all-packages

fmt: ## Format and autofix
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint without fixing
	uv run ruff format --check .
	uv run ruff check .

type: ## Strict type check
	uv run mypy src packages/makeover-contracts/src

test: ## Run the suite with coverage
	uv run pytest

schemas: ## Regenerate the checked-in JSON Schemas
	uv run makeover-contracts-export

check: lint type test ## Everything CI runs
	uv run makeover-contracts-export --check

run: ## Serve the API on :8080
	uv run uvicorn makeover_discovery.interfaces.api.app:app --reload --port 8080

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build
