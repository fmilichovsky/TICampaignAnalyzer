"""The catalog lines of the nation kinds that lead with the nation and the outcome."""

from __future__ import annotations

from tests.narrative.support import atomic, nation, ref
from tinarrative.kinds import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Event
from tinarrative.model.values import Observed, Unknown

K = "2032-01-01T00:00:00"
NORTH = nation("20", "Northland")
KABUL = ref(EntityDomain.REGION, "40", "Kabul")
TIRANA = ref(EntityDomain.REGION, "41", "Tirana")
ALGIERS = ref(EntityDomain.REGION, "42", "Algiers")


def line(event_type: str, *attributes: tuple[str, Observed]) -> str:
    event: Event = atomic(f"{event_type}/nation:20", K, entities=(NORTH,), attributes=attributes)
    return describe_event(event)


def test_a_nation_that_appears_or_disappears_is_named_without_the_snapshot_mechanics() -> None:
    assert line("nation.appeared", ("side", "after")) == "Northland (nation:20) appeared"
    assert line("nation.disappeared", ("side", "before")) == "Northland (nation:20) disappeared"


def test_a_claims_change_leads_with_its_counts_and_keeps_both_lists() -> None:
    added, removed = (KABUL, TIRANA), (ALGIERS,)
    assert line("nation.claims_changed", ("added", added), ("removed", removed)) == (
        "Northland (nation:20) claims list +2/-1: +[Kabul (region:40), Tirana (region:41)] -[Algiers (region:42)]"
    )
    assert line("nation.hostile_claims_changed", ("added", ()), ("removed", removed)) == (
        "Northland (nation:20) hostile claims list +0/-1: -[Algiers (region:42)]"
    )


def test_an_unresolved_claims_list_stays_a_literal_transition() -> None:
    text = line("nation.claims_changed", ("transition", "unresolved"), ("before", (KABUL,)), ("after", Unknown()))
    assert text.startswith("Northland (nation:20) claims list: [Kabul (region:40)] -> unknown")


def test_an_executive_change_leads_with_the_new_executive_and_keeps_the_date() -> None:
    resistance = ref(EntityDomain.FACTION, "15", "Resistance")
    initiative = ref(EntityDomain.FACTION, "16", "Initiative")
    changed = line(
        "nation.executive_change_recorded",
        ("new_executive", initiative),
        ("previous_executive", resistance),
        ("recorded_on", "2045-08-17"),
    )
    assert changed == (
        "Northland (nation:20) new executive Initiative (faction:16) (previously Resistance (faction:15)); "
        "change recorded 2045-08-17"
    )


def test_an_unknown_side_of_a_claims_change_is_a_question_mark_not_a_zero() -> None:
    assert line("nation.claims_changed", ("added", (KABUL,))).startswith("Northland (nation:20) claims list +1/-?:")
