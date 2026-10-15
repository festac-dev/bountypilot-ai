.PHONY: install dev-install lint format typecheck test test-live audit build demo-video dev-check help

install:            ## Install the package + all tooling into the current environment
	python -m pip install -e .

dev-install:        ## Alias of `install` (dev tooling ships with the base install)
	python -m pip install -e ".[dev]"

lint:               ## Ruff lint
	ruff check src tests

format:             ## Ruff format check
	ruff format --check src tests

format-fix:         ## Apply formatting
	ruff format src tests

typecheck:          ## Mypy
	mypy src/bountypilot

test:               ## Unit + integration + contract + security + e2e (no live network)
	python -m pytest tests -q

test-live:          ## Opt-in live Gibwork API tests (needs network)
	BOUNTYPILOT_LIVE_TESTS=1 pytest tests/integration/test_live_gibwork.py -q

audit:              ## Dependency vulnerability audit (best effort)
	pip-audit || echo "pip-audit not installed; run: pip install pip-audit"

build:              ## Build sdist and wheel
	python -m build

demo-video:         ## Render the cinematic demo video (title card + terminal + outro, soundtrack)
	python scripts/make_demo_video.py
dev-check:          ## Full local quality workflow
	bash scripts/dev-check.sh

help:               ## Show this help
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-18s %s\n", $$1, $$2}'
