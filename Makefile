.DEFAULT_GOAL := check

PYTHON ?= python

.PHONY: install format lint typecheck test check package-metrics runtime-metrics

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

check: install format lint typecheck test

# Measure the LLM-bound packages of the benchmark samples with this tree; see benchmarks/README.md.
package-metrics:
	$(PYTHON) -m tinarrative.cli benchmark metrics measure --out build/package-metrics --label "$$(git rev-parse --short HEAD)"

# Time events on the benchmark samples with this tree; see benchmarks/README.md.
runtime-metrics:
	$(PYTHON) -m tinarrative.cli benchmark runtime measure --out build/runtime-metrics/runtime.json --label "$$(git rev-parse --short HEAD)"
	$(PYTHON) -m tinarrative.cli benchmark runtime report build/runtime-metrics/runtime.json --out build/runtime-metrics/report.md
