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

# The interpreter that creates .venv: the first of these on PATH that is Python 3.11 or newer.
# Override BOOTSTRAP_PYTHON to force one (e.g. `make install BOOTSTRAP_PYTHON=python3.12`).
BOOTSTRAP_PYTHON ?= $(shell for p in python3 python python3.14 python3.13 python3.12 python3.11 py; do \
	if command -v $$p >/dev/null 2>&1 && $$p -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then echo $$p; break; fi; done)

install:
	@test -n "$(BOOTSTRAP_PYTHON)" || { echo "No Python 3.11+ found on PATH; install one or run: make install BOOTSTRAP_PYTHON=/path/to/python" >&2; exit 1; }
	@test -x "$(VENV_PYTHON)" || "$(BOOTSTRAP_PYTHON)" -m venv .venv
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

# Rewrite the generated regions of docs/commands/ from the CLI parser, the settings example's values, and the
# principles module from docs/calibration-principles.md; prints the reasons a raised principle revision made stale.
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
