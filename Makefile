# Makefile for python-cfdiclient
# All Python commands run inside the pipenv virtualenv so the local
# environment always matches what CI uses.

.DEFAULT_GOAL := help

# ── Helpers ───────────────────────────────────────────────────────────────────
.PHONY: help
help: ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ── Environment setup ─────────────────────────────────────────────────────────
.PHONY: install
install: ## Install all dependencies (including dev) via pipenv
	pip install --upgrade pip pipenv
	pipenv install --dev --deploy

.PHONY: install-hooks
install-hooks: install ## Install pre-commit hooks
	pipenv run pre-commit install
	pipenv run pre-commit install --hook-type commit-msg

# ── Code quality ──────────────────────────────────────────────────────────────
.PHONY: lint
lint: ## Run pylint against cfdiclient/ (fail-under=8.0)
	pipenv run pylint cfdiclient/ --rcfile=pylint.rc --fail-under=8.0

.PHONY: type-check
type-check: ## Run mypy static type analysis (strict mode)
	pipenv run mypy cfdiclient/ --ignore-missing-imports --strict

.PHONY: format
format: ## Auto-format code with black and sort imports with isort
	pipenv run black cfdiclient/ tests/ --line-length=100
	pipenv run isort cfdiclient/ tests/ --profile=black --line-length=100

.PHONY: format-check
format-check: ## Check formatting without modifying files
	pipenv run black cfdiclient/ tests/ --line-length=100 --check --diff
	pipenv run isort cfdiclient/ tests/ --profile=black --line-length=100 --check --diff

# ── Testing ───────────────────────────────────────────────────────────────────
.PHONY: test
test: ## Run the test suite
	pipenv run pytest tests/ -v

.PHONY: coverage
coverage: ## Run tests and generate HTML + XML coverage reports (fail-under=90)
	pipenv run pytest tests/ \
		--cov=cfdiclient \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--cov-report=term-missing \
		--cov-fail-under=90
	@echo ""
	@echo "HTML report written to htmlcov/index.html"

.PHONY: coverage-open
coverage-open: coverage ## Generate coverage report and open it in the browser
	open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html

# ── Security ──────────────────────────────────────────────────────────────────
.PHONY: security
security: ## Audit dependencies for known vulnerabilities with pip-audit
	pipenv run pip-audit --require-hashes --strict

# ── Building ──────────────────────────────────────────────────────────────────
.PHONY: build
build: ## Build sdist and wheel into dist/
	pipenv run python -m build
	pipenv run twine check dist/*

.PHONY: clean-build
clean-build: ## Remove build artefacts
	rm -rf dist/ build/ *.egg-info

# ── Publishing ────────────────────────────────────────────────────────────────
.PHONY: publish-dry-run
publish-dry-run: build ## Validate the distribution without uploading (twine check)
	pipenv run twine check --strict dist/*
	@echo ""
	@echo "Dry-run complete. Artefacts in dist/ are ready for upload."
	@echo "To publish: push a version tag (e.g. git tag v2.0.1 && git push origin v2.0.1)"

# ── Pre-commit ────────────────────────────────────────────────────────────────
.PHONY: pre-commit
pre-commit: ## Run all pre-commit hooks against staged files
	pipenv run pre-commit run

.PHONY: pre-commit-all
pre-commit-all: ## Run all pre-commit hooks against every file in the repo
	pipenv run pre-commit run --all-files

# ── Combined quality gate (mirrors CI) ───────────────────────────────────────
.PHONY: check
check: lint type-check security test ## Run all quality checks (lint + type-check + security + tests)
	@echo ""
	@echo "All checks passed."
