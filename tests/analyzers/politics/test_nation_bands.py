"""Nation band crossings: the margin, the tracked causes with their rest-value share, and the placeholder skip."""

from tests.analyzers.support import AFTER, BEFORE, analyze, region_ref, snapshot, state
from tinarrative.analyzers.politics import NationBandAnalyzer
from tinarrative.kinds import describe_event
from tinarrative.kinds.nations import BAND_CROSSED
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import SourceRole
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, freeze

ANALYZER = NationBandAnalyzer()
NATION = EntityDomain.NATION
REGIONS = (region_ref("40"),)
TRACKER = "tracker_UnrestChangeReason_AllTime"
QUARTER = 92.0


def nation_pair(
    before_fields: dict[str, Observed], after_fields: dict[str, Observed]
) -> tuple[SaveSnapshot, SaveSnapshot]:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, regions=REGIONS, **before_fields))
    after = snapshot(AFTER, state(NATION, "20", AFTER, regions=REGIONS, **after_fields))
    return before, after


def test_an_unrest_crossing_carries_the_bands_the_causes_and_the_rest_value_share() -> None:
    before, after = nation_pair(
        {"unrest": 2.5, TRACKER: freeze({"UnrestReason_MovementToRestValue": 1.0})},
        {
            "unrest": 4.75,
            TRACKER: freeze({"UnrestReason_MovementToRestValue": 1.75, "UnrestReason_OppressionPriority": 1.5}),
        },
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == BAND_CROSSED.event_type and event.id == "nation.band_crossed/nation:20/unrest"
    assert dict(event.attributes) == {
        "statistic": "unrest",
        "before": 2.5,
        "after": 4.75,
        "from_band": "Subversion",
        "to_band": "Insurgency",
        "bands_crossed": 2,
        "margin": 0.25,
        "interval_days": QUARTER,
        "causes": FrozenMap((("UnrestReason_MovementToRestValue", 0.75), ("UnrestReason_OppressionPriority", 1.5))),
        "rest_value_share": 0.75 / 2.25,
    }
    assert [source.role for source in event.sources] == [SourceRole.PRIMARY, SourceRole.CORROBORATING]
    assert describe_event(event) == "Fixture nation 20 (nation:20) unrest: Subversion -> Insurgency (2.5 -> 4.75)"


def test_a_crossing_short_of_the_margin_is_not_reported() -> None:
    before, after = nation_pair({"unrest": 1.25}, {"unrest": 1.5})
    assert analyze(ANALYZER, before, after) == []
    before, after = nation_pair({"democracy": 3.99}, {"democracy": 4.02})
    assert analyze(ANALYZER, before, after) == []


def test_military_tech_has_a_smaller_margin_and_no_causes() -> None:
    before, after = nation_pair({"militaryTechLevel": 4.0}, {"militaryTechLevel": 3.9})
    (event,) = analyze(ANALYZER, before, after)
    assert (event.attribute("from_band"), event.attribute("to_band")) == ("Information", "Atomic")
    assert isinstance(event.attribute("causes"), Unknown) and isinstance(event.attribute("rest_value_share"), Unknown)


def test_an_unchanged_tracker_gives_empty_causes_and_no_share() -> None:
    before, after = nation_pair({"democracy": 5.5}, {"democracy": 6.5})
    (event,) = analyze(ANALYZER, before, after)
    assert event.attribute("causes") == FrozenMap()
    assert isinstance(event.attribute("rest_value_share"), Unknown)


def test_placeholders_and_unknown_values_are_skipped() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, regions=(), unrest=1.0))
    after = snapshot(AFTER, state(NATION, "20", AFTER, regions=(), unrest=5.0))
    assert analyze(ANALYZER, before, after) == []
    before, after = nation_pair({"unrest": Unknown()}, {"unrest": 5.0})
    assert analyze(ANALYZER, before, after) == []
