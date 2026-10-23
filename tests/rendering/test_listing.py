from __future__ import annotations

from datetime import datetime

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
) -> Event:
    return Event(
        id=event_id,
        event_type="nation.changed",
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


def _narrative(event_id: str, significance: Significance, cites: tuple[str, ...]) -> Event:
    return Event(
        id=event_id,
        event_type="nation.changed.arc",
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


def test_evidence_lists_what_all_lists() -> None:
    every = listing([INTERVAL], NARRATIVE, minimum=Significance.MAJOR, constituents="all")
    evidence = listing([INTERVAL], NARRATIVE, minimum=Significance.MAJOR, constituents="evidence")

    assert (evidence.narrative, evidence.constituents) == (every.narrative, every.constituents)


def test_without_constituents_no_atomic_event_is_listed() -> None:
    chosen = listing([INTERVAL], NARRATIVE, minimum=Significance.MAJOR)

    assert chosen.narrative == (TOP,)
    assert not chosen.kept([OBJECTIVE, UNCITED, INFERRED])
    assert chosen.filters
    assert chosen.omissions([OBJECTIVE, UNCITED, INFERRED]) == [(3, "omitted with --constituents none")]


def test_without_narrative_atomic_events_are_filtered_by_significance() -> None:
    chosen = listing([INTERVAL], None, minimum=Significance.MINOR, constituents="all")

    assert chosen.narrative is None and chosen.constituents is None
    assert chosen.kept([OBJECTIVE, UNCITED, INFERRED]) == (UNCITED, INFERRED)
    assert chosen.omissions([OBJECTIVE, UNCITED, INFERRED]) == [(1, "below minor significance omitted")]
    assert not listing([INTERVAL], None, minimum=Significance.TRIVIAL).filters
