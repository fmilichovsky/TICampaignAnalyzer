"""The councilor brief: the model-facing rendering of the dossier header and one entry (ADR-0020).

The dossier stays the audit artifact; only the brief omits, rewords or bands what the model reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

HEADER_KEYS = ("as_of",)
"""The dossier header the brief keeps; ``source``, ``player_faction`` and ``selection`` are audit data."""
AUDIT_KEYS = frozenset({"id", "player", "xp", "prominence"})
"""Entry fields the brief drops."""
VISIBILITY_AUDIT_KEYS = frozenset({"concealment"})
ORG_AUDIT_KEYS = frozenset({"id", "template", "basis"})
CAREER_AUDIT_KEYS = frozenset({"event"})
NAMED_AUDIT_KEYS = frozenset({"id"})
"""Dropped from the named references of ``home``."""


def councilor_brief(dossier: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    """The header and ``entry`` without their audit fields; every other value is the dossier's own."""
    councilor: dict[str, Any] = {}
    for key, value in entry.items():
        if key in AUDIT_KEYS:
            continue
        if key == "visibility" and isinstance(value, Mapping):
            value = _without(value, VISIBILITY_AUDIT_KEYS)
        elif key == "orgs" and isinstance(value, list):
            value = [_without(org, ORG_AUDIT_KEYS) if isinstance(org, Mapping) else org for org in value]
        elif key == "career" and isinstance(value, list):
            value = [_without(item, CAREER_AUDIT_KEYS) if isinstance(item, Mapping) else item for item in value]
        elif key == "home" and isinstance(value, Mapping):
            value = {
                name: _without(ref, NAMED_AUDIT_KEYS) if isinstance(ref, Mapping) else ref
                for name, ref in value.items()
            }
        councilor[key] = value
    return {**{key: dossier.get(key) for key in HEADER_KEYS}, "councilor": councilor}


def _without(mapping: Mapping[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in keys}
