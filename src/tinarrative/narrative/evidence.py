"""Narrator evidence: which constituents of a development the narrator package lists in its atomic stream.

A development (``narrative.aggregation``) already summarizes the atomic and inferred events it is built from; the
atomic stream exists for detail and citation by ID. An event type is narrator evidence when it states a fact its
development does not carry, mostly a record date, a place or a destruction. ``events --constituents evidence`` and
``narrate`` list only those; ``--constituents all`` and the ``--inferred`` audit report list everything, so every
constituent ID still resolves there.

Every other type is bookkeeping its development states in summary form:

- control-point controllers, losses and presence, ``faction.nation_control_changed`` and the executive record: the
  takeover (its scopes, cause, loser, ``executive_recorded_on`` and ``previous_executive``);
- unrest attempts: the takeover's precursors; claims lists: ``nation.claims_declared``;
- fleet and hab presence: ``faction.battle_outcome``, ``hab.destroyed`` and the colonisation wave;
- per-ship appearances: the fleet buildup's counts;
- nation presence, the breakaway parent, a war's leading attacker or defender, leftover war lists and war relations:
  the release, breakaway and annexation readings and the war arc.

Types are listed with their rationale, as in ``narrative.significance``; a type no entry names is not evidence.
"""

from __future__ import annotations

from typing import Final

__all__ = ["EVIDENCE_PREFIXES", "NARRATOR_EVIDENCE", "is_evidence"]

_EVIDENCE: tuple[str, ...] = (
    # Space combat and footholds: the game's own records date each battle and lost hab and name the sides; the
    # inferred readings name who won, what was destroyed and where a faction first settled.
    "faction.hab_destruction_recorded",
    "faction.combat_recorded",
    "faction.battle_outcome",
    "hab.destroyed",
    "faction.first_hab_on_body",
    # Territory: which region went to whom, and the inferred reading of the transfer.
    "region.nation_changed",
    "nation.territory_gained",
    "nation.territory_lost",
    "nation.independence",
    "nation.unification",
    "nation.annexation",
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
    # A nation's new name, and a nation absorbed by its neighbour.
    "nation.renamed",
    "nation.disappeared",
    # Dated records: a campaign-wide first, a completed technology or project, a ledger charge.
    "campaign.global_milestone_recorded",
    "technology.completed",
    "faction.project_completed",
    "faction.transaction_recorded",
    # The statistic shifts behind a development's metric_shifts or a takeover's precursors, with their causes.
    "nation.statistic_shifted",
)

NARRATOR_EVIDENCE: Final[frozenset[str]] = frozenset(_EVIDENCE)
"""The event types that are narrator evidence by name."""

EVIDENCE_PREFIXES: Final[tuple[str, ...]] = (
    # The game's notification log dates and places a battle or a destroyed hab.
    "notification.",
    # A councilor defecting, detained or gone is who acted, which no development names.
    "councilor.",
)
"""Event type prefixes whose every type is narrator evidence."""


def is_evidence(event_type: str) -> bool:
    """Whether events of ``event_type`` are narrator evidence."""
    return event_type in NARRATOR_EVIDENCE or event_type.startswith(EVIDENCE_PREFIXES)
