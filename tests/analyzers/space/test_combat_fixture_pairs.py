"""Acceptance over the combat-log fixture pair: one event per entry added or removed, interval dates, provenance."""

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import ALL_ANALYZERS, SPACE_ANALYZERS, run_analyzers
from tinarrative.analyzers.common import FACTION_KINDS
from tinarrative.analyzers.render import describe_event
from tinarrative.model.events import Confidence, DateBasis, Event
from tinarrative.model.values import FrozenMap, Observed

PAIR = ("combat_before.json", "combat_after.json")
LOG_PATH = "/gamestates/PavonisInteractive.TerraInvicta.TIFactionState/{index}/Value/CombatLogs/{entry}"


def run() -> dict[str, Event]:
    return {event.id: event for event in run_analyzers(SPACE_ANALYZERS, *fixture_pair(*PAIR))}


def test_combat_pair_yields_one_event_per_entry_added_and_removed() -> None:
    assert sorted(run()) == [
        "faction.combat_entry_removed/faction:15/1",
        "faction.combat_recorded/faction:15/1",
        "faction.combat_recorded/faction:15/2",
        "faction.combat_recorded/faction:15/3",
        "faction.combat_recorded/faction:16/0",
    ]


def test_an_added_entry_with_a_null_date_is_interval_dated_and_cites_the_entry() -> None:
    event = run()["faction.combat_recorded/faction:15/1"]
    assert (event.date, event.date_basis, event.not_before) == (
        "2032-03-01T00:00:00",
        DateBasis.INTERVAL,
        "2032-01-01T00:00:00",
    )
    assert event.attribute("recorded_on") is None
    (source,) = event.sources
    assert source.entry is not None and source.entry.path == LOG_PATH.format(index=0, entry=1)
    assert source.entry.save_id.endswith("combat_after.json")
    assert [str(ref.entity_id) for ref in event.entities] == ["faction:15", "faction:16", "faction:17"]
    sides = event.attribute("sides")
    assert isinstance(sides, tuple)
    assert [(str(faction.entity_id), hulls) for faction, hulls in sides] == [  # type: ignore[union-attr,misc]
        ("faction:16", FrozenMap((("FixtureCruiser", 1), ("FixtureEscort", 1)))),
        ("faction:17", FrozenMap((("FixtureMonitor", 1),))),
    ]
    assert str(event.attribute("hab_faction").entity_id) == "faction:17"  # type: ignore[union-attr]
    assert (event.attribute("attack_count"), event.attribute("surprising")) == (1, "No")
    assert event.confidence is Confidence.HIGH


def test_one_combat_logged_by_two_factions_and_duplicates_are_separate_events() -> None:
    events = run()
    shared = [events["faction.combat_recorded/faction:15/1"], events["faction.combat_recorded/faction:16/0"]]
    # The logging faction is an entity of its own event only, so the kinds differ by that one faction.
    assert _without_kinds(shared[0]) == _without_kinds(shared[1])
    assert [dict(event.attribute("faction_kinds").items) for event in shared] == [  # type: ignore[union-attr]
        {"faction:15": "human", "faction:16": "human", "faction:17": "human"},
        {"faction:16": "human", "faction:17": "human"},
    ]
    twins = [events[f"faction.combat_recorded/faction:15/{index}"] for index in (2, 3)]
    assert twins[0].attributes == twins[1].attributes


def _without_kinds(event: Event) -> tuple[tuple[str, Observed], ...]:
    return tuple(item for item in event.attributes if item[0] != FACTION_KINDS)


def test_a_removed_entry_is_reported_literally_from_the_earlier_save() -> None:
    event = run()["faction.combat_entry_removed/faction:15/1"]
    assert event.date_basis is DateBasis.INTERVAL
    assert str(event.attribute("winner").entity_id) == "faction:16"  # type: ignore[union-attr]
    (source,) = event.sources
    assert source.entry is not None and source.entry.path == LOG_PATH.format(index=0, entry=1)
    assert source.entry.save_id.endswith("combat_before.json")


def test_lines_name_sides_and_winner_but_never_design_or_hull_names() -> None:
    events = run_analyzers(ALL_ANALYZERS, *fixture_pair(*PAIR))
    lines = sorted(describe_event(event) for event in events)
    assert lines == [
        "Fixture Aliens (faction:16) records a combat entry (undated): Fixture Aliens "
        "(faction:16) (2 ships) vs Fixture Servants (faction:17) (1 ship); "
        "winner Fixture Aliens (faction:16), hab faction Fixture Servants (faction:17), attacks 1",
        "Fixture Resistance (faction:15) no longer lists a combat entry (undated): Fixture "
        "Resistance (faction:15) (1 ship) vs Fixture Aliens (faction:16) (1 ship); "
        "winner Fixture Aliens (faction:16), hab faction null, attacks 0",
        "Fixture Resistance (faction:15) records a combat entry (undated): Fixture Aliens "
        "(faction:16) (2 ships) vs Fixture Servants (faction:17) (1 ship); "
        "winner Fixture Aliens (faction:16), hab faction Fixture Servants (faction:17), attacks 1",
        "Fixture Resistance (faction:15) records a combat entry (undated): Fixture Resistance (faction:15) (1 ship); "
        "winner Fixture Resistance (faction:15), hab faction null, attacks 0",
        "Fixture Resistance (faction:15) records a combat entry (undated): Fixture Resistance (faction:15) (1 ship); "
        "winner Fixture Resistance (faction:15), hab faction null, attacks 0",
    ]
    text = " ".join(lines)
    assert "Fixture Design" not in text and "FixtureEscort" not in text
