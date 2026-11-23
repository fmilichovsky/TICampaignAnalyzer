"""Space reconstruction: synthetic habs, fleets, destruction logs, kill lists, combat logs and notifications."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

import pytest

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    by_type,
    faction_ref,
    fleet_ref,
    named,
    pair,
    ranked,
    record_set,
    snapshot,
    state,
)
from tests.reconstruction.support import Scenario, assert_traceable, lines_of, only, run
from tinarrative.kinds import describe_event
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Significance, SourceRole
from tinarrative.model.records import (
    CombatEntry,
    DestructionEntry,
    KeyedEntry,
    NotificationEntry,
    RecordEntry,
    RecordKind,
    RecordSet,
)
from tinarrative.model.snapshot import EntityState
from tinarrative.model.values import FrozenMap, Observed
from tinarrative.reconstruction import FIRST_HAB_ON_BODY, HAB_DESTROYED, HAB_ESTABLISHED, SPACE_LOSSES

FACTION = EntityDomain.FACTION
HAB = EntityDomain.SPACE_OBJECT
PLAYER = faction_ref("15")
ENEMY = faction_ref("16")
THIRD = faction_ref("17")
QUEUE_KEY = "80"
GLOBAL_KEY = "70"
ESCORTS = FrozenMap((("FixtureEscort", 2),))
IN_INTERVAL = "2031-04-10T08:30:00.125000"
LATER_IN_INTERVAL = "2031-05-02T11:00:00"
BEFORE_INTERVAL = "2031-01-15T00:00:00"
AFTER_INTERVAL = "2031-08-20T00:00:00"

Core = Mapping[str, Observed]
"""A hab's ``anyCoreCompleted`` and ``core*`` fields."""
WORKING: Core = {"anyCoreCompleted": True}
"""A working core, the default: no dates (a hab created from a template)."""
PENDING: Core = {
    "anyCoreCompleted": False,
    "coreConstructionCompleted": False,
    "coreStartBuildDate": "2031-07-30T00:00:00",
    "coreCompletionDate": AFTER_INTERVAL,
    "corePriorCompletionDate": None,
}
"""A launched core still in transit: projected to arrive and complete after the later save."""


def built(completion: str, *, upgrade: str | None = None, prior: str | None = None) -> Core:
    """A core completed on ``completion``; with ``upgrade`` it is being replaced, due then (``prior`` is set)."""
    return {
        "anyCoreCompleted": True,
        "coreConstructionCompleted": upgrade is None,
        "coreStartBuildDate": "2031-03-20T00:00:00",
        "coreCompletionDate": completion if upgrade is None else upgrade,
        "corePriorCompletionDate": completion if upgrade is not None else prior,
    }


Ship = tuple[str, str | None]
"""A ship's fleet key and, optionally, its display name (ships share names in the game)."""

Hab = tuple[str, str, str | EntityRef] | tuple[str, str, str | EntityRef, Core]
"""Owning faction key, hab type, body key (or another place) and, optionally, the core (``WORKING`` by default)."""


def body(key: str) -> EntityRef:
    """A space body (``TISpaceBodyState``)."""
    return EntityRef(
        EntityId(EntityDomain.SPACE_BODY, key), IdentityConfidence.IN_SAVE_ID, state_type="TISpaceBodyState"
    )


def lagrange(key: str) -> EntityRef:
    """A Lagrange point (``TILagrangePointState``), named as ``space_pair(lagrange_points=...)`` builds it."""
    return EntityRef(
        EntityId(HAB, key), IdentityConfidence.IN_SAVE_ID, state_type="TILagrangePointState", name=f"Fixture L{key}"
    )


def space_pair(
    habs_before: Mapping[str, Hab],
    habs_after: Mapping[str, Hab],
    *,
    lagrange_points: tuple[str, ...] = (),
    fleets_before: Mapping[str, str] | None = None,
    fleets_after: Mapping[str, str] | None = None,
    ships_before: Mapping[str, Ship] | None = None,
    ships_after: Mapping[str, Ship] | None = None,
    records_before: tuple[RecordSet, ...] = (),
    records_after: tuple[RecordSet, ...] = (),
) -> Scenario:
    """Factions 15, 16 and 17, a notification queue, the global values singleton and the given Lagrange points, habs,
    fleets and ships."""

    def states(
        save: str, habs: Mapping[str, Hab], fleets: Mapping[str, str] | None, ships: Mapping[str, Ship] | None
    ) -> list[EntityState]:
        found = [
            state(FACTION, "15", save),
            state(FACTION, "16", save),
            state(FACTION, "17", save),
            state(EntityDomain.NOTIFICATION_QUEUE, QUEUE_KEY, save),
            state(EntityDomain.GLOBAL_VALUES, GLOBAL_KEY, save),
            *(replace(state(HAB, key, save, "TILagrangePointState"), ref=lagrange(key)) for key in lagrange_points),
        ]
        for key, hab in sorted(habs.items()):
            faction, hab_type, place = hab[:3]
            core = hab[3] if len(hab) == 4 else WORKING
            where = place if isinstance(place, EntityRef) else body(place)
            fields = {"faction": faction_ref(faction), "habType": hab_type, "barycenter": where, **core}
            found.append(state(HAB, key, save, **fields))
        for key, faction in sorted((fleets or {}).items()):
            found.append(state(EntityDomain.FLEET, key, save, faction=faction_ref(faction)))
        for key, (fleet, name) in sorted((ships or {}).items()):
            ship = state(EntityDomain.SHIP, key, save, fleet=fleet_ref(fleet))
            found.append(ship if name is None else replace(ship, ref=replace(ship.ref, name=name)))
        return found

    return pair(
        snapshot(BEFORE, *states(BEFORE, habs_before, fleets_before, ships_before), records=records_before),
        snapshot(AFTER, *states(AFTER, habs_after, fleets_after, ships_after), records=records_after),
    )


def destruction_log(save: str, owner: EntityRef, *entries: DestructionEntry) -> RecordSet:
    return record_set(save, owner, "HabDestructionLog", RecordKind.DESTRUCTION_LOG, entries)


def destruction(index: int, hab_type: str, place: str, date: str, destroyer: EntityRef = PLAYER) -> DestructionEntry:
    return DestructionEntry(index, hab_type, body(place), date, destroyer)


def kills(save: str, killer: EntityRef, *victims: tuple[EntityRef, tuple[str, ...]]) -> RecordSet:
    """``Kills`` listing the given display names per victim."""
    entries: tuple[RecordEntry, ...] = tuple(
        KeyedEntry(index, victim, names) for index, (victim, names) in enumerate(victims)
    )
    return record_set(save, killer, "Kills", RecordKind.REFERENCE_VALUES, entries)


def combat_log(save: str, owner: EntityRef, *winners: EntityRef) -> RecordSet:
    entries: tuple[RecordEntry, ...] = tuple(
        CombatEntry(index, None, ((PLAYER, ESCORTS), (ENEMY, ESCORTS)), None, winner, (), "No")
        for index, winner in enumerate(winners)
    )
    return record_set(save, owner, "CombatLogs", RecordKind.COMBAT_LOG, entries)


def notifications(save: str, *entries: tuple[str, str, EntityRef]) -> RecordSet:
    """The notification log with (template, date, subject) entries."""
    owner = state(EntityDomain.NOTIFICATION_QUEUE, QUEUE_KEY, save).ref
    decoded: tuple[RecordEntry, ...] = tuple(
        NotificationEntry(index, template, date, "Fixture summary.", "None", subject, False, (), ())
        for index, (template, date, subject) in enumerate(entries)
    )
    return record_set(save, owner, "notificationSummaryQueue", RecordKind.NOTIFICATION_LOG, decoded)


def milestones(save: str, *labels: tuple[str, EntityRef]) -> RecordSet:
    owner = state(EntityDomain.GLOBAL_VALUES, GLOBAL_KEY, save).ref
    entries: tuple[RecordEntry, ...] = tuple(
        KeyedEntry(index, label, faction) for index, (label, faction) in enumerate(labels)
    )
    return record_set(save, owner, "globalMilestones", RecordKind.LABELLED_REFERENCES, entries)


def ids(refs: object) -> list[str]:
    assert isinstance(refs, tuple)
    return [str(ref.entity_id) for ref in refs]


# --- Scenarios: first hab on a body -----------------------------------------------------------------------------


def new_body() -> Scenario:
    """Faction 15 builds two habs on body 900, where faction 16 already had one; it already held body 901."""
    return space_pair(
        {"50": ("15", "Base", "901"), "60": ("16", "Base", "900")},
        {
            "50": ("15", "Base", "901"),
            "60": ("16", "Base", "900"),
            "51": ("15", "Base", "900"),
            "52": ("15", "Station", "900"),
        },
    )


def first_of_any_faction(*, second_body: bool = False) -> Scenario:
    """Faction 15 builds the first hab of any faction on body 902 (and on 903) and records a first-base milestone."""
    after = {"53": ("15", "Base", "902")}
    if second_body:
        after["54"] = ("15", "Base", "903")
    return space_pair(
        {},
        after,
        records_before=(milestones(BEFORE),),
        records_after=(milestones(AFTER, ("FirstBaseOnMars", PLAYER), ("FirstWarship", PLAYER)),),
    )


# --- Scenarios: hab lifecycle -----------------------------------------------------------------------------------


def launched() -> Scenario:
    """Faction 15 launches hab 56 to body 904, new to every faction; its core is still in transit."""
    return space_pair({}, {"56": ("15", "Base", "904", PENDING)})


def landed(core: Core | None = None, *, held: bool = False) -> Scenario:
    """Hab 56, launched before, gets a working core on body 904; with ``held`` faction 15 also had a hab in transit
    there."""
    before: dict[str, Hab] = {"56": ("15", "Base", "904", PENDING)}
    after: dict[str, Hab] = {"56": ("15", "Base", "904", core or built(IN_INTERVAL))}
    if held:
        before["57"] = after["57"] = ("15", "Station", "904", PENDING)
    return space_pair(before, after)


# --- Scenarios: hab destroyed -----------------------------------------------------------------------------------


def destroyed_notice(date: str) -> tuple[str, str, EntityRef]:
    """A ``LogHabDestroyed`` on ``date``; its subject is the destroyer's fleet, as the game writes for stations."""
    return ("LogHabDestroyed", date, fleet_ref("95"))


def unique_destruction(*, notified: bool = False) -> Scenario:
    """Faction 16's Base 70 on body 900 vanishes and its log records one Base destroyed there by faction 15."""
    notes = (destroyed_notice(IN_INTERVAL),) if notified else ()
    return space_pair(
        {"70": ("16", "Base", "900"), "71": ("16", "Station", "900")},
        {"71": ("16", "Station", "900")},
        records_before=(destruction_log(BEFORE, ENEMY), notifications(BEFORE)),
        records_after=(
            destruction_log(AFTER, ENEMY, destruction(0, "Base", "900", IN_INTERVAL)),
            notifications(AFTER, *notes),
        ),
    )


def ambiguous_destruction(
    entries: int,
    *,
    habs: int = 2,
    mixed: bool = False,
    notified: bool = False,
    gained: Mapping[EntityRef, tuple[str, ...]] | None = None,
) -> Scenario:
    """``habs`` Bases of faction 16 on body 900 (72, 73, ...) vanish; the log records ``entries`` Base destructions
    there by faction 15, the second by faction 17 when ``mixed``; each killer's ``Kills`` against faction 16 gains
    the names in ``gained``."""
    dates = (IN_INTERVAL, LATER_IN_INTERVAL)
    destroyers = (PLAYER, THIRD if mixed else PLAYER)
    logged = tuple(destruction(index, "Base", "900", dates[index], destroyers[index]) for index in range(entries))
    notes = (destroyed_notice(LATER_IN_INTERVAL),) if notified else ()
    killers = gained or {}
    return space_pair(
        {str(72 + index): ("16", "Base", "900") for index in range(habs)},
        {},
        records_before=(
            destruction_log(BEFORE, ENEMY),
            notifications(BEFORE),
            *(kills(BEFORE, killer, (ENEMY, (OLD_KILL,))) for killer in killers),
        ),
        records_after=(
            destruction_log(AFTER, ENEMY, *logged),
            notifications(AFTER, *notes),
            *(kills(AFTER, killer, (ENEMY, (OLD_KILL, *names))) for killer, names in killers.items()),
        ),
    )


def mismatched_destruction() -> Scenario:
    """The vanished hab is a Station and on another body than the recorded Base."""
    return space_pair(
        {"74": ("16", "Station", "900"), "75": ("16", "Base", "901")},
        {},
        records_before=(destruction_log(BEFORE, ENEMY),),
        records_after=(destruction_log(AFTER, ENEMY, destruction(0, "Base", "900", IN_INTERVAL)),),
    )


# --- Scenarios: space losses -------------------------------------------------------------------------------------

OLD_KILL = "Fixture earlier kill"
HAB_73 = "Fixture space object 73"
"""The display name the fixture gives hab 73."""


def losses(
    *,
    vanished: Mapping[str, Ship] | None = None,
    gained: Mapping[EntityRef, tuple[str, ...]] | None = None,
    victim: EntityRef = ENEMY,
    merged: bool = False,
    hab_destroyed: bool = False,
) -> Scenario:
    """Faction 16's ships ``vanished`` from fleet 90 (``merged``: they move into fleet 91 and fleet 90 goes) while
    each killer's ``Kills`` list against ``victim`` gains the names in ``gained``; ``hab_destroyed`` also loses a
    hab to faction 15's destruction log."""
    ships_before = {**(vanished or {}), "60": ("90", "Fixture survivor")}
    ships_after: dict[str, Ship] = {"60": ("90", "Fixture survivor")}
    fleets_before = {"90": "16", "91": "16"}
    fleets_after = {"91": "16"} if merged else fleets_before
    if merged:
        ships_after.update({key: ("91", name) for key, (_, name) in (vanished or {}).items()})
        ships_after["60"] = ("91", "Fixture survivor")
    habs_before = {"80": ("16", "Base", "900"), "81": ("16", "Station", "901")}
    habs_after = {"81": ("16", "Station", "901")} if hab_destroyed else habs_before
    killers = {PLAYER: (), **(gained or {})}
    log_after = (destruction_log(AFTER, ENEMY, destruction(0, "Base", "900", IN_INTERVAL)),) if hab_destroyed else ()
    return space_pair(
        habs_before,
        habs_after,
        fleets_before=fleets_before,
        fleets_after=fleets_after,
        ships_before=ships_before,
        ships_after=ships_after,
        records_before=(
            *(kills(BEFORE, killer, (victim, (OLD_KILL,))) for killer in killers),
            destruction_log(BEFORE, ENEMY),
        ),
        records_after=(
            *(kills(AFTER, killer, (victim, (OLD_KILL, *names))) for killer, names in killers.items()),
            *log_after,
        ),
    )


def vanished_ships(*names: str) -> dict[str, Ship]:
    """Faction 16's ships 61, 62, ... of fleet 90 with the given display names."""
    return {str(61 + index): ("90", name) for index, name in enumerate(names)}


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "landed": landed,
    "upgraded": lambda: landed(built(IN_INTERVAL, upgrade=AFTER_INTERVAL)),
    "new_body": new_body,
    "first_of_any_faction": first_of_any_faction,
    "unique_destruction": unique_destruction,
    "ambiguous_destruction": lambda: ambiguous_destruction(2),
    "short_destruction": lambda: ambiguous_destruction(1),
    "mixed_destruction": lambda: ambiguous_destruction(2, mixed=True),
    "notified_destruction": lambda: ambiguous_destruction(2, mixed=True, notified=True),
    "kills_tied_destruction": lambda: ambiguous_destruction(2, mixed=True, gained={THIRD: (HAB_73,)}),
    "ship_losses": lambda: losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}),
    "ship_and_hab_losses": lambda: losses(
        vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}, hab_destroyed=True
    ),
}


# --- hab.established --------------------------------------------------------------------------------------------


def test_a_launch_is_a_minor_appearance_with_projected_dates_and_establishes_nothing() -> None:
    scenario = launched()
    objective, inferred = run(scenario)
    assert inferred == []
    (appeared,) = ranked(by_type(list(objective), "hab.appeared"), scenario[0], scenario[1])
    assert appeared.attribute("core_completed") is False
    assert appeared.attribute("projected_arrival") == "2031-07-30T00:00:00"
    assert appeared.attribute("projected_completion") == AFTER_INTERVAL
    assert appeared.significance is Significance.MINOR
    assert describe_event(appeared) == (
        "Fixture space object 56 (space object:56) appeared (faction Fixture faction 15 (faction:15)); "
        f"core projected to arrive 2031-07-30T00:00:00 and complete {AFTER_INTERVAL}"
    )


def test_a_completed_core_establishes_the_hab_on_its_completion_date() -> None:
    _, inferred = run(landed())
    event = only(inferred, HAB_ESTABLISHED)
    assert event.id == "hab.established/space object:56"
    assert (event.date, event.date_basis, event.confidence) == (IN_INTERVAL, DateBasis.RECORD, Confidence.HIGH)
    assert event.attribute("faction") == named(PLAYER)
    assert ids((event.attribute("body"),)) == ["space body:904"]
    assert event.constituents == ("hab.core_completed_changed/space object:56",)
    assert lines_of(landed())["hab.established/space object:56"] == (
        "Fixture space object 56 (space object:56) became operational at "
        "space body:904 (faction Fixture faction 15 (faction:15))",
        Significance.MAJOR,
    )


@pytest.mark.parametrize(
    ("core", "date"),
    [
        (built(IN_INTERVAL, upgrade=AFTER_INTERVAL), IN_INTERVAL),  # upgrade under way: the replaced core's date
        (built(LATER_IN_INTERVAL, prior=IN_INTERVAL), IN_INTERVAL),  # upgrade finished: the earlier date
        (built(BEFORE_INTERVAL), "2031-06-01T00:00:00"),  # outside the interval: interval-dated
    ],
)
def test_an_establishment_is_dated_by_the_earliest_core_completion_inside_the_interval(core: Core, date: str) -> None:
    _, inferred = run(landed(core))
    event = only(inferred, HAB_ESTABLISHED)
    basis = DateBasis.INTERVAL if date == "2031-06-01T00:00:00" else DateBasis.RECORD
    assert (event.date, event.date_basis) == (date, basis)


def test_a_hab_that_appears_with_a_working_core_is_established_by_its_appearance() -> None:
    _, inferred = run(space_pair({}, {"58": ("15", "Station", "904", built(IN_INTERVAL))}))
    event = only(inferred, HAB_ESTABLISHED)
    assert (event.date, event.constituents) == (IN_INTERVAL, ("hab.appeared/space object:58",))


# --- faction.first_hab_on_body ----------------------------------------------------------------------------------


def test_a_first_presence_waits_for_a_working_core_and_takes_its_date() -> None:
    _, inferred = run(landed(held=True))  # the hab in transit there does not count as presence
    event = only(inferred, FIRST_HAB_ON_BODY)
    assert event.id == "faction.first_hab_on_body/faction:15/space body:904"
    assert (event.date, event.date_basis) == (IN_INTERVAL, DateBasis.RECORD)
    assert event.attribute("first_of_any_faction") is True
    assert event.constituents == ("hab.core_completed_changed/space object:56",)


def test_habs_on_a_body_new_to_their_faction_are_one_high_first_presence() -> None:
    _, inferred = run(new_body())
    event = only(inferred, FIRST_HAB_ON_BODY)
    assert event.id == "faction.first_hab_on_body/faction:15/space body:900"
    assert event.confidence is Confidence.HIGH
    assert ids(event.attribute("habs")) == ["space object:51", "space object:52"]
    assert event.attribute("hab_count") == 2
    assert event.attribute("first_of_any_faction") is False  # faction 16 was there before
    assert event.attribute("milestones") == ()
    assert set(event.constituents) == {"hab.appeared/space object:51", "hab.appeared/space object:52"}
    assert event.date_basis is DateBasis.INTERVAL  # template-created cores carry no dates
    assert [str(ref.entity_id) for ref in event.entities[:2]] == ["faction:15", "space body:900"]


def test_a_hab_at_a_lagrange_point_is_established_and_a_first_presence_there() -> None:
    point = lagrange("375")
    unnamed = replace(point, name=None)  # as normalization resolves a reference; the name comes from the snapshot
    _, inferred = run(space_pair({}, {"57": ("15", "Station", unnamed)}, lagrange_points=("375",)))
    assert only(inferred, HAB_ESTABLISHED).attribute("body") == point
    first = only(inferred, FIRST_HAB_ON_BODY)
    assert first.id == "faction.first_hab_on_body/faction:15/space object:375"
    assert "first presence on Fixture L375 (space object:375)" in describe_event(first)


def test_a_hab_on_a_body_the_faction_already_held_is_no_first_presence() -> None:
    scenario = space_pair({"50": ("15", "Base", "901")}, {"50": ("15", "Base", "901"), "55": ("15", "Station", "901")})
    objective, inferred = run(scenario)
    assert by_type(list(objective), "hab.appeared") and by_type(inferred, FIRST_HAB_ON_BODY) == []


def test_a_first_base_milestone_is_cited_for_the_factions_only_first_of_any_faction() -> None:
    _, inferred = run(first_of_any_faction())
    event = only(inferred, FIRST_HAB_ON_BODY)
    assert event.attribute("first_of_any_faction") is True
    assert event.attribute("milestones") == ("FirstBaseOnMars",)  # ``FirstWarship`` names no base
    assert "campaign.global_milestone_recorded/global values:70/FirstBaseOnMars" in event.constituents
    corroborating = [source for source in event.sources if source.role is SourceRole.CORROBORATING]
    assert [source.change.field for source in corroborating] == ["globalMilestones"]


def test_a_milestone_is_not_attributed_when_the_faction_reached_two_new_bodies() -> None:
    _, inferred = run(first_of_any_faction(second_body=True))
    events = by_type(inferred, FIRST_HAB_ON_BODY)
    assert len(events) == 2
    assert all(event.attribute("milestones") == () for event in events)


# --- hab.destroyed ----------------------------------------------------------------------------------------------


def test_one_vanished_hab_and_one_matching_entry_is_a_high_destruction_dated_by_the_entry() -> None:
    _, inferred = run(unique_destruction())
    event = only(inferred, HAB_DESTROYED)
    assert event.id == "hab.destroyed/space object:70"
    assert event.confidence is Confidence.HIGH
    assert (event.date, event.date_basis) == (IN_INTERVAL, DateBasis.RECORD)
    assert event.attribute("destroyer") == named(PLAYER) and event.attribute("ambiguous") is False
    assert event.attribute("signals") == ("destruction_log",)
    assert set(event.constituents) == {
        "hab.disappeared/space object:70",
        "faction.hab_destruction_recorded/faction:16/0",
    }
    primary = [source for source in event.sources if source.role is SourceRole.PRIMARY]
    assert [source.change.entity_id for source in primary] == [EntityId(HAB, "70")]


def test_entries_naming_one_destroyer_tie_every_hab_to_it_dated_by_the_interval() -> None:
    _, inferred = run(ambiguous_destruction(2))
    events = sorted(by_type(inferred, HAB_DESTROYED), key=lambda event: event.id)
    assert [event.id for event in events] == ["hab.destroyed/space object:72", "hab.destroyed/space object:73"]
    for event in events:
        assert (event.confidence, event.attribute("ambiguous")) == (Confidence.HIGH, False)
        assert event.attribute("destroyer") == named(PLAYER)
        assert event.date_basis is DateBasis.INTERVAL
        assert event.attribute("recorded_dates") == (IN_INTERVAL, LATER_IN_INTERVAL)
    assert only(inferred, SPACE_LOSSES).attribute("habs_lost") == 2


def test_more_entries_naming_one_destroyer_than_habs_is_medium() -> None:
    _, inferred = run(ambiguous_destruction(2, habs=1))
    event = only(inferred, HAB_DESTROYED)
    assert (event.confidence, event.attribute("ambiguous")) == (Confidence.MEDIUM, False)
    assert event.attribute("destroyer") == named(PLAYER)


def test_entries_naming_several_destroyers_are_medium_and_ambiguous() -> None:
    _, inferred = run(ambiguous_destruction(2, mixed=True))
    events = by_type(inferred, HAB_DESTROYED)
    assert len(events) == 2
    for event in events:
        assert (event.confidence, event.attribute("ambiguous")) == (Confidence.MEDIUM, True)
        assert event.date_basis is DateBasis.INTERVAL
        assert (event.attribute("candidates"), event.attribute("vanished")) == (2, 2)
        assert event.attribute("recorded_dates") == (IN_INTERVAL, LATER_IN_INTERVAL)
        assert ids(event.attribute("destroyers")) == ["faction:15", "faction:17"]
    assert by_type(inferred, SPACE_LOSSES) == []


def test_fewer_entries_than_vanished_habs_is_low() -> None:
    _, inferred = run(ambiguous_destruction(1))
    events = by_type(inferred, HAB_DESTROYED)
    assert len(events) == 2
    assert {event.confidence for event in events} == {Confidence.LOW}
    assert all(event.attribute("ambiguous") is True for event in events)


def test_a_hab_name_one_destroyer_alone_gained_ties_it_to_that_destroyer() -> None:
    _, inferred = run(ambiguous_destruction(2, mixed=True, gained={THIRD: (HAB_73,)}))
    by_id = {event.id: event for event in by_type(inferred, HAB_DESTROYED)}
    tied = by_id["hab.destroyed/space object:73"]
    assert (tied.confidence, tied.attribute("ambiguous")) == (Confidence.HIGH, False)
    assert tied.attribute("destroyer") == named(THIRD)
    assert (tied.date, tied.attribute("signals")) == (LATER_IN_INTERVAL, ("destruction_log", "kills"))
    rest = by_id["hab.destroyed/space object:72"]
    assert (rest.attribute("ambiguous"), rest.attribute("vanished")) == (True, 1)


def test_a_hab_name_several_destroyers_gained_ties_it_to_none() -> None:
    _, inferred = run(ambiguous_destruction(2, mixed=True, gained={PLAYER: (HAB_73,), THIRD: (HAB_73,)}))
    assert all(event.attribute("ambiguous") is True for event in by_type(inferred, HAB_DESTROYED))


def test_a_notification_dated_like_the_entry_is_cited_as_corroboration() -> None:
    _, inferred = run(unique_destruction(notified=True))
    event = only(inferred, HAB_DESTROYED)
    assert event.confidence is Confidence.HIGH
    assert event.attribute("signals") == ("destruction_log", "notification")
    assert "notification.LogHabDestroyed/notification queue:80/0" in event.constituents


def test_a_notification_dated_like_one_entry_never_picks_a_hab() -> None:
    _, plain = run(ambiguous_destruction(2, mixed=True))
    _, notified = run(ambiguous_destruction(2, mixed=True, notified=True))
    for before, after in zip(
        sorted(by_type(plain, HAB_DESTROYED), key=lambda e: e.id),
        sorted(by_type(notified, HAB_DESTROYED), key=lambda e: e.id),
        strict=True,
    ):
        assert (after.confidence, after.attribute("ambiguous")) == (before.confidence, True)
        assert after.attribute("signals") == ("destruction_log", "notification")
        assert "notification.LogHabDestroyed/notification queue:80/0" in after.constituents


def test_a_vanished_hab_of_another_type_or_body_is_not_joined() -> None:
    objective, inferred = run(mismatched_destruction())
    assert len(by_type(list(objective), "hab.disappeared")) == 2
    assert by_type(inferred, HAB_DESTROYED) == []


# --- faction.space_losses ---------------------------------------------------------------------------------------


def test_a_vanished_ship_whose_name_the_destroyer_gained_is_a_space_loss() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha", "Beta"), gained={PLAYER: ("Alpha",)}))
    event = only(inferred, SPACE_LOSSES)
    assert event.id == "faction.space_losses/faction:15/faction:16"
    assert event.confidence is Confidence.HIGH
    assert (event.attribute("ships_lost"), event.attribute("habs_lost")) == (1, 0)
    assert ids(event.attribute("ships")) == ["ship:61"]
    kills_source = next(source for source in event.sources if source.change.field == "Kills")
    assert kills_source.role is SourceRole.PRIMARY and kills_source.member == ENEMY
    assert kills_source.entry is not None and kills_source.entry.path.endswith("/Kills/0")


def test_names_from_kills_are_never_copied_into_the_event() -> None:
    def strings(value: object) -> list[str]:
        if isinstance(value, tuple):
            return [text for item in value for text in strings(item)]
        return [value] if isinstance(value, str) else []

    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}))
    event = only(inferred, SPACE_LOSSES)
    assert not any("Alpha" in text for _, value in event.attributes for text in strings(value))


def test_a_name_gained_by_two_destroyers_is_credited_to_neither() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",), THIRD: ("Alpha",)}))
    assert by_type(inferred, SPACE_LOSSES) == []


def test_duplicate_names_tie_the_smaller_of_vanished_ships_and_gained_entries() -> None:
    twins = vanished_ships("Twin", "Twin", "Twin")
    _, inferred = run(losses(vanished=twins, gained={PLAYER: ("Twin", "Twin")}))
    assert only(inferred, SPACE_LOSSES).attribute("ships_lost") == 2
    _, inferred = run(losses(vanished=vanished_ships("Twin", "Twin"), gained={PLAYER: ("Twin", "Twin", "Twin")}))
    assert only(inferred, SPACE_LOSSES).attribute("ships_lost") == 2


def test_a_fleet_merge_with_kills_growth_is_no_space_loss() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}, merged=True))
    assert by_type(inferred, SPACE_LOSSES) == []


def test_kills_that_match_no_vanished_ship_are_no_space_loss() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("A councilor", "A megafauna army")}))
    assert by_type(inferred, SPACE_LOSSES) == []


def test_vanished_ships_nobody_names_are_credited_to_no_one() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha")))
    assert by_type(inferred, SPACE_LOSSES) == []


def test_a_hab_destroyed_by_the_destroyer_is_a_space_loss_without_any_kills() -> None:
    _, inferred = run(losses(hab_destroyed=True))
    event = only(inferred, SPACE_LOSSES)
    assert (event.attribute("ships_lost"), event.attribute("habs_lost")) == (0, 1)
    assert ids(event.attribute("habs")) == ["space object:80"]
    assert describe_event(event).endswith("destroyed 1 hab of Fixture faction 16 (faction:16)")


def test_a_hab_destroyed_by_its_own_faction_is_no_space_loss() -> None:
    scenario = space_pair(
        {"70": ("16", "Base", "900")},
        {},
        records_before=(destruction_log(BEFORE, ENEMY),),
        records_after=(destruction_log(AFTER, ENEMY, destruction(0, "Base", "900", IN_INTERVAL, ENEMY)),),
    )
    _, inferred = run(scenario)
    assert by_type(inferred, HAB_DESTROYED) and by_type(inferred, SPACE_LOSSES) == []


def test_ships_and_habs_of_one_pair_are_one_event() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}, hab_destroyed=True))
    event = only(inferred, SPACE_LOSSES)
    assert (event.attribute("ships_lost"), event.attribute("habs_lost")) == (1, 1)
    assert "1 ship and 1 hab" in describe_event(event)


def test_kills_keyed_by_the_destroyer_itself_are_ignored() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}, victim=PLAYER))
    assert by_type(inferred, SPACE_LOSSES) == []


def test_a_space_loss_names_the_victim_in_its_entities_and_attribute() -> None:
    _, inferred = run(losses(vanished=vanished_ships("Alpha"), gained={PLAYER: ("Alpha",)}))
    event = only(inferred, SPACE_LOSSES)
    victim = event.attribute("victim")
    assert isinstance(victim, EntityRef) and victim.entity_id == ENEMY.entity_id and victim.name is not None
    assert all(ref.name is not None for ref in event.entities)
    assert len({ref.entity_id for ref in event.entities}) == len(event.entities)


# --- Invariants and presentation --------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_inferred_events_cite_their_constituents_and_trace_to_the_diff(name: str) -> None:
    assert_traceable(SCENARIOS[name]())


def test_lines_name_the_reading_and_significance_ranks_it() -> None:
    assert lines_of(new_body())["faction.first_hab_on_body/faction:15/space body:900"] == (
        "Fixture faction 15 (faction:15) established its first presence on space body:900 (2 habs)",
        Significance.MAJOR,
    )
    assert lines_of(first_of_any_faction())["faction.first_hab_on_body/faction:15/space body:902"][0] == (
        "Fixture faction 15 (faction:15) established its first presence on space body:902 (1 "
        "hab, the first of any faction there)"
    )
    assert lines_of(unique_destruction())["hab.destroyed/space object:70"] == (
        f"Fixture space object 70 (space object:70) was destroyed by Fixture faction 15 (faction:15) "
        f'on {IN_INTERVAL} (type "Base" at space body:900)',
        Significance.MAJOR,
    )
    assert lines_of(ambiguous_destruction(2))["hab.destroyed/space object:72"][0] == (
        "Fixture space object 72 (space object:72) was destroyed by Fixture faction 15 (faction:15) "
        f'between {IN_INTERVAL} and {LATER_IN_INTERVAL} (type "Base" at space body:900)'
    )
    assert lines_of(ambiguous_destruction(2, mixed=True))["hab.destroyed/space object:72"][0] == (
        "Fixture space object 72 (space object:72) was destroyed by Fixture faction 15 (faction:15), Fixture "
        'faction 17 (faction:17) (type "Base" at space body:900): one of 2 recorded destructions for 2 vanished habs'
    )
    assert lines_of(SCENARIOS["ship_and_hab_losses"]())["faction.space_losses/faction:15/faction:16"] == (
        "Fixture faction 15 (faction:15) destroyed 1 ship and 1 hab of Fixture faction 16 (faction:16)",
        Significance.MAJOR,
    )
