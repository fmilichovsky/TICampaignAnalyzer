"""Maintenance tooling: scan saves for unknown structures and keep the triage registry.

A tool package, not a pipeline stage: it may import ``io``, ``parsing`` and ``log``; nothing in the pipeline
imports it.
"""

from __future__ import annotations

REGISTRY_ENV_VAR = "TINARRATIVE_UNKNOWNS_REGISTRY"
"""Default registry path for ``tinarrative unknowns`` and ``parse --record-unknowns``; a flag overrides it."""

__all__ = ["REGISTRY_ENV_VAR"]
