"""Narrator evidence: which constituents of a development the narrator package lists in its atomic stream.

A type is evidence when it states a fact its development does not carry, mostly a record date, a place or a
destruction; every other type is bookkeeping the development already states in summary form. A type no entry names
is not evidence. ``--constituents all`` still lists everything, so every constituent ID resolves there.
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
    # The band crossing behind a band-shift development, with the game's band labels and its causes.
    "nation.band_crossed",
    # A population move beyond territory, and a five-year per-capita GDP trend at its quarter, behind a collapse or
    # an economic trajectory.
    "nation.population_changed",
    "nation.pcgdp_trend",
    # A boost, mission control or space defences move with the share territory carried, behind a space program or
    # the first space defences.
    "nation.space_assets_changed",
    # A nuclear program starting, behind a nation's first nuclear weapons.
    "nation.nuclear_program_changed",
)

NARRATOR_EVIDENCE: Final[frozenset[str]] = frozenset(_EVIDENCE)

EVIDENCE_PREFIXES: Final[tuple[str, ...]] = (
    # The game's notification log dates and places a battle or a destroyed hab.
    "notification.",
    # A councilor defecting, detained or gone is who acted, which no development names.
    "councilor.",
)


def is_evidence(event_type: str) -> bool:
    return event_type in NARRATOR_EVIDENCE or event_type.startswith(EVIDENCE_PREFIXES)
