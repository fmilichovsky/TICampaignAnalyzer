"""Narrator evidence: which constituents of a narrative event the narrator package lists in its atomic stream.

A type is evidence when it states a fact its narrative event does not carry, mostly a record date, a place or a
destruction; every other type is bookkeeping the narrative event already states in summary form. A kind declares its
role; a type not yet migrated to a kind is evidence only when an entry here names it. ``--constituents all`` still
lists everything, so every constituent ID resolves there.
"""

from __future__ import annotations

from typing import Final

from ..kinds import kind_of
from ..model.kinds import EvidenceRole

__all__ = ["EVIDENCE_PREFIXES", "NARRATOR_EVIDENCE", "is_evidence"]

_EVIDENCE: tuple[str, ...] = ()

NARRATOR_EVIDENCE: Final[frozenset[str]] = frozenset(_EVIDENCE)

EVIDENCE_PREFIXES: Final[tuple[str, ...]] = ()


def is_evidence(event_type: str) -> bool:
    kind = kind_of(event_type)
    if kind is not None:
        return kind.evidence is EvidenceRole.EVIDENCE
    return event_type in NARRATOR_EVIDENCE or event_type.startswith(EVIDENCE_PREFIXES)
