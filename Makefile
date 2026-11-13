.DEFAULT_GOAL := check

# The main checkout, found through git's common directory; equals this tree outside a worktree.
MAIN_CHECKOUT := $(patsubst %/.git,%,$(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null))

# Prefer an activated environment, then a Codex or project environment, then the main checkout's
# (when run from a worktree without its own), then PATH.
PYTHON ?= $(if $(VIRTUAL_ENV),python,$(if $(wildcard .venv-codex/bin/python),.venv-codex/bin/python,$(if $(wildcard .venv/bin/python),.venv/bin/python,$(if $(wildcard $(MAIN_CHECKOUT)/.venv/bin/python),$(MAIN_CHECKOUT)/.venv/bin/python,python))))

# Run this tree's source whatever environment's editable install points elsewhere.
export PYTHONPATH := $(CURDIR)/src$(if $(PYTHONPATH),:$(PYTHONPATH))
SAMPLE_CAMPAIGNS ?=

.PHONY: install format lint typecheck test check samples package-metrics runtime-metrics

install:
	$(PYTHON) -m pip install -e ".[dev]"

format:
	$(PYTHON) -m ruff format --check .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

check: format lint typecheck test

# The tests that read the committed benchmark campaigns; see docs/testing.md.
samples:
	$(PYTHON) -m pytest -m samples --sample-campaigns "$(SAMPLE_CAMPAIGNS)"

# Measure the LLM-bound packages of the benchmark samples with this tree; see benchmarks/README.md.
package-metrics:
	$(PYTHON) -m tinarrative.cli benchmark metrics measure --out build/package-metrics --label "$$(git rev-parse --short HEAD)"

# Time events on the benchmark samples with this tree; see benchmarks/README.md.
runtime-metrics:
	$(PYTHON) -m tinarrative.cli benchmark runtime measure --out build/runtime-metrics/runtime.json --label "$$(git rev-parse --short HEAD)"
	$(PYTHON) -m tinarrative.cli benchmark runtime report build/runtime-metrics/runtime.json --out build/runtime-metrics/report.md
