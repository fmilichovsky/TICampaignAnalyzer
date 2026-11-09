from __future__ import annotations

from datetime import datetime

from tinarrative.kinds.control import TAKEOVER, TAKEOVER_WAVE
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus, Role, Significance
from tinarrative.rendering.listing import listing
from tinarrative.sequence import IntervalResult, SaveRef

BEFORE = SaveRef("before.save", "a" * 64, datetime(2030, 1, 1))
AFTER = SaveRef("after.save", "b" * 64, datetime(2030, 2, 1))
NATION = EntityRef(EntityId(EntityDomain.NATION, "1"), IdentityConfidence.IN_SAVE_ID, name="Germany")


def _atomic(
    event_id: str,
    significance: Significance,
    *,
    status: EventStatus = EventStatus.OBJECTIVE,
    cites: tuple[str, ...] = (),
    event_type: str = "nation.changed",
) -> Event:
    return Event(
        id=event_id,
        event_type=event_type,
        status=status,
        confidence=Confidence.HIGH,
        date=AFTER.date,
        date_basis=DateBasis.INTERVAL,
        not_before=BEFORE.date,
        sources=(),
        entities=(NATION,),
        significance=significance,
        constituents=cites,
    )


def _narrative(
    event_id: str, significance: Significance, cites: tuple[str, ...], event_type: str = "nation.changed.arc"
) -> Event:
    return Event(
        id=event_id,
        event_type=event_type,
        status=EventStatus.INFERRED,
        confidence=Confidence.MEDIUM,
        date=AFTER.date,
        date_basis=DateBasis.INTERVAL,
        not_before=BEFORE.date,
        sources=(),
        entities=(NATION,),
        significance=significance,
        constituents=cites,
        start=BEFORE.date,
        start_basis=DateBasis.INTERVAL,
        end=AFTER.date,
        end_basis=DateBasis.INTERVAL,
        intervals=(AFTER.date,),
        roles=((Role.ACTOR, NATION),),
    )


OBJECTIVE = _atomic("o-1", Significance.TRIVIAL)
UNCITED = _atomic("o-2", Significance.MAJOR)
INFERRED = _atomic("i-1", Significance.MINOR, status=EventStatus.INFERRED, cites=("o-1",))
INTERVAL = IntervalResult(0, AFTER.date, BEFORE, AFTER, 0, (OBJECTIVE, UNCITED), (INFERRED,))
NESTED = _narrative("n-nested", Significance.MINOR, ("i-1",))
TOP = _narrative("n-top", Significance.MAJOR, ("n-nested",))
OTHER = _narrative("n-other", Significance.MINOR, ("o-2",))
NARRATIVE = [NESTED, TOP, OTHER]


def test_constituents_are_followed_through_narrative_and_inferred_events() -> None:
    chosen = listing([INTERVAL], NARRATIVE, minimum=Significance.MAJOR, constituents="all")

    assert chosen.narrative == (NESTED, TOP)  # the cited lower-order event is listed below the level
    assert chosen.constituents == chosen.reached == {"i-1", "o-1"}
    assert [chosen.keeps(event) for event in (OBJECTIVE, UNCITED, INFERRED)] == [True, False, True]
    assert chosen.reason(UNCITED) == "omitted: not cited by a listed narrative event"
    assert chosen.omissions([OBJECTIVE, UNCITED, INFERRED]) == [(1, "omitted: not cited by a listed narrative event")]


def test_evidence_passes_through_bookkeeping_to_the_evidence_beneath_it() -> None:
    region = _atomic("o-1", Significance.TRIVIAL, event_type="region.nation_changed")
    control = _atomic(
        "i-1",
        Significance.MINOR,
        status=EventStatus.INFERRED,
        cites=("o-1",),
        event_type="faction.nation_control_changed",
    )
    interval = IntervalResult(0, AFTER.date, BEFORE, AFTER, 0, (region, UNCITED), (control,))

    chosen = listing([interval], NARRATIVE, minimum=Significance.MAJOR, constituents="evidence")

    assert chosen.narrative == (NESTED, TOP)
    assert chosen.constituents == {"o-1"} and chosen.reached == {"i-1", "o-1"}
    assert chosen.kept([region, UNCITED, control]) == (region,)
    assert chosen.omissions([region, UNCITED, control]) == [
        (1, "omitted: not cited by a listed narrative event"),
        (1, "omitted: not narrator evidence"),
    ]


def test_without_constituents_no_atomic_event_is_listed() -> None:
    chosen = listing([INTERVAL], NARRATIVE, minimum=Significance.MAJOR)

    assert chosen.narrative == (TOP,)
    assert not chosen.kept([OBJECTIVE, UNCITED, INFERRED])
    assert chosen.omissions([OBJECTIVE, UNCITED, INFERRED]) == [(3, "omitted with --constituents none")]


def test_without_narrative_atomic_events_are_filtered_by_significance() -> None:
    chosen = listing([INTERVAL], None, minimum=Significance.MINOR, constituents="all")

    assert chosen.narrative is None and chosen.constituents is None
    assert chosen.kept([OBJECTIVE, UNCITED, INFERRED]) == (UNCITED, INFERRED)
    assert chosen.omissions([OBJECTIVE, UNCITED, INFERRED]) == [(1, "below minor significance omitted")]
    assert not listing([INTERVAL], None, minimum=Significance.TRIVIAL).filters


FIRST = _narrative("t-1", Significance.MAJOR, ("i-1",), TAKEOVER.event_type)
SECOND = _narrative("t-2", Significance.MAJOR, ("o-2",), TAKEOVER.event_type)
WAVE = _narrative("w-1", Significance.MAJOR, ("t-1", "t-2"), TAKEOVER_WAVE.event_type)


def test_a_wave_member_is_a_digest_even_at_its_own_level_and_its_evidence_is_not_reached() -> None:
    chosen = listing([INTERVAL], [FIRST, SECOND, WAVE], minimum=Significance.MAJOR, constituents="all")

    assert chosen.narrative == (FIRST, SECOND, WAVE)
    assert chosen.digested == {"t-1": "w-1", "t-2": "w-1"}
    assert chosen.reached == set() and chosen.constituents == set()


def test_a_member_another_listed_narrative_event_cites_is_listed_in_full() -> None:
    context = _narrative("r-1", Significance.MAJOR, ("t-1",))

    chosen = listing([INTERVAL], [FIRST, SECOND, WAVE, context], minimum=Significance.MAJOR, constituents="all")

    assert chosen.digested == {"t-2": "w-1"}
    assert chosen.reached == {"i-1", "o-1"}


def test_without_the_wave_listed_its_members_are_listed_in_full() -> None:
    minor_wave = _narrative("w-1", Significance.MINOR, ("t-1", "t-2"), TAKEOVER_WAVE.event_type)

    chosen = listing([INTERVAL], [FIRST, SECOND, minor_wave], minimum=Significance.MAJOR, constituents="all")

    assert chosen.narrative == (FIRST, SECOND) and chosen.digested == {}
    assert chosen.reached == {"i-1", "o-1", "o-2"}


def test_without_constituents_a_wave_member_is_still_a_digest() -> None:
    chosen = listing([INTERVAL], [FIRST, SECOND, WAVE], minimum=Significance.MAJOR)

    assert chosen.digested == {"t-1": "w-1", "t-2": "w-1"}
