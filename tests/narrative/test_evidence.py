from __future__ import annotations

import pytest

from tinarrative.narrative.evidence import is_evidence

EVIDENCE = [
    "faction.hab_destruction_recorded",
    "faction.combat_recorded",
    "faction.battle_outcome",
    "hab.destroyed",
    "faction.first_hab_on_body",
    "notification.LogSpaceBattleTakesPlace",
    "notification.LogHabDestroyed",
    "region.nation_changed",
    "nation.territory_gained",
    "nation.territory_lost",
    "nation.independence",
    "nation.unification",
    "nation.annexation",
    "war.appeared",
    "war.disappeared",
    "war.last_fighting_changed",
    "war.alliance_changed",
    "federation.appeared",
    "federation.disappeared",
    "federation.members_changed",
    "federation.renamed",
    "nation.renamed",
    "nation.disappeared",
    "campaign.global_milestone_recorded",
    "technology.completed",
    "faction.project_completed",
    "faction.transaction_recorded",
    "councilor.faction_changed",
    "councilor.detaining_faction_changed",
    "councilor.disappeared",
    "nation.statistic_shifted",
    "nation.band_crossed",
]
BOOKKEEPING = [
    "control_point.controller_changed",
    "control_point.loss_recorded",
    "control_point.appeared",
    "control_point.disappeared",
    "faction.nation_control_changed",
    "nation.executive_change_recorded",
    "fleet.disappeared",
    "hab.appeared",
    "hab.disappeared",
    "nation.claims_changed",
    "nation.unrest_attempts_changed",
    "nation.appeared",
    "nation.breakaway_parent_changed",
    "war.attacker_changed",
    "war.defending_alliance_changed",
    "nation.relation_changed",
    "ship.appeared",
]


@pytest.mark.parametrize("event_type", EVIDENCE)
def test_a_fact_no_development_carries_is_evidence(event_type: str) -> None:
    assert is_evidence(event_type)


@pytest.mark.parametrize("event_type", BOOKKEEPING)
def test_what_a_development_summarizes_is_not_evidence(event_type: str) -> None:
    assert not is_evidence(event_type)
