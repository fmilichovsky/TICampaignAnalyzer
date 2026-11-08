"""Region alien sub-state events: crashdown (record-dated), landing, facility and xenoforming level."""

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
    BEFORE,
    analyze,
    only,
    record_set,
    region_ref,
    snapshot,
    state,
)
from tinarrative.analyzers.aliens import RegionAlienAnalyzer
from tinarrative.analyzers.aliens.regions import (
    ALIEN_FACILITY_CHANGED,
    CRASHDOWN_CHANGED,
    LANDING_CHANGED,
    XENOFORMING_CHANGED,
)
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, SourceRole
from tinarrative.model.records import ItemEntry, RecordKind, RecordSet
from tinarrative.model.snapshot import EntityState
from tinarrative.model.values import Observed, Unknown

ANALYZER = RegionAlienAnalyzer()
ALIEN = EntityDomain.REGION_ALIEN_STATE
REGION = EntityDomain.REGION
CRASHDOWN = "TIRegionUFOCrashdownState"
CRASH_DATE = "2031-04-12T00:00:00"


def sub_state(save: str, key: str, state_type: str, region: str = "40", **fields: Observed) -> EntityState:
    return state(ALIEN, key, save, state_type=state_type, region=region_ref(region), **fields)


def crashdown_time(save: str, value: str | None, key: str = "100") -> RecordSet:
    owner = EntityRef(EntityId(ALIEN, key), IdentityConfidence.IN_SAVE_ID, CRASHDOWN)
    return record_set(save, owner, "crashdownTime", RecordKind.DATE, (ItemEntry(0, value),))


def sources(event: Event) -> list[tuple[SourceRole, str, str | None]]:
    return [(s.role, str(s.change.entity_id), s.change.field) for s in event.sources]


def entities(event: Event) -> list[str]:
    return [str(r.entity_id) for r in event.entities]


def test_a_crashdown_is_named_by_region_dated_by_its_time_record_and_cites_both_fields() -> None:
    before = snapshot(
        BEFORE,
        state(REGION, "40", BEFORE),
        sub_state(BEFORE, "100", CRASHDOWN, crashdownPresent=False),
        records=(crashdown_time(BEFORE, None),),
    )
    after = snapshot(
        AFTER,
        state(REGION, "40", AFTER),
        sub_state(AFTER, "100", CRASHDOWN, crashdownPresent=True),
        records=(crashdown_time(AFTER, CRASH_DATE),),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == CRASHDOWN_CHANGED and event.confidence is Confidence.HIGH
    assert (event.date, event.date_basis) == (CRASH_DATE, DateBasis.RECORD)
    assert entities(event) == ["region:40", "region alien state:100"]
    assert event.entities[1].state_type == CRASHDOWN
    assert sources(event) == [
        (SourceRole.PRIMARY, "region alien state:100", "crashdownPresent"),
        (SourceRole.PRIMARY, "region alien state:100", "crashdownTime"),
    ]
    assert dict(event.attributes) == {
        "transition": "changed",
        "before": False,
        "after": True,
        "crashdown_time": CRASH_DATE,
    }


def test_a_cleared_crashdown_is_interval_dated_and_a_time_only_change_still_yields_the_event() -> None:
    before = snapshot(
        BEFORE,
        sub_state(BEFORE, "100", CRASHDOWN, crashdownPresent=True),
        sub_state(BEFORE, "101", CRASHDOWN, region="41", crashdownPresent=True),
        records=(crashdown_time(BEFORE, CRASH_DATE), crashdown_time(BEFORE, CRASH_DATE, "101")),
    )
    after = snapshot(
        AFTER,
        sub_state(AFTER, "100", CRASHDOWN, crashdownPresent=False),
        sub_state(AFTER, "101", CRASHDOWN, region="41", crashdownPresent=True),
        records=(crashdown_time(AFTER, None), crashdown_time(AFTER, "2031-05-01T00:00:00", "101")),
    )
    cleared, redated = analyze(ANALYZER, before, after)
    assert (cleared.date, cleared.date_basis) == (AFTER_DATE, DateBasis.INTERVAL)
    assert cleared.attribute("after") is False and cleared.attribute("crashdown_time") is None
    assert sources(redated) == [(SourceRole.PRIMARY, "region alien state:101", "crashdownTime")]
    assert (redated.date, redated.date_basis) == ("2031-05-01T00:00:00", DateBasis.RECORD)
    assert isinstance(redated.attribute("crashdown_time"), Unknown)
    assert entities(redated) == ["region:41", "region alien state:101"]


def test_xenoforming_level_rising_and_dropping_to_zero_keeps_the_literal_levels() -> None:
    xeno = "TIRegionXenoformingState"
    before = snapshot(
        BEFORE,
        sub_state(BEFORE, "103", xeno, xenoformingLevel=0.0),
        sub_state(BEFORE, "113", xeno, region="41", xenoformingLevel=3.0),
    )
    after = snapshot(
        AFTER,
        sub_state(AFTER, "103", xeno, xenoformingLevel=2.5),
        sub_state(AFTER, "113", xeno, region="41", xenoformingLevel=0.0),
    )
    events = analyze(ANALYZER, before, after)
    rising, dropping = sorted(events, key=lambda event: event.id)
    assert {event.event_type for event in events} == {XENOFORMING_CHANGED}
    assert (rising.attribute("before"), rising.attribute("after")) == (0.0, 2.5)
    assert (dropping.attribute("before"), dropping.attribute("after")) == (3.0, 0.0)
    assert entities(dropping) == ["region:41", "region alien state:113"]
    assert (rising.date, rising.date_basis) == (AFTER_DATE, DateBasis.INTERVAL)


def test_landing_and_facility_flags_are_events_and_secondary_fields_stay_in_the_diff() -> None:
    landing, facility, activity = "TIRegionUFOLandingState", "TIRegionAlienFacilityState", "TIRegionAlienActivityState"
    before = snapshot(
        BEFORE,
        sub_state(BEFORE, "121", landing, region="42", landingPresent=False, deployingArmy=False, currentHP=0.0),
        sub_state(BEFORE, "112", facility, region="41", built=False, currentHP=0.0),
        sub_state(BEFORE, "122", facility, region="42", built=False, currentHP=0.0),
        sub_state(BEFORE, "104", activity, alienMissionsDetected=None),
    )
    after = snapshot(
        AFTER,
        sub_state(AFTER, "121", landing, region="42", landingPresent=True, deployingArmy=True, currentHP=20.0),
        sub_state(AFTER, "112", facility, region="41", built=True, currentHP=50.0),
        sub_state(AFTER, "122", facility, region="42", built=False, currentHP=10.0),
        sub_state(AFTER, "104", activity, alienMissionsDetected="changed"),
    )
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "region.alien_facility_changed/region alien state:112",
        "region.landing_changed/region alien state:121",
    ]
    assert entities(only(events, LANDING_CHANGED)) == ["region:42", "region alien state:121"]
    assert sources(only(events, ALIEN_FACILITY_CHANGED)) == [(SourceRole.PRIMARY, "region alien state:112", "built")]


def test_a_sub_state_without_its_region_is_still_reported_and_identical_snapshots_produce_nothing() -> None:
    xeno = "TIRegionXenoformingState"
    before = snapshot(BEFORE, state(ALIEN, "103", BEFORE, state_type=xeno, xenoformingLevel=1.0))
    after = snapshot(AFTER, state(ALIEN, "103", AFTER, state_type=xeno, xenoformingLevel=2.0))
    (event,) = analyze(ANALYZER, before, after)
    assert entities(event) == ["region alien state:103"]
    assert analyze(ANALYZER, before, before) == []
