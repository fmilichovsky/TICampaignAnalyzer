.DEFAULT_GOAL := check

# `make install` creates this environment; callers can still override PYTHON.
ifeq ($(OS),Windows_NT)
VENV_PYTHON := .venv/Scripts/python.exe
else
VENV_PYTHON := .venv/bin/python
endif
PYTHON ?= $(VENV_PYTHON)

# Run this tree's source whatever environment's editable install points elsewhere.
export PYTHONPATH := $(CURDIR)/src$(if $(PYTHONPATH),:$(PYTHONPATH))
SAMPLE_CAMPAIGNS ?=

.PHONY: install format lint typecheck test check docs samples samples-fast calibrate-open package-metrics runtime-metrics

# Override PYTHON when a particular interpreter is needed (Python 3.11 or newer).

install:
	python -m venv .venv
	$(VENV_PYTHON) -m pip install -e ".[dev]"

format:
	$(PYTHON) -m ruff format --check .

format-fix:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

check: format lint typecheck test

# Rewrite the generated regions of docs/commands/ from the CLI parser.
docs:
	$(PYTHON) -m tinarrative.reference_docs

# The tests that read the committed benchmark campaigns; see docs/testing.md.
# samples-fast: the short campaign only, for pull request CI and local agent runs.
# samples: every campaign (or SAMPLE_CAMPAIGNS), for pushes to main.
SAMPLES_FAST_CAMPAIGNS := protectorate-short

samples-fast:
	$(PYTHON) -m pytest -m samples --sample-campaigns "$(SAMPLES_FAST_CAMPAIGNS)"

samples:
	$(PYTHON) -m pytest -m samples --sample-campaigns "$(SAMPLE_CAMPAIGNS)"

# Serve the share calibration page until interrupted, without opening a browser; .claude/launch.json runs it.
calibrate-open:
	$(PYTHON) -m tinarrative.cli benchmark calibrate open --no-open

# Measure the LLM-bound packages of the benchmark samples with this tree; see benchmarks/README.md.
package-metrics:
	$(PYTHON) -m tinarrative.cli benchmark metrics measure --out build/package-metrics --label "$$(git rev-parse --short HEAD)"

# Time events on the benchmark samples with this tree; see benchmarks/README.md.
runtime-metrics:
	$(PYTHON) -m tinarrative.cli benchmark runtime measure --out build/runtime-metrics/runtime.json --label "$$(git rev-parse --short HEAD)"
	$(PYTHON) -m tinarrative.cli benchmark runtime report build/runtime-metrics/runtime.json --out build/runtime-metrics/report.md
