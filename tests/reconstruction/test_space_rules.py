"""Space reconstruction: synthetic habs, fleets, destruction logs, kill lists, combat logs and notifications."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    by_type,
    faction_ref,
    fleet_ref,
    hab_ref,
    named,
    pair,
    record_set,
    snapshot,
    state,
)
from tests.reconstruction.support import Scenario, assert_traceable, lines_of, only, run
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
from tinarrative.model.values import FrozenMap
from tinarrative.reconstruction import BATTLE_OUTCOME, FIRST_HAB_ON_BODY, HAB_DESTROYED

FACTION = EntityDomain.FACTION
HAB = EntityDomain.SPACE_OBJECT
PLAYER = faction_ref("15")
ENEMY = faction_ref("16")
QUEUE_KEY = "80"
GLOBAL_KEY = "70"
ESCORTS = FrozenMap((("FixtureEscort", 2),))
IN_INTERVAL = "2031-04-10T08:30:00.125000"
LATER_IN_INTERVAL = "2031-05-02T11:00:00"

Hab = tuple[str, str, str]
"""Owning faction key, hab type and body key."""


def body(key: str) -> EntityRef:
    """A space body (``TISpaceBodyState``)."""
    return EntityRef(
        EntityId(EntityDomain.SPACE_BODY, key), IdentityConfidence.IN_SAVE_ID, state_type="TISpaceBodyState"
    )


def space_pair(
    habs_before: Mapping[str, Hab],
    habs_after: Mapping[str, Hab],
    *,
    fleets_before: Mapping[str, str] | None = None,
    fleets_after: Mapping[str, str] | None = None,
    records_before: tuple[RecordSet, ...] = (),
    records_after: tuple[RecordSet, ...] = (),
) -> Scenario:
    """Factions 15 and 16, a notification queue and the global values singleton, with the given habs and fleets."""

    def states(save: str, habs: Mapping[str, Hab], fleets: Mapping[str, str] | None) -> list[EntityState]:
        found = [
            state(FACTION, "15", save),
            state(FACTION, "16", save),
            state(EntityDomain.NOTIFICATION_QUEUE, QUEUE_KEY, save),
            state(EntityDomain.GLOBAL_VALUES, GLOBAL_KEY, save),
        ]
        for key, (faction, hab_type, place) in sorted(habs.items()):
            found.append(state(HAB, key, save, faction=faction_ref(faction), habType=hab_type, barycenter=body(place)))
        for key, faction in sorted((fleets or {}).items()):
            found.append(state(EntityDomain.FLEET, key, save, faction=faction_ref(faction)))
        return found

    return pair(
        snapshot(BEFORE, *states(BEFORE, habs_before, fleets_before), records=records_before),
        snapshot(AFTER, *states(AFTER, habs_after, fleets_after), records=records_after),
    )


def destruction_log(save: str, owner: EntityRef, *entries: DestructionEntry) -> RecordSet:
    return record_set(save, owner, "HabDestructionLog", RecordKind.DESTRUCTION_LOG, entries)


def destruction(index: int, hab_type: str, place: str, date: str, destroyer: EntityRef = PLAYER) -> DestructionEntry:
    return DestructionEntry(index, hab_type, body(place), date, destroyer)


def kills(save: str, killer: EntityRef, *victims: tuple[EntityRef, int]) -> RecordSet:
    """``Kills`` with ``count`` synthetic asset names per victim."""
    entries: tuple[RecordEntry, ...] = tuple(
        KeyedEntry(index, victim, tuple(f"Fixture asset {n}" for n in range(count)))
        for index, (victim, count) in enumerate(victims)
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


# --- Scenarios: hab destroyed -----------------------------------------------------------------------------------


def unique_destruction() -> Scenario:
    """Faction 16's Base 70 on body 900 vanishes and its log records one Base destroyed there by faction 15."""
    return space_pair(
        {"70": ("16", "Base", "900"), "71": ("16", "Station", "900")},
        {"71": ("16", "Station", "900")},
        records_before=(destruction_log(BEFORE, ENEMY),),
        records_after=(destruction_log(AFTER, ENEMY, destruction(0, "Base", "900", IN_INTERVAL)),),
    )


def ambiguous_destruction(entries: int, *, pinned: bool = False) -> Scenario:
    """Two Bases of faction 16 on body 900 vanish; the log records ``entries`` Base destructions there."""
    dates = (IN_INTERVAL, LATER_IN_INTERVAL)
    logged = tuple(destruction(index, "Base", "900", dates[index]) for index in range(entries))
    notes = (("LogHabDestroyed", LATER_IN_INTERVAL, hab_ref("73")),) if pinned else ()
    return space_pair(
        {"72": ("16", "Base", "900"), "73": ("16", "Base", "900")},
        {},
        records_before=(destruction_log(BEFORE, ENEMY), notifications(BEFORE)),
        records_after=(destruction_log(AFTER, ENEMY, *logged), notifications(AFTER, *notes)),
    )


def mismatched_destruction() -> Scenario:
    """The vanished hab is a Station and on another body than the recorded Base."""
    return space_pair(
        {"74": ("16", "Station", "900"), "75": ("16", "Base", "901")},
        {},
        records_before=(destruction_log(BEFORE, ENEMY),),
        records_after=(destruction_log(AFTER, ENEMY, destruction(0, "Base", "900", IN_INTERVAL)),),
    )


# --- Scenarios: battle outcome ----------------------------------------------------------------------------------


def battle(
    *,
    grown: int = 4,
    hab_loss: bool = True,
    fleet_loss: bool = False,
    winners: tuple[EntityRef, ...] = (),
    notified: bool = False,
    victim: EntityRef = ENEMY,
) -> Scenario:
    """Faction 15's kills against ``victim`` grow by ``grown``; faction 16 may lose hab 80 and fleet 90."""
    habs_before = {"80": ("16", "Base", "900"), "81": ("16", "Base", "901")}
    habs_after = {"81": ("16", "Base", "901")} if hab_loss else habs_before
    fleets_before = {"90": "16", "91": "15"}
    fleets_after = {"91": "15"} if fleet_loss else fleets_before
    notes = (("LogSpaceBattleTakesPlace", IN_INTERVAL, fleet_ref("91")),) if notified else ()
    return space_pair(
        habs_before,
        habs_after,
        fleets_before=fleets_before,
        fleets_after=fleets_after,
        records_before=(kills(BEFORE, PLAYER, (victim, 2)), combat_log(BEFORE, PLAYER), notifications(BEFORE)),
        records_after=(
            kills(AFTER, PLAYER, (victim, 2 + grown)),
            combat_log(AFTER, PLAYER, *winners),
            notifications(AFTER, *notes),
        ),
    )


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "new_body": new_body,
    "first_of_any_faction": first_of_any_faction,
    "unique_destruction": unique_destruction,
    "ambiguous_destruction": lambda: ambiguous_destruction(2),
    "short_destruction": lambda: ambiguous_destruction(1),
    "pinned_destruction": lambda: ambiguous_destruction(2, pinned=True),
    "battle": battle,
    "won_battle": lambda: battle(winners=(PLAYER,), fleet_loss=True),
    "notified_battle": lambda: battle(notified=True),
}


# --- faction.first_hab_on_body ----------------------------------------------------------------------------------


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
    assert [str(ref.entity_id) for ref in event.entities[:2]] == ["faction:15", "space body:900"]


def test_a_hab_on_a_body_the_faction_already_held_is_no_first_presence() -> None:
    scenario = space_pair({"50": ("15", "Base", "901")}, {"50": ("15", "Base", "901"), "55": ("15", "Station", "901")})
    objective, inferred = run(scenario)
    assert by_type(list(objective), "hab.appeared") and inferred == []


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


def test_two_entries_for_two_vanished_habs_are_medium_and_ambiguous() -> None:
    _, inferred = run(ambiguous_destruction(2))
    events = by_type(inferred, HAB_DESTROYED)
    assert [event.id for event in sorted(events, key=lambda e: e.id)] == [
        "hab.destroyed/space object:72",
        "hab.destroyed/space object:73",
    ]
    for event in events:
        assert event.confidence is Confidence.MEDIUM
        assert event.date_basis is DateBasis.INTERVAL
        assert event.attribute("ambiguous") is True
        assert (event.attribute("candidates"), event.attribute("vanished")) == (2, 2)
        assert event.attribute("recorded_dates") == (IN_INTERVAL, LATER_IN_INTERVAL)
        assert ids(event.attribute("destroyers")) == ["faction:15"]


def test_fewer_entries_than_vanished_habs_is_low() -> None:
    _, inferred = run(ambiguous_destruction(1))
    events = by_type(inferred, HAB_DESTROYED)
    assert len(events) == 2
    assert {event.confidence for event in events} == {Confidence.LOW}


def test_a_notification_naming_the_hab_on_an_entrys_date_pins_the_pair() -> None:
    _, inferred = run(ambiguous_destruction(2, pinned=True))
    by_id = {event.id: event for event in by_type(inferred, HAB_DESTROYED)}
    pinned = by_id["hab.destroyed/space object:73"]
    assert pinned.confidence is Confidence.HIGH
    assert (pinned.date, pinned.attribute("signals")) == (LATER_IN_INTERVAL, ("destruction_log", "notification"))
    assert "notification.LogHabDestroyed/notification queue:80/0" in pinned.constituents
    rest = by_id["hab.destroyed/space object:72"]  # the other hab takes the remaining entry
    assert (rest.confidence, rest.date, rest.attribute("ambiguous")) == (Confidence.HIGH, IN_INTERVAL, False)


def test_a_vanished_hab_of_another_type_or_body_is_not_joined() -> None:
    objective, inferred = run(mismatched_destruction())
    assert len(by_type(list(objective), "hab.disappeared")) == 2
    assert by_type(inferred, HAB_DESTROYED) == []


# --- faction.battle_outcome -------------------------------------------------------------------------------------


def test_kills_with_a_victim_hab_loss_are_a_medium_battle_outcome() -> None:
    _, inferred = run(battle())
    event = only(inferred, BATTLE_OUTCOME)
    assert event.id == "faction.battle_outcome/faction:15/faction:16"
    assert event.confidence is Confidence.MEDIUM
    assert (event.attribute("kill_count"), event.attribute("habs_lost"), event.attribute("fleets_lost")) == (4, 1, 0)
    assert event.attribute("signals") == ("kills", "hab_losses")
    kills_source = next(source for source in event.sources if source.change.field == "Kills")
    assert kills_source.role is SourceRole.PRIMARY and kills_source.member == ENEMY
    assert kills_source.entry is not None and kills_source.entry.path.endswith("/Kills/0")
    assert not any("Fixture asset" in str(value) for _, value in event.attributes)  # names are never copied


def test_a_combat_won_by_the_killer_raises_the_outcome_to_high() -> None:
    _, inferred = run(battle(winners=(PLAYER,), fleet_loss=True))
    event = only(inferred, BATTLE_OUTCOME)
    assert event.confidence is Confidence.HIGH
    assert (event.attribute("combats_won"), event.attribute("combats_lost"), event.attribute("fleets_lost")) == (
        1,
        0,
        1,
    )
    assert event.attribute("signals") == ("kills", "hab_losses", "fleet_losses", "combat_log")


def test_a_battle_notification_raises_the_outcome_and_supplies_its_date() -> None:
    _, inferred = run(battle(notified=True))
    event = only(inferred, BATTLE_OUTCOME)
    assert event.confidence is Confidence.HIGH
    assert event.attribute("battle_dates") == (IN_INTERVAL,)


def test_a_battle_notification_does_not_raise_an_outcome_the_combat_log_says_the_victim_won() -> None:
    _, inferred = run(battle(notified=True, winners=(ENEMY,)))
    event = only(inferred, BATTLE_OUTCOME)
    assert event.confidence is Confidence.MEDIUM
    assert (event.attribute("combats_won"), event.attribute("combats_lost")) == (0, 1)


def test_kills_without_a_victim_loss_are_no_battle_outcome() -> None:
    _, inferred = run(battle(hab_loss=False))
    assert by_type(inferred, BATTLE_OUTCOME) == []


def test_a_battle_outcome_names_the_victim_in_its_entities_and_attribute() -> None:
    _, inferred = run(battle())
    event = only(inferred, BATTLE_OUTCOME)
    victim = event.attribute("victim")
    assert isinstance(victim, EntityRef) and victim.entity_id == ENEMY.entity_id and victim.name is not None
    assert all(ref.name is not None for ref in event.entities)
    assert len({ref.entity_id for ref in event.entities}) == len(event.entities)


def test_kills_keyed_by_the_killer_itself_are_no_battle_outcome() -> None:
    _, inferred = run(battle(victim=PLAYER))
    assert by_type(inferred, BATTLE_OUTCOME) == []


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
        f'Fixture space object 70 (space object:70) (type "Base" at space body:900) was '
        f"destroyed by Fixture faction 15 (faction:15) on {IN_INTERVAL}",
        Significance.MAJOR,
    )
    assert lines_of(ambiguous_destruction(2))["hab.destroyed/space object:72"][0] == (
        'Fixture space object 72 (space object:72) (type "Base" at space body:900) was '
        "destroyed by Fixture faction 15 (faction:15): "
        "one of 2 recorded destructions for 2 vanished habs"
    )
    assert lines_of(battle(winners=(PLAYER,)))["faction.battle_outcome/faction:15/faction:16"] == (
        "Fixture faction 15 (faction:15) inflicted 4 kills on Fixture faction 16 (faction:16), "
        "which lost 1 hab; recorded combats won 1, lost 0",
        Significance.MAJOR,
    )
