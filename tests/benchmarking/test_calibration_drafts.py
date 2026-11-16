"""Draft stakes: their validation, and their shadow rows over the synthetic politics sequence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.benchmarking.calibration_support import check_parity, check_rows
from tests.fixtures import fixture_path
from tinarrative.benchmarking.calibration import drafts
from tinarrative.benchmarking.calibration.drafts import DraftStake, DraftStakeError, draft_name, validate_drafts
from tinarrative.benchmarking.calibration.replay import default_state, replay
from tinarrative.benchmarking.calibration.table import build_index, extract_campaign
from tinarrative.kinds.registry import kind_for
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import Event, Role, Significance
from tinarrative.model.kinds import Stake, StakeMeasure
from tinarrative.narrative.significance import NARRATIVE_STAKE_IMPLEMENTATIONS, NarrativeScaling

SEQUENCE = ("politics_before.json", "politics_after.json", "politics_reverted.json")
CLAIMS, CESSION = "nation.claims_declared", "nation.cession"
REGIONS = NARRATIVE_STAKE_IMPLEMENTATIONS[Stake.REGIONS]


def locations(event: Event, cited: Any = ()) -> tuple[EntityRef, ...]:
    return tuple(
        ref for role, ref in event.roles if role is Role.LOCATION and ref.entity_id.domain is EntityDomain.REGION
    )


TERRITORY = DraftStake(
    name="territory",
    label="Territory",
    issue=1,
    event_types=(CLAIMS, CESSION),
    scalings=(
        REGIONS,
        NarrativeScaling(StakeMeasure.POWER, locations),
        NarrativeScaling(StakeMeasure.POPULATION, locations),
    ),
    base=Significance.MINOR,
)
"""Three candidates on two types: the listed regions' population, which the kinds use, and the location's power
(which no region has) and population."""
CESSION_ONLY = DraftStake(name="cession-only", label="Cession", issue=2, event_types=(CESSION,), scalings=(REGIONS,))


def saves() -> list[Path]:
    return [fixture_path("io", "terra_invicta_json_v1", name) for name in SEQUENCE]


@pytest.fixture(scope="module")
def plain() -> dict[str, Any]:
    return extract_campaign(saves(), ())


@pytest.fixture(scope="module")
def drafted() -> dict[str, Any]:
    return extract_campaign(saves(), (TERRITORY, CESSION_ONLY))


def test_a_draft_scores_one_shadow_row_per_event_of_its_types(drafted: dict[str, Any]) -> None:
    events, shadows = drafted["events"], drafted["drafts"]
    real = {row["id"]: row for row in events}
    covered = [row for row in events if row["type"] in TERRITORY.event_types]

    assert covered
    assert [row["id"] for row in shadows if draft_name(row["id"]) == TERRITORY.name] == [
        f"draft:{TERRITORY.name}:{row['id']}" for row in covered
    ]
    for shadow in shadows:
        source = real[shadow["id"].split(":", 2)[2]]
        assert (shadow["type"], shadow["cited"], shadow["tier"]) == (source["type"], source["cited"], "narrative")
        assert shadow["ruled"] is False
    check_rows(events, shadows)


def test_the_shadow_rows_replay_to_their_scores_at_the_code_references(drafted: dict[str, Any]) -> None:
    check_parity(drafted["events"], drafted["drafts"], (TERRITORY, CESSION_ONLY))


def test_a_shadow_row_takes_the_draft_base_its_candidates_with_a_share_and_the_cited_floor(
    drafted: dict[str, Any],
) -> None:
    rows = [row for row in drafted["drafts"] if draft_name(row["id"]) == TERRITORY.name]

    assert {row["base"] for row in rows} == {Significance.MINOR.base}
    assert any(len(row["stakes"]) == 2 for row in rows)
    assert all(stake["measure"] == StakeMeasure.POPULATION.value for row in rows for stake in row["stakes"])
    index = build_index(["politics"], key="", extracted_at="", drafts=(TERRITORY,))
    result = replay(index, {"politics": drafted["events"]}, default_state(index), {"politics": rows})
    assert any(event["decided_by"] != event["id"] for event in result["campaigns"]["politics"]["drafts"])


def test_two_drafts_on_one_type_sit_side_by_side_and_leave_the_real_rows_alone(
    drafted: dict[str, Any], plain: dict[str, Any]
) -> None:
    cessions = {
        name: {row["id"].split(":", 2)[2] for row in drafted["drafts"] if draft_name(row["id"]) == name}
        for name in (TERRITORY.name, CESSION_ONLY.name)
    }

    assert cessions[CESSION_ONLY.name] and cessions[CESSION_ONLY.name] <= cessions[TERRITORY.name]
    assert drafted["events"] == plain["events"]
    assert plain["drafts"] == []


def test_the_declared_drafts_are_read_when_extraction_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drafts, "DRAFT_STAKES", (CESSION_ONLY,))

    index = build_index(["politics"], key="", extracted_at="")

    assert index["drafts"] == [
        {
            "name": CESSION_ONLY.name,
            "label": CESSION_ONLY.label,
            "issue": CESSION_ONLY.issue,
            "base": kind_for(CESSION).base.value,  # type: ignore[union-attr]
            "measures": [REGIONS.measure.value],
        }
    ]


def test_the_index_lists_each_measure_of_a_draft_once_in_scaling_order() -> None:
    index = build_index(["politics"], key="", extracted_at="", drafts=(TERRITORY,))

    assert index["drafts"][0]["measures"] == [REGIONS.measure.value, StakeMeasure.POWER.value]
    assert len(TERRITORY.scalings) == 3
    assert index["drafts"][0]["base"] == Significance.MINOR.value


def draft(**changes: Any) -> DraftStake:
    fields: dict[str, Any] = {
        "name": "space-program",
        "label": "Space program",
        "issue": 1,
        "event_types": (CESSION,),
        "scalings": (REGIONS,),
        **changes,
    }
    return DraftStake(**fields)


@pytest.mark.parametrize(
    ("drafts_given", "message"),
    [
        ((draft(event_types=("nation.ghost",)),), "'nation.ghost' is declared by no kind"),
        ((draft(event_types=("nation.appeared",)),), "'nation.appeared' is not a narrative event type"),
        ((draft(), draft()), "'space-program' is repeated"),
        ((draft(name="Space Program"),), "not a lowercase slug"),
        ((draft(name="space:program"),), "not a lowercase slug"),
        ((draft(event_types=()),), "names no event type"),
        ((draft(scalings=()),), "has no scaling"),
        ((draft(event_types=(CLAIMS, CESSION)),), "needs a base"),
    ],
)
def test_a_draft_that_cannot_be_scored_is_rejected(drafts_given: tuple[DraftStake, ...], message: str) -> None:
    with pytest.raises(DraftStakeError, match=message):
        validate_drafts(drafts_given)
    with pytest.raises(DraftStakeError, match=message):
        extract_campaign(saves(), drafts_given)
