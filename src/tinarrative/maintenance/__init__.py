"""Maintenance tooling: scan saves for unknown structures and keep the triage registry.

Like ``inspection``, this is a tool package rather than a pipeline stage. It may import ``io``, ``parsing`` and
``log``; nothing in the pipeline imports it.
"""

from __future__ import annotations

REGISTRY_ENV_VAR = "TINARRATIVE_UNKNOWNS_REGISTRY"
"""Default registry path for ``tinarrative unknowns`` and ``parse --record-unknowns``; a flag overrides it."""

__all__ = ["REGISTRY_ENV_VAR"]
