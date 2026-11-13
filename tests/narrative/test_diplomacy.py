"""The diplomatic realignment rule over synthetic alliance and rivalry changes, takeovers and situation reports."""

from __future__ import annotations

from tests.narrative.support import atomic, faction, nation, nation_row, situation
from tinarrative.config import GeopoliticsSettings, NarrativeSettings
from tinarrative.kinds import attributes, describe_event
from tinarrative.kinds.control import NATION_CONTROL_CHANGED
from tinarrative.kinds.nations import RELATION_CHANGED
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, Event, EventStatus, Role, Significance
from tinarrative.model.values import FrozenMap, Observed
from tinarrative.narrative import aggregate, narrative_rules
from tinarrative.narrative.diplomacy import REALIGNMENT
from tinarrative.narrative.situation import SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
K3 = "2034-01-01T00:00:00"
K4 = "2034-04-01T00:00:00"
PREVIOUS = {K1: K0, K2: K1, K3: K2, K4: K3}
NORTH = nation("20", "Northland")
SOUTH = nation("21", "Southland")
EAST = nation("22", "Eastland")
WEST = nation("23", "Westland")
FAR = nation("24", "Farland")
RESISTANCE = faction("15", "Resistance")
SERVANTS = faction("16", "Servants")


def relation(key: str, one: EntityRef, other: EntityRef, field: str = "allies", transition: str = "added") -> Event:
    pair = sorted((one, other), key=lambda ref: ref.entity_id.sort_key)
    return atomic(
        f"{RELATION_CHANGED.event_type}/{field}/{pair[0].entity_id}/{pair[1].entity_id}/{transition}",
        key,
        not_before=PREVIOUS[key],
        entities=tuple(pair),
        attributes=attributes(RELATION_CHANGED, relation=field, transition=transition, reciprocal=True),
    )


def executive_change(key: str, before: EntityRef, after: EntityRef, subject: EntityRef = NORTH) -> Event:
    return atomic(
        f"faction.nation_control_changed/{subject.entity_id}/executive",
        key,
        not_before=PREVIOUS[key],
        status=EventStatus.INFERRED,
        significance=Significance.MAJOR,
        entities=(subject, before, after),
        attributes=attributes(
            NATION_CONTROL_CHANGED,
            scope="executive",
            before=before,
            after=after,
            shares_before=FrozenMap(()),
            shares_after=FrozenMap(()),
            point_count_before=0,
            point_count_after=0,
            points_moved=0,
            cause="Politics",
            recorded_on=None,
            new_executive=None,
            seat=None,
            population=None,
        ),
    )


def reports(gdp: Observed = 1.0, *keys: str) -> list[SituationReport]:
    """Reports at K0..K4 by default; NORTH ranks first by GDP when ``gdp`` exceeds SOUTH's 100."""
    return [
        situation(key, nations=[nation_row(NORTH, gdp=gdp), nation_row(SOUTH, gdp=100.0), EAST, WEST, FAR])
        for key in (keys or (K0, *PREVIOUS))
    ]


def built(stream: list[Event], situations: list[SituationReport] | None = None, **settings: object) -> list[Event]:
    narrative = NarrativeSettings(geopolitics=GeopoliticsSettings(top_gdp_nations=1, **settings))  # type: ignore[arg-type]
    events = aggregate(stream, reports() if situations is None else situations, narrative_rules(narrative))
    return [event for event in events if event.event_type == REALIGNMENT]


def three_partners(key: str = K1) -> list[Event]:
    return [relation(key, NORTH, SOUTH), relation(key, NORTH, EAST), relation(key, NORTH, WEST, "rivals", "removed")]


def test_three_partners_in_one_interval_are_one_objective_realignment() -> None:
    stream = three_partners()

    [item] = built(stream)

    assert item.id == f"{REALIGNMENT}/nation:20@{K1}"
    assert item.constituents == tuple(sorted(event.id for event in stream))
    assert [(role, ref.entity_id.key) for role, ref in item.roles] == [
        (Role.ACTOR, "20"),
        (Role.TARGET, "21"),
        (Role.TARGET, "22"),
        (Role.TARGET, "23"),
    ]
    assert dict(item.attributes) == {
        "allies_gained": (SOUTH, EAST),
        "allies_lost": (),
        "rivals_gained": (),
        "rivals_lost": (WEST,),
        "reversed_partners": (),
        "partner_count": 3,
        "executive": None,
        "gdp_rank": 2,
        "strength_rank": None,
        "metric_shifts": (),
    }
    assert (item.status, item.confidence, item.significance) == (
        EventStatus.OBJECTIVE,
        Confidence.HIGH,
        Significance.MAJOR,
    )
    assert (item.start, item.end, item.open) == (K0, K1, False)
    assert describe_event(item) == (
        "Northland (nation:20) realigned its diplomacy with 3 partners: allies +2/-0, rivals +0/-1"
    )


def test_fewer_partners_than_the_threshold_is_no_realignment() -> None:
    assert built(three_partners()[:2]) == []
    assert len(built(three_partners()[:2], realignment_min_partners=2)) == 1


def test_a_change_beyond_the_window_starts_a_new_run() -> None:
    stream = [*three_partners()[:2], relation(K4, NORTH, WEST)]

    assert built(stream) == []
    [item] = built(stream, realignment_window_days=1000)
    assert item.intervals == (K1, K4)
    assert item.open is True


def test_the_same_partner_counts_once_and_an_ally_turned_rival_is_reversed() -> None:
    stream = [
        relation(K1, NORTH, SOUTH, "allies", "removed"),
        relation(K2, NORTH, SOUTH, "rivals", "added"),
        relation(K2, NORTH, EAST),
        relation(K2, NORTH, WEST),
    ]

    [item] = built(stream)

    attributes = dict(item.attributes)
    assert (attributes["partner_count"], attributes["reversed_partners"]) == (3, (SOUTH,))
    assert attributes["allies_lost"] == attributes["rivals_gained"] == (SOUTH,)
    assert describe_event(item) == (
        "Northland (nation:20) realigned its diplomacy with 3 partners: allies +2/-1, rivals +1/-0; "
        "reversed with [Southland (nation:21)]"
    )


def test_a_pair_change_counts_for_both_nations() -> None:
    stream = [*three_partners(), relation(K1, SOUTH, EAST), relation(K1, SOUTH, WEST)]

    items = built(stream)

    assert [item.entities[0] for item in items] == [NORTH, SOUTH]
    assert dict(items[1].attributes)["allies_gained"] == (NORTH, EAST, WEST)


def test_a_takeover_inside_the_window_is_cited_as_context_and_names_the_executive() -> None:
    control = executive_change(K1, RESISTANCE, SERVANTS)
    stream = [control, *three_partners(K2)]

    [item] = built(stream)

    assert f"faction.takeover/nation:20/faction:16@{K1}" in item.constituents
    assert item.status is EventStatus.INFERRED
    assert dict(item.attributes)["executive"] == SERVANTS
    assert (item.start, item.end) == (K0, K2)
    assert describe_event(item).endswith("; executive Servants (faction:16)")


def test_a_takeover_outside_the_window_or_of_another_nation_is_not_cited() -> None:
    far_back = executive_change(K1, RESISTANCE, SERVANTS)
    other = executive_change(K4, RESISTANCE, SERVANTS, subject=SOUTH)

    [item] = built([far_back, other, *three_partners(K4)])

    assert all(not constituent.startswith("faction.takeover") for constituent in item.constituents)
    assert dict(item.attributes)["executive"] is None


def test_a_top_economy_realignment_is_campaign_defining() -> None:
    [item] = built(three_partners(), reports(gdp=1000.0))

    assert (item.significance, dict(item.attributes)["gdp_rank"]) == (Significance.CAMPAIGN_DEFINING, 1)


def test_war_entries_and_one_sided_lists_are_not_diplomacy() -> None:
    stream = [relation(K1, NORTH, SOUTH, "wars"), relation(K1, NORTH, EAST, "wars"), relation(K1, NORTH, WEST, "wars")]

    assert built(stream) == []


def test_the_order_of_the_stream_does_not_matter() -> None:
    stream = [executive_change(K1, RESISTANCE, SERVANTS), *three_partners(K2), relation(K2, NORTH, SOUTH, "rivals")]

    items = built(stream)

    assert items
    assert built(list(reversed(stream))) == items
