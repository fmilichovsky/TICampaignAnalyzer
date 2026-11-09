"""The geopolitical narrative rules over synthetic qualified streams and situation reports."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import pytest

from tests.narrative.support import (
    atomic,
    faction,
    federation_row,
    nation,
    nation_row,
    ref,
    situation,
    state_change,
    unification,
    war,
    war_row,
)
from tinarrative.config import GeopoliticsSettings, NarrativeSettings
from tinarrative.kinds import attributes, describe_event
from tinarrative.kinds import attributes as kind_attributes
from tinarrative.kinds import nations as nation_kinds
from tinarrative.kinds.faction import TRANSACTION_RECORDED
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus, Role, Significance
from tinarrative.model.values import FrozenMap, Observed, Unknown
from tinarrative.narrative import NARRATIVE_RULES, aggregate, narrative_rules
from tinarrative.narrative.geopolitics import bounded_shifts
from tinarrative.narrative.situation import SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
K3 = "2032-10-01T00:00:00"
PREVIOUS = {K1: K0, K2: K1, K3: K2}
NORTH = nation("20", "Northland")
SOUTH = nation("21", "Southland")
EAST = nation("22", "Eastland")
WEST = nation("23", "Westland")
RESISTANCE = faction("15", "Resistance")
SERVANTS = faction("16", "Servants")
ACADEMY = faction("17", "Academy")
UNION = ref(EntityDomain.FEDERATION, "60", "Union")
WAR = war("70")
POINT = ref(EntityDomain.CONTROL_POINT, "9")
COUNCILOR = ref(EntityDomain.COUNCILOR, "30")
NORTH_REGION = ref(EntityDomain.REGION, "40", "North")
EAST_REGION = ref(EntityDomain.REGION, "41", "East")
SOUTH_REGION = ref(EntityDomain.REGION, "42", "South")


NATION_KINDS = {kind.event_type: kind for kind in nation_kinds.KINDS}


def event(
    raw_type: str,
    key: str,
    subject: EntityRef,
    *parts: object,
    entities: Sequence[EntityRef] = (),
    attributes: Sequence[tuple[str, Observed]] = (),
    status: EventStatus = EventStatus.OBJECTIVE,
    **overrides: object,
) -> Event:
    """An event of interval ``key`` about ``subject``, dated by the interval, citing one change of the subject."""
    raw_id = "/".join([raw_type, str(subject.entity_id), *map(str, parts)])
    if raw_type in NATION_KINDS:  # the kind's constructor checks the keys; a call states only what it exercises
        kind = NATION_KINDS[raw_type]
        stated = {key for key, _ in attributes}
        attributes = kind_attributes(kind, attributes, **{key: Unknown() for key in sorted(kind.required - stated)})
    fields: dict[str, object] = {
        "not_before": PREVIOUS[key],
        "entities": (subject, *entities),
        "attributes": attributes,
        "status": status,
        "sources": (EventSource(state_change(subject)),) if subject.entity_id.key.isdigit() else (),
    }
    fields.update(overrides)
    return atomic(raw_id, key, **fields)  # type: ignore[arg-type]


def control(
    key: str,
    scope: str,
    before: EntityRef | None,
    after: EntityRef | None,
    subject: EntityRef = NORTH,
    cause: str | None = "Politics",
    tag: str = "",
    **overrides: object,
) -> Event:
    return event(
        "faction.nation_control_changed",
        key,
        subject,
        scope,
        *([tag] if tag else []),
        entities=[holder for holder in (before, after) if holder is not None],
        attributes=(("scope", scope), ("before", before), ("after", after), ("cause", cause)),
        status=EventStatus.INFERRED,
        **overrides,
    )


def point(key: str, after: EntityRef, subject: EntityRef = NORTH, point_ref: EntityRef = POINT) -> Event:
    return event(
        "control_point.controller_changed",
        key,
        point_ref,
        entities=[subject, after],
        attributes=(("transition", "changed"), ("after", after)),
    )


def shift(key: str, statistic: str, subject: EntityRef = NORTH, before: float = 1.0, after: float = 2.0) -> Event:
    return event(
        "nation.statistic_shifted",
        key,
        subject,
        statistic,
        attributes=(
            ("statistic", statistic),
            ("before", before),
            ("after", after),
            ("relative_change", abs(after - before) / before),
            ("causes", FrozenMap(((f"{statistic}Reason_Test", after - before),))),
        ),
    )


def territory(
    raw_type: str, key: str, subject: EntityRef, counterparts: Sequence[EntityRef], regions: Sequence[EntityRef]
) -> Event:
    return event(
        raw_type,
        key,
        subject,
        entities=[*counterparts, *regions],
        attributes=(("counterparts", tuple(counterparts)), ("regions", tuple(regions)), ("region_count", len(regions))),
        status=EventStatus.INFERRED,
        confidence=Confidence.HIGH,
    )


def transfer(key: str, gainer: EntityRef, loser: EntityRef, region: EntityRef) -> list[Event]:
    """The territory aggregates of one region moving from ``loser`` to ``gainer``."""
    return [
        territory("nation.territory_gained", key, gainer, [loser], [region]),
        territory("nation.territory_lost", key, loser, [gainer], [region]),
    ]


def annexation(key: str, gainer: EntityRef, loser: EntityRef, region: EntityRef) -> list[Event]:
    reading = event(
        "nation.annexation",
        key,
        gainer,
        loser.entity_id,
        entities=[loser, region],
        attributes=(("regions", (region,)), ("region_count", 1), ("signals", ("war",))),
        status=EventStatus.INFERRED,
        confidence=Confidence.MEDIUM,
        significance=Significance.MAJOR,
    )
    return [reading, *transfer(key, gainer, loser, region)]


def reports(*rows: SituationReport) -> list[SituationReport]:
    return list(rows)


def plain(*keys: str, **kwargs: object) -> list[SituationReport]:
    return [situation(key, **kwargs) for key in keys]  # type: ignore[arg-type]


def built(
    stream: Sequence[Event],
    situations: Sequence[SituationReport],
    settings: GeopoliticsSettings | None = None,
) -> list[Event]:
    rules = NARRATIVE_RULES if settings is None else narrative_rules(NarrativeSettings(settings))
    return aggregate(stream, situations, rules)


def of_type(events: Sequence[Event], event_type: str) -> list[Event]:
    return [item for item in events if item.event_type == event_type]


def only(events: Sequence[Event], event_type: str) -> Event:
    [found] = of_type(events, event_type)
    return found


def roles(item: Event) -> list[tuple[Role, str]]:
    return [(role, str(entity.entity_id)) for role, entity in item.roles]


def shift_ids(item: Event) -> list[str]:
    entries = item.attribute("metric_shifts")
    assert isinstance(entries, tuple)
    return [str(value) for entry in entries for name, ids in entry.items if name == "events" for value in ids]  # type: ignore[union-attr]


# --- faction.takeover --------------------------------------------------------------------------------------------


def test_no_executive_or_sole_change_to_a_faction_is_no_takeover() -> None:
    stream = [
        control(K1, "plurality", RESISTANCE, SERVANTS),
        control(K1, "executive", SERVANTS, None),
        point(K1, SERVANTS),
    ]

    assert of_type(built(stream, plain(K0, K1)), "faction.takeover") == []


def test_an_executive_change_is_a_takeover_with_its_points_records_and_the_loser() -> None:
    anchor = control(K1, "executive", RESISTANCE, SERVANTS)
    gained = point(K1, SERVANTS)
    record = event(
        "nation.executive_change_recorded",
        K1,
        NORTH,
        entities=[SERVANTS],
        attributes=[("recorded_on", "2032-02-15T00:00:00"), ("previous_executive", RESISTANCE)],
    )
    defector = event("councilor.faction_changed", K1, COUNCILOR, entities=[RESISTANCE, SERVANTS])
    elsewhere = event("councilor.faction_changed", K2, ref(EntityDomain.COUNCILOR, "31"), entities=[RESISTANCE])
    other_nation = point(K1, SERVANTS, subject=SOUTH, point_ref=ref(EntityDomain.CONTROL_POINT, "8"))
    stream = [anchor, gained, record, defector, elsewhere, other_nation]

    takeover = only(built(stream, plain(K0, K1, K2)), "faction.takeover")

    assert roles(takeover) == [(Role.ACTOR, "faction:16"), (Role.TARGET, "nation:20"), (Role.LOSER, "faction:15")]
    assert takeover.constituents == tuple(sorted(item.id for item in (anchor, gained, record, defector)))
    assert dict(takeover.attributes) | {"metric_shifts": ()} == {
        "scopes": ("executive",),
        "cause": "Politics",
        "executive_recorded_on": "2032-02-15T00:00:00",
        "previous_executive": RESISTANCE,
        "consolidated": False,
        "gdp_rank": None,
        "metric_shifts": (),
    }
    assert (takeover.status, takeover.confidence, takeover.significance) == (
        EventStatus.INFERRED,
        Confidence.MEDIUM,
        Significance.MAJOR,
    )
    assert takeover.id == f"faction.takeover/nation:20/faction:16@{K1}"
    assert describe_event(takeover) == (
        "Servants (faction:16) took control of Northland (nation:20) from Resistance (faction:15)"
    )


def test_executive_then_every_point_is_one_takeover_and_a_late_one_is_a_second() -> None:
    stream = [control(K1, "executive", RESISTANCE, SERVANTS), control(K2, "sole", None, SERVANTS)]

    consolidated = only(built(stream, plain(K0, K1, K2)), "faction.takeover")
    assert consolidated.attribute("scopes") == ("executive", "sole")
    assert consolidated.attribute("executive_recorded_on") is consolidated.attribute("previous_executive") is None
    assert consolidated.attribute("consolidated") is True
    assert describe_event(consolidated).endswith(" and holds every control point")

    late = [control(K1, "executive", RESISTANCE, SERVANTS), control(K3, "sole", None, SERVANTS)]
    short = GeopoliticsSettings(takeover_consolidation_days=30)
    assert len(of_type(built(late, plain(K0, K1, K2, K3), short), "faction.takeover")) == 2
    assert len(of_type(built(late, plain(K0, K1, K2, K3)), "faction.takeover")) == 1


def test_takeovers_of_one_nation_in_one_interval_are_ordered_by_the_later_ones_loser() -> None:
    stream = [
        control(K1, "executive", SERVANTS, RESISTANCE, tag="a"),
        control(K1, "executive", RESISTANCE, ACADEMY, tag="b"),
    ]

    found = {
        str(item.roles[0][1].entity_id): item for item in of_type(built(stream, plain(K0, K1)), "faction.takeover")
    }

    earlier, later = found["faction:15"], found["faction:17"]
    assert earlier.attribute("succeeded_by") == later.id
    assert later.attribute("succeeds") == earlier.id
    assert "ambiguous" not in dict(earlier.attributes) | dict(later.attributes)


def test_takeovers_of_one_interval_without_a_derivable_order_are_ambiguous() -> None:
    mutual = [
        control(K1, "executive", ACADEMY, RESISTANCE, tag="a"),
        control(K1, "executive", RESISTANCE, ACADEMY, tag="b"),
    ]
    unnamed = [
        control(K1, "executive", None, RESISTANCE, tag="a"),
        control(K1, "executive", None, ACADEMY, tag="b"),
    ]

    for stream in (mutual, unnamed):
        first, second = of_type(built(stream, plain(K0, K1)), "faction.takeover")
        for item, other in ((first, second), (second, first)):
            assert item.attribute("ambiguous") is True
            assert item.attribute("alternatives") == (other.id,)
            assert {"succeeds", "succeeded_by"}.isdisjoint(dict(item.attributes))


def test_takeovers_of_one_nation_in_different_intervals_are_not_linked() -> None:
    stream = [control(K1, "executive", SERVANTS, RESISTANCE), control(K2, "executive", RESISTANCE, ACADEMY)]

    for item in of_type(built(stream, plain(K0, K1, K2)), "faction.takeover"):
        assert {"succeeds", "succeeded_by", "ambiguous", "alternatives"}.isdisjoint(dict(item.attributes))


def test_losing_the_seat_in_between_starts_a_new_takeover() -> None:
    stream = [
        control(K1, "executive", RESISTANCE, SERVANTS),
        control(K2, "executive", SERVANTS, ACADEMY),
        control(K3, "executive", ACADEMY, SERVANTS),
    ]

    found = of_type(built(stream, plain(K0, K1, K2, K3)), "faction.takeover")

    assert [(item.intervals[0], str(item.roles[0][1].entity_id)) for item in found] == [
        (K1, "faction:16"),
        (K2, "faction:17"),
        (K3, "faction:16"),
    ]


def test_a_retaken_nation_is_identified_by_the_retaking_interval_not_its_precursors() -> None:
    stream = [
        control(K1, "sole", None, SERVANTS),
        point(K1, SERVANTS),
        control(K2, "sole", SERVANTS, None),
        control(K3, "sole", None, SERVANTS),
    ]
    reaching = GeopoliticsSettings(takeover_precursor_days=180)

    first, second = of_type(built(stream, plain(K0, K1, K2, K3), reaching), "faction.takeover")

    assert second.intervals[0] == K1
    assert [first.id, second.id] == [
        f"faction.takeover/nation:20/faction:16@{K1}",
        f"faction.takeover/nation:20/faction:16@{K3}",
    ]


def test_an_independence_control_change_is_left_to_the_release_rule() -> None:
    stream = [control(K1, "executive", None, SERVANTS, cause="Independence")]

    assert of_type(built(stream, plain(K0, K1)), "faction.takeover") == []


def test_a_top_economy_takeover_is_campaign_defining_by_the_configured_rank() -> None:
    stream = [control(K1, "executive", RESISTANCE, SERVANTS)]
    after = situation(
        K1, nations=[nation_row(SOUTH, gdp=900.0), nation_row(NORTH, gdp=500.0), nation_row(EAST, gdp=1.0)]
    )
    situations = [situation(K0), after]

    takeover = only(built(stream, situations), "faction.takeover")
    assert (takeover.attribute("gdp_rank"), takeover.significance) == (2, Significance.CAMPAIGN_DEFINING)
    strict = only(built(stream, situations, GeopoliticsSettings(top_gdp_nations=1)), "faction.takeover")
    assert strict.significance is Significance.MAJOR


def _seized(key: str, subject: EntityRef, actor: EntityRef = SERVANTS) -> Event:
    return control(key, "executive", RESISTANCE if actor != RESISTANCE else SERVANTS, actor, subject=subject)


def test_takeovers_of_several_small_nations_by_one_faction_form_a_wave() -> None:
    stream = [_seized(K1, NORTH), _seized(K1, SOUTH), _seized(K2, EAST), _seized(K2, WEST, actor=ACADEMY)]

    events = built(stream, plain(K0, K1, K2))

    wave = only(events, "faction.takeover_wave")
    members = [item for item in of_type(events, "faction.takeover") if item.roles[0][1] == SERVANTS]
    assert set(wave.constituents) == {item.id for item in members}
    assert wave.attribute("nations") == (NORTH, SOUTH, EAST) and wave.attribute("count") == 3
    assert wave.roles == ((Role.ACTOR, SERVANTS), (Role.TARGET, NORTH), (Role.TARGET, SOUTH), (Role.TARGET, EAST))
    assert wave.significance is Significance.MAJOR
    assert describe_event(wave).startswith(f"{SERVANTS.label()} took control of ")


def test_fewer_takeovers_than_the_minimum_are_no_wave() -> None:
    stream = [_seized(K1, NORTH), _seized(K2, SOUTH)]

    assert not of_type(built(stream, plain(K0, K1, K2)), "faction.takeover_wave")
    loose = built(stream, plain(K0, K1, K2), GeopoliticsSettings(takeover_wave_min_nations=2))
    assert only(loose, "faction.takeover_wave").attribute("count") == 2


def test_a_top_economy_takeover_stays_out_of_the_wave() -> None:
    stream = [_seized(K1, nation_ref) for nation_ref in (NORTH, SOUTH, EAST, WEST)]
    after = situation(K1, nations=[nation_row(NORTH, gdp=900.0), nation_row(SOUTH, gdp=1.0)])

    settings = GeopoliticsSettings(top_gdp_nations=1)

    wave = only(built(stream, [situation(K0), after], settings), "faction.takeover_wave")

    assert wave.attribute("nations") == (SOUTH, EAST, WEST)


def test_a_takeover_after_the_window_starts_a_new_run() -> None:
    stream = [_seized(K1, NORTH), _seized(K1, SOUTH), _seized(K2, EAST), _seized(K3, WEST)]

    settings = GeopoliticsSettings(takeover_wave_window_days=60)

    wave = only(built(stream, plain(K0, K1, K2, K3), settings), "faction.takeover_wave")

    assert wave.attribute("nations") == (NORTH, SOUTH, EAST)


@pytest.mark.parametrize(
    ("shares", "expected"),
    [([(SERVANTS, 2), (RESISTANCE, 1)], True), ([(SERVANTS, 3)], False)],
)
def test_a_takeover_is_open_while_the_faction_holds_the_executive_but_not_every_point(
    shares: list[tuple[EntityRef, int]], expected: bool
) -> None:
    last = situation(K1, nations=[nation_row(NORTH, executive=SERVANTS, shares=shares, control_points=3)])

    takeover = only(built([control(K1, "executive", RESISTANCE, SERVANTS)], [situation(K0), last]), "faction.takeover")

    assert takeover.open is expected


def charge(key: str, holder: EntityRef, label: str, date: str) -> Event:
    return event(
        "faction.transaction_recorded",
        key,
        holder,
        label,
        date,
        attributes=attributes(TRANSACTION_RECORDED, label=label, resource="Money", amount=1.0, recorded_on=date),
        date=date,
        date_basis=DateBasis.RECORD,
    )


def test_a_mission_charge_corroborates_only_when_the_faction_is_the_only_candidate() -> None:
    anchor = control(K2, "executive", RESISTANCE, SERVANTS)
    alone = charge(K2, SERVANTS, "Coup", "2032-04-10T00:00:00")
    early = charge(K1, SERVANTS, "Purge", "2032-02-01T00:00:00")
    shared = [
        charge(K2, SERVANTS, "Crackdown", "2032-05-01T00:00:00"),
        charge(K2, ACADEMY, "Crackdown", "2032-05-02T00:00:00"),
    ]
    situations = plain(K0, K1, K2)

    takeover = only(built([anchor, alone, early, *shared], situations), "faction.takeover")

    assert takeover.constituents == tuple(sorted([anchor.id, alone.id]))
    assert takeover.start == "2032-04-01T00:00:00"
    assert takeover.confidence is Confidence.MEDIUM


def test_a_charge_at_the_interval_end_corroborates_without_setting_the_takeovers_end() -> None:
    anchor = control(K2, "executive", RESISTANCE, SERVANTS)
    at_end = charge(K2, SERVANTS, "Crackdown", K2)

    takeover = only(built([anchor, at_end], plain(K0, K1, K2)), "faction.takeover")

    assert at_end.id in takeover.constituents
    assert (takeover.end, takeover.end_basis) == (anchor.date, anchor.date_basis)
    assert takeover.end_basis is not DateBasis.RECORD


def test_a_charge_is_listed_once_when_several_anchors_reach_it() -> None:
    first = control(K1, "executive", RESISTANCE, SERVANTS)
    second = control(K2, "executive", RESISTANCE, SERVANTS)
    near = charge(K1, SERVANTS, "Coup", "2032-03-25T00:00:00")

    takeover = only(built([first, second, near], plain(K0, K1, K2)), "faction.takeover")

    assert takeover.constituents.count(near.id) == 1


def test_one_untargeted_charge_may_corroborate_takeovers_of_two_nations_without_dating_either_end() -> None:
    north = control(K2, "executive", RESISTANCE, SERVANTS)
    south = control(K2, "executive", RESISTANCE, SERVANTS, subject=SOUTH)
    at_end = charge(K2, SERVANTS, "Crackdown", K2)

    takeovers = of_type(built([north, south, at_end], plain(K0, K1, K2)), "faction.takeover")

    assert len(takeovers) == 2
    assert all(at_end.id in t.constituents for t in takeovers)
    assert all(t.end_basis is not DateBasis.RECORD for t in takeovers)


def test_precursors_are_the_factions_unrest_attempts_and_the_nations_unrest_shifts_before_it() -> None:
    anchor = control(K2, "executive", RESISTANCE, SERVANTS)
    attempts = event("nation.unrest_attempts_changed", K1, NORTH, "faction:16", attributes=(("faction", SERVANTS),))
    rival = event("nation.unrest_attempts_changed", K1, NORTH, "faction:17", attributes=(("faction", ACADEMY),))
    unrest = shift(K1, "unrest")
    gdp = shift(K1, "GDP")

    takeover = only(built([anchor, attempts, rival, unrest, gdp], plain(K0, K1, K2)), "faction.takeover")

    assert set(takeover.constituents) == {anchor.id, attempts.id, unrest.id}
    assert takeover.start == K0
    late = control(K3, "executive", RESISTANCE, SERVANTS)
    narrow = GeopoliticsSettings(takeover_precursor_days=0)
    assert only(built([late, attempts], plain(K0, K1, K2, K3), narrow), "faction.takeover").constituents == (late.id,)


def test_metric_shifts_are_attributes_citing_the_shift_events_and_never_constituents() -> None:
    anchor = control(K1, "executive", RESISTANCE, SERVANTS, date="2032-03-01T00:00:00", date_basis=DateBasis.RECORD)
    first = shift(K1, "democracy", before=5.0, after=3.0)
    second = shift(K2, "democracy", before=3.0, after=2.0)
    other = shift(K1, "GDP", subject=SOUTH)
    takeover = only(built([anchor, first, second, other], plain(K0, K1, K2)), "faction.takeover")

    assert takeover.constituents == (anchor.id,)
    assert takeover.start == "2032-03-01T00:00:00"
    (entry,) = takeover.attribute("metric_shifts")  # type: ignore[misc]
    assert dict(entry.items) == {
        "nation": NORTH,
        "statistic": "democracy",
        "before": 5.0,
        "after": 3.0,
        "relative_change": 0.4,
        "not_before": K0,
        "date": K1,
        "date_basis": "interval",
        "causes": FrozenMap((("democracyReason_Test", -2.0),)),
        "from_band": "Anocracy",
        "to_band": "Authoritarian",
        "events": (first.id,),
    }


def statistics(item: Event) -> list[tuple[str, str]]:
    entries = item.attribute("metric_shifts")
    assert isinstance(entries, tuple)
    return [(str(dict(entry.items)["nation"].entity_id), str(dict(entry.items)["statistic"])) for entry in entries]  # type: ignore[union-attr]


def test_metric_shifts_are_bounded_per_narrative_event_and_the_cut_is_counted() -> None:
    stream = [
        *transfer(K1, SOUTH, NORTH, SOUTH_REGION),
        shift(K1, "democracy", before=1.0, after=2.0),
        shift(K1, "GDP", before=1.0, after=1.5),
        shift(K1, "unrest", before=1.0, after=4.0),
        shift(K1, "cohesion", subject=SOUTH, before=1.0, after=1.2),
    ]

    full = only(built(stream, plain(K0, K1)), "nation.cession")
    bounded = only(built(stream, plain(K0, K1), GeopoliticsSettings(metric_shifts_max=2)), "nation.cession")

    assert len(statistics(full)) == 4 and "metric_shifts_omitted" not in dict(full.attributes)
    assert statistics(bounded) == [("nation:20", "democracy"), ("nation:20", "unrest")]
    assert bounded.attribute("metric_shifts_omitted") == 2


def shift_entry(subject: EntityRef, statistic: str, relative: float | None) -> FrozenMap:
    return FrozenMap((("nation", subject), ("statistic", statistic), ("relative_change", relative)))


def test_bounded_shifts_rank_role_nations_then_nuclear_weapons_then_the_largest_change() -> None:
    entries = [
        shift_entry(NORTH, "GDP", 0.1),
        shift_entry(SOUTH, "democracy", 5.0),
        shift_entry(SOUTH, "numNuclearWeapons", None),
        shift_entry(SOUTH, "spaceFunding_year", None),
        shift_entry(SOUTH, "unrest", 0.5),
        shift_entry(WEST, "unrest", 0.5),
    ]
    roles = [(Role.ACTOR, NORTH), (Role.LOCATION, SOUTH_REGION)]

    def kept(limit: int) -> dict[str, object]:
        return dict(bounded_shifts(entries, roles, limit))

    assert kept(4) == {"metric_shifts": tuple(entries[index] for index in (0, 1, 2, 4)), "metric_shifts_omitted": 2}
    assert kept(5) == {"metric_shifts": tuple(entries[:3] + entries[4:]), "metric_shifts_omitted": 1}
    assert kept(6) == kept(12) == {"metric_shifts": tuple(entries)}
    assert kept(0) == {"metric_shifts": (), "metric_shifts_omitted": 6}


# --- war.arc -----------------------------------------------------------------------------------------------------


def war_event(raw_type: str, key: str, *, entities: Sequence[EntityRef] = (), **attributes: Observed) -> Event:
    return event(
        raw_type,
        key,
        WAR,
        *attributes.get("_parts", ()),
        entities=entities,
        attributes=tuple((name, value) for name, value in attributes.items() if name != "_parts"),
        significance=Significance.MAJOR,
    )


def test_a_war_neither_appearing_nor_present_at_the_start_or_without_events_is_no_arc() -> None:
    fighting = war_event("war.last_fighting_changed", K2)
    later = [situation(K0), situation(K1, wars=[WAR]), situation(K2, wars=[WAR])]

    assert of_type(built([fighting], later), "war.arc") == []
    assert of_type(built([], plain(K0, K1, wars=[WAR])), "war.arc") == []


def test_a_war_arc_joins_its_events_by_war_id_and_states_sides_duration_and_strikes() -> None:
    row = war_row(WAR, [NORTH], [SOUTH], start_date="2032-02-01T00:00:00")
    situations = [
        situation(K0, nuclear_strikes=2),
        situation(K1, wars=[row], nuclear_strikes=3),
        situation(K2, wars=[war_row(WAR, [NORTH, WEST], [SOUTH])], nuclear_strikes=5),
        situation(K3, nuclear_strikes=6),
    ]
    appeared = war_event(
        "war.appeared",
        K1,
        entities=[NORTH, SOUTH],
        started_on="2032-02-01T00:00:00",
        date="2032-02-01T00:00:00",
        date_basis=DateBasis.RECORD,
    )  # type: ignore[arg-type]
    joined = war_event("war.alliance_changed", K2, entities=[WEST], side="attacking", member=WEST, _parts=("west",))
    ended = war_event("war.disappeared", K3)

    arc = only(built([appeared, joined, ended], situations), "war.arc")

    assert arc.constituents == tuple(sorted(item.id for item in (appeared, joined, ended)))
    assert (arc.status, arc.confidence, arc.significance, arc.open) == (
        EventStatus.OBJECTIVE,
        Confidence.HIGH,
        Significance.MAJOR,
        False,
    )
    assert roles(arc) == [(Role.ACTOR, "nation:20"), (Role.ACTOR, "nation:23"), (Role.TARGET, "nation:21")]
    assert arc.attribute("duration_days") is None
    assert arc.attribute("duration_days_at_most") == 243.0
    assert (arc.start, arc.start_basis) == ("2032-02-01T00:00:00", DateBasis.RECORD)
    assert arc.attribute("nuclear_strikes") == 4
    assert arc.attribute("war") == WAR
    assert describe_event(arc) == "war:70 between Northland (nation:20), Westland (nation:23) and Southland (nation:21)"


def test_a_record_dated_end_gives_the_duration_and_an_open_war_gives_none() -> None:
    row = war_row(WAR, [NORTH], [SOUTH], start_date="2032-02-01T00:00:00")
    appeared = war_event("war.appeared", K1, entities=[NORTH, SOUTH], started_on="2032-02-01T00:00:00")
    ended = replace(war_event("war.disappeared", K2), date="2032-05-01T00:00:00", date_basis=DateBasis.RECORD)

    closed = only(built([appeared, ended], [situation(K0), situation(K1, wars=[row]), situation(K2)]), "war.arc")
    running = only(built([appeared], [situation(K0), situation(K1, wars=[row]), situation(K2, wars=[row])]), "war.arc")

    assert closed.attribute("duration_days") == 90.0
    assert closed.attribute("duration_days_at_most") is None
    assert running.attribute("duration_days") is None
    assert running.attribute("duration_days_at_most") is None


def test_a_war_started_before_the_first_save_starts_at_its_own_start_date() -> None:
    row = war_row(WAR, [NORTH], [SOUTH], start_date="2031-11-15T00:00:00")
    fighting = replace(
        war_event("war.last_fighting_changed", K2, entities=[NORTH, SOUTH]),
        date="2032-05-01T00:00:00",
        date_basis=DateBasis.RECORD,
    )
    situations = [situation(K0, wars=[row]), situation(K1, wars=[row]), situation(K2, wars=[row])]

    arc = only(built([fighting], situations), "war.arc")

    assert arc.attribute("started_on") == "2031-11-15T00:00:00"
    assert (arc.start, arc.start_basis) == ("2031-11-15T00:00:00", DateBasis.RECORD)
    assert (arc.end, arc.end_basis) == ("2032-05-01T00:00:00", DateBasis.RECORD)


def test_a_war_arc_leaves_out_what_closed_before_its_start_date() -> None:
    row = war_row(WAR, [NORTH], [SOUTH], start_date="2032-08-01T00:00:00")
    older = [shift(K1, "democracy", NORTH), war_event("war.alliance_changed", K1, entities=[NORTH, SOUTH])]
    fighting = war_event("war.last_fighting_changed", K3, entities=[NORTH, SOUTH])
    situations = [situation(key, wars=[row]) for key in (K0, K1, K2, K3)]

    arc = only(built([*older, fighting], situations), "war.arc")

    assert (arc.start, arc.start_basis) == ("2032-08-01T00:00:00", DateBasis.RECORD)
    assert arc.intervals == (K3,)
    assert shift_ids(arc) == []


def test_annexations_between_belligerents_join_the_arc_and_an_expansion_nests_inside_it() -> None:
    sides = war_row(WAR, [NORTH], [SOUTH, EAST])
    situations = [situation(key, wars=[sides]) for key in (K0, K1, K2)]
    first = annexation(K1, NORTH, SOUTH, SOUTH_REGION)
    second = annexation(K2, NORTH, EAST, EAST_REGION)
    unrelated = annexation(K2, WEST, SOUTH, ref(EntityDomain.REGION, "43"))

    events = built([*first, *second, *unrelated], situations)
    expansion = only(of_type(events, "nation.expansion"), "nation.expansion")
    arc = only(events, "war.arc")

    assert expansion.attribute("mode") == "annexation"
    assert arc.constituents == (expansion.id,)
    assert arc.status is EventStatus.INFERRED and arc.open
    assert arc.attribute("regions_transferred") == (EAST_REGION, SOUTH_REGION)

    alone = built(first, situations)
    assert only(alone, "war.arc").constituents == (first[0].id,)


# --- federation.lifecycle ----------------------------------------------------------------------------------------


def federation_event(raw_type: str, key: str, member: EntityRef | None = None, transition: str = "added") -> Event:
    attributes = (("member", member), ("transition", transition)) if member is not None else ()
    parts = (str(member.entity_id), transition) if member is not None else ()
    return event(raw_type, key, UNION, *parts, entities=[member] if member else [], attributes=attributes,
                 significance=Significance.MAJOR)  # fmt: skip


def test_a_federation_lifecycle_lists_its_member_timeline_and_is_objective() -> None:
    situations = [
        situation(K0, federations=[federation_row(UNION, [NORTH])]),
        situation(K1, federations=[federation_row(UNION, [NORTH, SOUTH])]),
        situation(K2, federations=[federation_row(UNION, [SOUTH])]),
    ]
    added = federation_event("federation.members_changed", K1, SOUTH)
    removed = federation_event("federation.members_changed", K2, NORTH, "removed")

    lifecycle = only(built([added, removed, shift(K2, "GDP", SOUTH)], situations), "federation.lifecycle")

    assert (lifecycle.status, lifecycle.significance, lifecycle.open) == (
        EventStatus.OBJECTIVE,
        Significance.MAJOR,
        True,
    )
    assert lifecycle.attribute("members_initial") == (NORTH,)
    assert lifecycle.attribute("members_final") == (SOUTH,)
    assert [dict(change.items)["transition"] for change in lifecycle.attribute("member_changes")] == [
        "added",
        "removed",
    ]  # type: ignore[union-attr]
    assert len(shift_ids(lifecycle)) == 1
    assert describe_event(lifecycle) == (
        "Union (federation:60) members [Northland (nation:20)] -> [Southland (nation:21)] (2 member changes)"
    )


def test_a_federation_lifecycle_attaches_a_members_shifts_only_from_its_membership() -> None:
    situations = [
        situation(K0, federations=[federation_row(UNION, [NORTH])]),
        situation(K1, federations=[federation_row(UNION, [NORTH])]),
        situation(K2, federations=[federation_row(UNION, [NORTH, SOUTH])]),
        situation(K3, federations=[federation_row(UNION, [NORTH])]),
    ]
    joined = federation_event("federation.members_changed", K2, SOUTH)
    left = federation_event("federation.members_changed", K3, SOUTH, "removed")
    stream = [joined, left, shift(K1, "GDP", SOUTH), shift(K2, "GDP", SOUTH), shift(K3, "GDP", SOUTH)]

    lifecycle = only(built(stream, situations), "federation.lifecycle")

    (entry,) = lifecycle.attribute("metric_shifts")  # type: ignore[misc]
    assert dict(entry.items)["events"] == (stream[3].id, stream[4].id)  # the K1 shift predates the membership
    assert dict(entry.items)["not_before"] == K1


def test_a_federation_lifecycle_leaves_out_shifts_from_before_a_member_joined() -> None:
    situations = [
        situation(K0, federations=[federation_row(UNION, [NORTH])]),
        situation(K1, federations=[federation_row(UNION, [NORTH])]),
        situation(K2, federations=[federation_row(UNION, [NORTH, SOUTH])]),
        situation(K3, federations=[federation_row(UNION, [NORTH, SOUTH])]),
    ]
    joined = federation_event("federation.members_changed", K2, SOUTH)
    renamed = [federation_event("federation.renamed", K1), federation_event("federation.renamed", K3)]
    early, late = shift(K1, "GDP", SOUTH), shift(K3, "GDP", SOUTH)

    lifecycle = only(built([joined, *renamed, early, late], situations), "federation.lifecycle")

    assert shift_ids(lifecycle) == [late.id]


def test_a_federation_without_its_anchor_is_no_lifecycle() -> None:
    added = federation_event("federation.members_changed", K2, SOUTH)
    situations = [situation(K0), situation(K1, federations=[UNION]), situation(K2, federations=[UNION])]

    assert of_type(built([added], situations), "federation.lifecycle") == []
    appeared = federation_event("federation.appeared", K1)
    assert len(of_type(built([appeared, added], situations), "federation.lifecycle")) == 1


# --- nation.expansion and nation.cession -------------------------------------------------------------------------


def test_one_gain_is_no_expansion_and_its_territory_aggregate_does_not_count_twice() -> None:
    events = built(annexation(K1, NORTH, SOUTH, SOUTH_REGION), plain(K0, K1))

    assert of_type(events, "nation.expansion") == []


def test_gains_chained_within_the_gap_are_one_expansion_with_cessions_nested() -> None:
    situations = plain(K0, K1, K2, K3)
    ceded = transfer(K1, NORTH, SOUTH, SOUTH_REGION)
    taken = annexation(K2, NORTH, EAST, EAST_REGION)
    gone = event("nation.disappeared", K2, EAST, significance=Significance.CAMPAIGN_DEFINING)

    events = built([*ceded, *taken, gone], situations)
    cession = only(events, "nation.cession")
    expansion = only(events, "nation.expansion")

    assert set(expansion.constituents) == {cession.id, taken[0].id, taken[1].id, gone.id}
    assert expansion.attribute("mode") == "mixed"
    assert expansion.attribute("losers") == (SOUTH, EAST)
    assert expansion.attribute("regions") == (EAST_REGION, SOUTH_REGION)
    assert (expansion.status, expansion.significance) == (EventStatus.INFERRED, Significance.CAMPAIGN_DEFINING)
    assert expansion.open
    short = GeopoliticsSettings(expansion_gap_days=30)
    assert not only(built([*ceded, *taken], situations, short), "nation.expansion").open  # the last save is too late
    far = [*ceded, *annexation(K3, NORTH, EAST, EAST_REGION)]
    assert of_type(built(far, situations, short), "nation.expansion") == []
    assert describe_event(expansion) == (
        "Northland (nation:20) expanded over Southland (nation:21), Eastland (nation:22): 2 regions (mixed)"
    )


def test_a_cession_is_a_transfer_no_reading_or_war_explains_with_allies_as_context() -> None:
    before = situation(
        K0,
        nations=[nation_row(NORTH, federation=UNION, allies=[SOUTH]), nation_row(SOUTH, federation=UNION)],
    )
    stream = transfer(K1, SOUTH, NORTH, SOUTH_REGION)

    cession = only(built(stream, [before, situation(K1)]), "nation.cession")

    assert roles(cession) == [(Role.ACTOR, "nation:20"), (Role.BENEFICIARY, "nation:21"), (Role.LOCATION, "region:42")]
    assert (cession.attribute("allied"), cession.attribute("shared_federation")) == (True, UNION)
    assert (cession.confidence, cession.significance, cession.open) == (Confidence.MEDIUM, Significance.MAJOR, False)
    assert describe_event(cession) == "Northland (nation:20) ceded 1 region to Southland (nation:21)"


def test_no_cession_with_a_reading_a_war_between_the_two_or_an_unmatched_loss() -> None:
    at_war = [situation(K0, wars=[war_row(WAR, [SOUTH], [NORTH])]), situation(K1)]
    unmatched = [
        territory("nation.territory_gained", K1, SOUTH, [NORTH], [SOUTH_REGION]),
        territory("nation.territory_lost", K1, NORTH, [EAST], [SOUTH_REGION]),
    ]

    assert of_type(built(annexation(K1, SOUTH, NORTH, SOUTH_REGION), plain(K0, K1)), "nation.cession") == []
    assert of_type(built(transfer(K1, SOUTH, NORTH, SOUTH_REGION), at_war), "nation.cession") == []
    assert of_type(built(unmatched, plain(K0, K1)), "nation.cession") == []


# --- nation.merger -----------------------------------------------------------------------------------------------


def merged(key: str, gainer: EntityRef, absorbed: EntityRef, region: EntityRef) -> list[Event]:
    """A unification with the territory aggregates of the absorbed nation's one region."""
    return [
        unification(key, gainer, absorbed, not_before=PREVIOUS[key], unifier=RESISTANCE),
        *transfer(key, gainer, absorbed, region),
    ]


def test_a_merger_carries_the_absorbed_nations_losses_and_both_nations_changes() -> None:
    reading = merged(K1, NORTH, SOUTH, SOUTH_REGION)
    lost_executive = control(K1, "executive", RESISTANCE, None, subject=SOUTH)
    gone_point = event("control_point.disappeared", K1, POINT, entities=[SOUTH, RESISTANCE])
    alliance = event("nation.relation_changed", K1, EAST, "allies", entities=[SOUTH])
    fallen = event("nation.rank_changed", K1, SOUTH, "GDP", attributes=(("metric", "GDP"),))
    renamed = event("nation.renamed", K1, NORTH, attributes=(("before", "Northland"), ("after", "Union")))
    arsenal = shift(K1, "numNuclearWeapons", SOUTH, 2.0, 0.0)
    unrelated = [
        event("nation.rank_changed", K1, NORTH, "GDP", attributes=(("metric", "GDP"),)),
        event("nation.rank_changed", K2, SOUTH, "GDP", attributes=(("metric", "GDP"),)),
    ]
    stream = [*reading, lost_executive, gone_point, alliance, fallen, renamed, arsenal, *unrelated]

    events = built(stream, plain(K0, K1, K2))
    merger = only(events, "nation.merger")

    assert roles(merger) == [(Role.ACTOR, "nation:20"), (Role.TARGET, "nation:21"), (Role.LOCATION, "region:42")]
    assert set(merger.constituents) == {
        *(item.id for item in reading),
        lost_executive.id,
        gone_point.id,
        alliance.id,
        fallen.id,
        renamed.id,
        arsenal.id,
    }
    assert merger.attribute("absorbed") == (SOUTH,) and merger.attribute("regions") == (SOUTH_REGION,)
    assert merger.attribute("unifying_faction") == RESISTANCE
    assert shift_ids(merger) == [arsenal.id]
    assert (merger.significance, merger.open) == (Significance.MAJOR, False)
    assert of_type(events, "nation.cession") == [] and of_type(events, "faction.takeover") == []
    assert describe_event(merger) == (
        "Northland (nation:20) absorbed Southland (nation:21) by unification under Resistance (faction:15)"
    )


def test_a_merger_carries_events_skipped_by_every_rule_that_checks_its_parties() -> None:
    reading = unification(K1, NORTH, SOUTH, not_before=K0, unifier=RESISTANCE)
    armies = [
        event(
            event_type,
            K1,
            NORTH,
            event_type,
            attributes=tuple(
                [("home_nation", home)]
                + ([("deployment_type", "Standard")] if event_type in {"army.appeared", "army.disappeared"} else [])
                + ([("before", "Standard"), ("after", "Naval")] if event_type == "army.deployment_type_changed" else [])
            ),
        )
        for event_type, home in (
            ("nation.armies_changed", NORTH),
            ("army.appeared", NORTH),
            ("army.disappeared", SOUTH),
            ("army.deployment_type_changed", SOUTH),
        )
    ]
    naval = event(
        "army.appeared",
        K1,
        NORTH,
        "naval",
        attributes=(("home_nation", SOUTH), ("deployment_type", "Naval")),
    )
    nuclear_shifts = [shift(K1, "numNuclearWeapons", nation, 20.0, 25.0) for nation in (NORTH, SOUTH)]
    relations = [
        event(
            "nation.relation_changed",
            K1,
            nation,
            "allies",
            partner.entity_id.key,
            entities=[partner],
            attributes=(("relation", "allies"), ("transition", "added")),
        )
        for nation, partner in ((NORTH, EAST), (NORTH, WEST), (SOUTH, EAST), (SOUTH, WEST))
    ]
    parent = event("nation.breakaway_parent_changed", K1, SOUTH, entities=[NORTH])
    population = event(
        "nation.population_changed",
        K1,
        SOUTH,
        attributes=(("direction", "drop"), ("before", 100.0), ("after", 50.0), ("relative_change", 0.5)),
    )
    trend = event("nation.pcgdp_trend", K1, SOUTH)
    space = event(
        "nation.space_assets_changed",
        K1,
        NORTH,
        attributes=(("statistic", "boost"), ("direction", "growth"), ("before", 1.0), ("after", 2.0)),
    )
    space_defences = event(
        "nation.space_assets_changed",
        K1,
        SOUTH,
        "spaceDefences",
        attributes=(("statistic", "spaceDefences"), ("before", 0), ("after", 2)),
    )
    rank = event("nation.rank_changed", K1, SOUTH, "GDP", attributes=(("metric", "GDP"),))
    control_loss = control(K1, "executive", RESISTANCE, None, subject=SOUTH)
    release_anchor = event(
        "nation.independence",
        K2,
        SOUTH,
        entities=[NORTH],
        attributes=(("parents", (NORTH,)), ("released", True), ("releasing_nation", NORTH)),
        status=EventStatus.INFERRED,
        significance=Significance.MAJOR,
    )
    regained_control = control(K2, "executive", None, SERVANTS, subject=SOUTH, cause="Independence")
    carried = [
        *armies,
        naval,
        *nuclear_shifts,
        *relations,
        parent,
        population,
        trend,
        space,
        space_defences,
        rank,
        control_loss,
    ]

    events = built(
        [reading, *carried, release_anchor, regained_control],
        plain(K0, K1, K2),
        GeopoliticsSettings(realignment_min_partners=2),
    )
    merger = only(events, "nation.merger")

    assert {item.id for item in carried} <= set(merger.constituents)
    assert not [
        narrative
        for narrative in events
        if narrative.event_type != "nation.merger" and set(narrative.constituents) & {item.id for item in carried}
    ]


def test_an_expansion_of_mergers_is_a_unification_and_a_member_leaving_by_merger_names_its_new_nation() -> None:
    situations = [situation(key, federations=[federation_row(UNION, [NORTH, SOUTH, EAST])]) for key in (K0, K1, K2)]
    left = federation_event("federation.members_changed", K1, SOUTH, "removed")
    stayed = federation_event("federation.members_changed", K2, WEST, "removed")
    stream = [*merged(K1, NORTH, SOUTH, SOUTH_REGION), *merged(K2, NORTH, EAST, EAST_REGION), left, stayed]

    events = built(stream, situations)
    expansion = only(events, "nation.expansion")
    mergers = of_type(events, "nation.merger")

    assert set(expansion.constituents) == {merger.id for merger in mergers} and len(mergers) == 2
    assert expansion.attribute("mode") == "unification"
    assert expansion.attribute("losers") == (SOUTH, EAST)
    changes = only(events, "federation.lifecycle").attribute("member_changes")
    assert [dict(change.items).get("merged_into") for change in changes] == [NORTH, None]  # type: ignore[union-attr]


# --- nation.release / nation.breakaway ---------------------------------------------------------------------------


def independence(key: str, released: bool, releasing: EntityRef | None = NORTH) -> Event:
    attributes: list[tuple[str, Observed]] = [("parents", (NORTH,)), ("released", released)]
    if released:
        attributes.append(("releasing_nation", releasing))
    return event("nation.independence", key, EAST, entities=[NORTH], attributes=attributes,
                 status=EventStatus.INFERRED, significance=Significance.MAJOR)  # fmt: skip


def test_a_release_attaches_the_new_nations_control_event_within_the_window() -> None:
    anchor = independence(K1, True)
    control_after = control(K2, "executive", None, SERVANTS, subject=EAST, cause="Independence")
    parent = event("nation.breakaway_parent_changed", K1, EAST, entities=[NORTH])

    release = only(built([anchor, control_after, parent], plain(K0, K1, K2)), "nation.release")

    assert set(release.constituents) == {anchor.id, control_after.id, parent.id}
    assert roles(release) == [(Role.ACTOR, "nation:20"), (Role.BENEFICIARY, "nation:22")]
    assert release.attribute("executive_faction") == SERVANTS
    assert release.confidence is Confidence.HIGH and release.status is EventStatus.INFERRED
    assert describe_event(release) == "Northland (nation:20) released Eastland (nation:22)"
    later = control(K3, "executive", None, SERVANTS, subject=EAST, cause="Independence")
    situations = plain(K0, K1, K2, K3)
    assert later.id in only(built([anchor, later], situations), "nation.release").constituents
    narrow = built([anchor, later], situations, GeopoliticsSettings(release_window_days=30))
    assert only(narrow, "nation.release").constituents == (anchor.id,)


def test_a_release_after_a_merger_does_not_repeat_the_mergers_constituents() -> None:
    merger = unification(K1, NORTH, EAST, not_before=K0, unifier=RESISTANCE)
    lost_control = control(K1, "executive", SERVANTS, None, subject=EAST)
    parent = event("nation.breakaway_parent_changed", K1, EAST, entities=[NORTH])
    anchor = event(
        "nation.independence",
        K2,
        EAST,
        entities=[NORTH],
        attributes=(("parents", (NORTH,)), ("released", True), ("releasing_nation", NORTH)),
        status=EventStatus.INFERRED,
        significance=Significance.MAJOR,
    )
    regained_control = control(K2, "executive", None, SERVANTS, subject=EAST, cause="Independence")

    events = built([merger, lost_control, parent, anchor, regained_control], plain(K0, K1, K2))
    release = only(events, "nation.release")
    merger_event = only(events, "nation.merger")

    assert set(release.constituents) == {anchor.id, regained_control.id}
    assert set(release.constituents).isdisjoint(merger_event.constituents)
    assert release.id == f"nation.release/nation:22@{K2}"
    assert release.intervals == (K2,)


def test_a_breakaway_names_the_parents_and_is_open_while_the_window_reaches_past_the_last_save() -> None:
    breakaway = only(built([independence(K2, False)], plain(K0, K1, K2)), "nation.breakaway")

    assert roles(breakaway) == [(Role.ACTOR, "nation:22"), (Role.TARGET, "nation:20")]
    assert breakaway.open
    assert not only(built([independence(K1, False)], plain(K0, K1, K2, K3)), "nation.breakaway").open
    assert describe_event(breakaway) == "Eastland (nation:22) broke away from Northland (nation:20)"


# --- nation.claims_declared --------------------------------------------------------------------------------------


def claims(key: str, added: Sequence[EntityRef], owners: Sequence[EntityRef]) -> Event:
    return event(
        "nation.claims_changed",
        key,
        SOUTH,
        entities=[*added, *owners],
        attributes=(("added", tuple(added)), ("removed", ()), ("added_owners", tuple(owners))),
        significance=Significance.MAJOR,
    )


def test_claims_on_another_nations_regions_are_declared_and_on_its_own_are_not() -> None:
    declared = only(built([claims(K1, [NORTH_REGION], [NORTH])], plain(K0, K1)), "nation.claims_declared")

    assert roles(declared) == [(Role.ACTOR, "nation:21"), (Role.TARGET, "nation:20")]
    assert (declared.status, declared.significance, declared.open) == (EventStatus.OBJECTIVE, Significance.MAJOR, False)
    assert describe_event(declared) == "Southland (nation:21) claimed regions of Northland (nation:20)"
    assert of_type(built([claims(K1, [SOUTH_REGION], [SOUTH])], plain(K0, K1)), "nation.claims_declared") == []
    assert of_type(built([claims(K1, [], [])], plain(K0, K1)), "nation.claims_declared") == []


# --- Across rules ------------------------------------------------------------------------------------------------


def scenario() -> tuple[list[Event], list[SituationReport]]:
    """One stream that builds every geopolitical type, each with at least one metric shift."""
    sides = war_row(WAR, [NORTH], [SOUTH, EAST])
    situations = [
        situation(K0, wars=[sides], federations=[federation_row(UNION, [NORTH])]),
        situation(K1, wars=[sides], federations=[federation_row(UNION, [NORTH, WEST])]),
        situation(K2, wars=[sides], federations=[federation_row(UNION, [NORTH, WEST])]),
        situation(K3, federations=[federation_row(UNION, [NORTH, WEST])]),
    ]
    stream = [
        control(K1, "executive", RESISTANCE, SERVANTS, subject=WEST),
        shift(K1, "democracy", WEST),
        *annexation(K1, NORTH, SOUTH, SOUTH_REGION),
        *annexation(K2, NORTH, EAST, EAST_REGION),
        shift(K2, "GDP", NORTH),
        shift(K2, "GDP", SOUTH),
        war_event("war.disappeared", K3),
        federation_event("federation.members_changed", K1, WEST),
        *transfer(K3, WEST, SOUTH, ref(EntityDomain.REGION, "44")),
        shift(K3, "unrest", WEST),
        independence(K3, False),
        shift(K3, "cohesion", EAST),
        claims(K3, [NORTH_REGION], [NORTH]),
        shift(K3, "GDP", SOUTH),
        shift(K1, "cohesion", ref(EntityDomain.NATION, "24", "Farland")),
        shift(K1, "unrest", ref(EntityDomain.NATION, "24", "Farland")),
    ]
    return stream, situations


def test_every_geopolitical_type_is_built_and_carries_metric_shifts() -> None:
    stream, situations = scenario()

    events = built(stream, situations)

    by_type = {item.event_type: item for item in events}
    assert set(by_type) == {
        "faction.takeover",
        "war.arc",
        "federation.lifecycle",
        "nation.expansion",
        "nation.cession",
        "nation.breakaway",
        "nation.claims_declared",
    }
    for item in events:
        assert shift_ids(item), item.event_type


def test_traceability_holds_and_the_result_does_not_depend_on_stream_order() -> None:
    stream, situations = scenario()
    events = built(stream, situations)
    visible = {item.id: item for item in [*stream, *events]}

    for item in events:
        assert item.is_narrative
        assert all(constituent in visible for constituent in item.constituents)
        assert all(shift_id in {event.id for event in stream} for shift_id in shift_ids(item))
        assert set(item.sources) >= {source for c in item.constituents for source in visible[c].sources}
        assert set(shift_ids(item)).isdisjoint(item.constituents)
    assert built(list(reversed(stream)), situations) == events


def test_the_alien_administrations_claims_are_not_declared() -> None:
    stream = [claims(K1, [NORTH_REGION], [NORTH])]

    alien = plain(K0, K1, nations=[nation_row(SOUTH, alien=True)])
    assert of_type(built(stream, alien), "nation.claims_declared") == []
    human = plain(K0, K1, nations=[nation_row(SOUTH)])
    assert len(of_type(built(stream, human), "nation.claims_declared")) == 1
