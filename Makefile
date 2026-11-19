.DEFAULT_GOAL := check

# The main checkout, found through git's common directory; equals this tree outside a worktree.
MAIN_CHECKOUT := $(patsubst %/.git,%,$(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null))

# Prefer an activated environment, then a Codex or project environment, then the main checkout's
# (when run from a worktree without its own), then this tree's .venv, which `make install` creates.
PYTHON ?= $(if $(VIRTUAL_ENV),python,$(if $(wildcard .venv-codex/bin/python),.venv-codex/bin/python,$(if $(wildcard .venv/bin/python),.venv/bin/python,$(if $(wildcard $(MAIN_CHECKOUT)/.venv/bin/python),$(MAIN_CHECKOUT)/.venv/bin/python,.venv/bin/python))))

# Run this tree's source whatever environment's editable install points elsewhere.
export PYTHONPATH := $(CURDIR)/src$(if $(PYTHONPATH),:$(PYTHONPATH))
SAMPLE_CAMPAIGNS ?=

.PHONY: install format lint typecheck test check docs samples samples-fast calibrate-open package-metrics runtime-metrics

# Interpreter used to create .venv; override for a specific Python (3.11 or newer).
BOOTSTRAP_PYTHON ?= python3

# Only the project .venv is created on demand; an activated, Codex or main-checkout
# environment, or a PYTHON the caller passed, is used as it is.
$(CURDIR)/.venv/bin/python:
	$(BOOTSTRAP_PYTHON) -m venv .venv

# Creates .venv if there is no environment yet; no `source .venv/bin/activate` is needed,
# since every target resolves the interpreter itself.
install: $(if $(filter .venv/bin/python,$(PYTHON)),$(CURDIR)/.venv/bin/python)
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

# Serve the stake calibration page until interrupted, without opening a browser; .claude/launch.json runs it.
calibrate-open:
	$(PYTHON) -m tinarrative.cli benchmark calibrate open --no-open

# Measure the LLM-bound packages of the benchmark samples with this tree; see benchmarks/README.md.
package-metrics:
	$(PYTHON) -m tinarrative.cli benchmark metrics measure --out build/package-metrics --label "$$(git rev-parse --short HEAD)"

# Time events on the benchmark samples with this tree; see benchmarks/README.md.
runtime-metrics:
	$(PYTHON) -m tinarrative.cli benchmark runtime measure --out build/runtime-metrics/runtime.json --label "$$(git rev-parse --short HEAD)"
	$(PYTHON) -m tinarrative.cli benchmark runtime report build/runtime-metrics/runtime.json --out build/runtime-metrics/report.md
