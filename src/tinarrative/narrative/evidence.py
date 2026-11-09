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

_EVIDENCE: tuple[str, ...] = (
    # Space combat and footholds: the game's own records date each battle and lost hab and name the sides; the
    # inferred readings name who won, what was destroyed, when a hab began to work and where a faction first
    # settled.
    "faction.hab_destruction_recorded",
    "faction.combat_recorded",
    "faction.battle_outcome",
    "hab.destroyed",
    "hab.established",
    "faction.first_hab_on_body",
    # Wars: the start and end dates, the last fighting and when each nation joined a side.
    "war.appeared",
    "war.disappeared",
    "war.last_fighting_changed",
    "war.alliance_changed",
    # Federations: founding, dissolution, each member joining or leaving, and a new name.
    "federation.appeared",
    "federation.disappeared",
    "federation.members_changed",
    "federation.renamed",
    # Dated records: a completed technology or project.
    "technology.completed",
    "faction.project_completed",
)

NARRATOR_EVIDENCE: Final[frozenset[str]] = frozenset(_EVIDENCE)

EVIDENCE_PREFIXES: Final[tuple[str, ...]] = (
    # A councilor defecting, detained or gone is who acted, which no narrative event names.
    "councilor.",
)


def is_evidence(event_type: str) -> bool:
    kind = kind_of(event_type)
    if kind is not None:
        return kind.evidence is EvidenceRole.EVIDENCE
    return event_type in NARRATOR_EVIDENCE or event_type.startswith(EVIDENCE_PREFIXES)
