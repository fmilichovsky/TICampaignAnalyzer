"""Space and faction stakes: habs, combats and the faction stake, from snapshots and situation reports."""

from __future__ import annotations

import pytest

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    analyze,
    faction_ref,
    fleet_ref,
    only,
    record_set,
    snapshot,
    state,
)
from tinarrative.analyzers.space import CombatAnalyzer, HabAnalyzer
from tinarrative.config import DEFAULT_SETTINGS
from tinarrative.kinds import KINDS
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Event
from tinarrative.model.records import CombatEntry, RecordKind
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import FrozenMap
from tinarrative.narrative import assign_significance
from tinarrative.narrative.prominence import (
    CONTEST_RATIO,
    FLEET_SATURATION,
    HAB_FLOOR,
    HAB_SATURATION,
    contested_mass,
    dry_mass,
    hab_share,
    ship_masses,
    space_weight,
)
from tinarrative.narrative.situation import build_situation

HAB, SHIP, FLEET, FACTION = (
    EntityDomain.SPACE_OBJECT,
    EntityDomain.SHIP,
    EntityDomain.FLEET,
    EntityDomain.FACTION,
)
HUMAN, ALIEN, OTHER = faction_ref("15"), faction_ref("16"), faction_ref("17")
KG = 1_000_000.0  # one kt is 1,000,000 kg; masses below are in kt
DESIGNS = FrozenMap(
    (("HumanDesign", FrozenMap((("hullName", "HumanHull"),))), ("AlienDesign", FrozenMap((("hullName", "AlienHull"),))))
)


def factions(save: str) -> list[EntityState]:
    return [
        state(FACTION, "15", save, templateName="ResistCouncil", shipDesigns=DESIGNS),
        state(FACTION, "16", save, templateName="AlienCouncil", shipDesigns=DESIGNS),
        state(FACTION, "17", save, templateName="ProtectorateCouncil", shipDesigns=DESIGNS),
    ]


def ship(key: str, save: str, fleet: str, design: str, dry_kt: float, propellant: float = 0.0) -> EntityState:
    return state(
        SHIP,
        key,
        save,
        fleet=fleet_ref(fleet),
        templateName=design,
        currentMass_kg=dry_kt * KG + propellant * 1000,
        propellant_tons=propellant,
    )


def fleets_and_ships(save: str) -> list[EntityState]:
    """One live ship of each design: 5 kt dry each, the human one refuelled."""
    return [
        state(FLEET, "50", save, faction=HUMAN, ships=()),
        state(FLEET, "51", save, faction=ALIEN, ships=()),
        ship("60", save, "50", "HumanDesign", 5, propellant=300),
        ship("61", save, "51", "AlienDesign", 5),
    ]


def combat_world(*entries: CombatEntry) -> tuple[SaveSnapshot, SaveSnapshot]:
    def save(name: str, log: tuple[CombatEntry, ...]) -> SaveSnapshot:
        return snapshot(
            name,
            *factions(name),
            *fleets_and_ships(name),
            records=(record_set(name, HUMAN, "CombatLogs", RecordKind.COMBAT_LOG, log),),
        )

    return save(BEFORE, ()), save(AFTER, entries)


def combat(index, first, second=None, hab_faction=None):  # type: ignore[no-untyped-def]
    """Sides are ``(faction, ((design, hull, count), ...))``."""
    designs = tuple(side for side in (first, second) if side is not None)
    sides = tuple((faction, FrozenMap(())) for faction, _ in designs)
    return CombatEntry(index, None, sides, hab_faction, HUMAN, (), "No", designs)


def scored(*entries: CombatEntry) -> list[Event]:
    before, after = combat_world(*entries)
    return list(assign_significance(analyze(CombatAnalyzer(), before, after), before, after))


H, A = "HumanDesign", "AlienDesign"


def test_dry_mass_removes_the_propellant_and_needs_both_numbers() -> None:
    assert dry_mass(10_000.0, 2.0) == 8_000.0
    assert dry_mass(10_000.0, None) is None


def test_the_hab_floor_keeps_a_share_defined_with_no_human_hab() -> None:
    assert hab_share(1.0, 0.0) == 1 / HAB_FLOOR
    assert hab_share(9.0, 2.0) == 9 / HAB_FLOOR


def test_contested_mass_is_symmetric_and_caps_the_larger_side() -> None:
    assert contested_mass(10.0, 1000.0) == contested_mass(1000.0, 10.0) == 10.0 * (1 + CONTEST_RATIO)
    assert contested_mass(10.0, 15.0) == 25.0


def test_space_counts_in_proportion_to_how_far_humans_have_reached_the_saturation() -> None:
    assert space_weight(0.5, 0.0, 0.0) == 0.0
    assert space_weight(0.5, HAB_SATURATION, FLEET_SATURATION) == 0.5


def test_an_early_world_leaves_the_faction_stakes_to_earth() -> None:
    habs = [
        state(HAB, "1", AFTER, faction=ALIEN, tier=3),
        state(HAB, "2", AFTER, faction=ALIEN, tier=2),
        state(HAB, "3", AFTER, faction=HUMAN, tier=1),
        state(HAB, "4", AFTER, faction=HUMAN, tier=1),
    ]
    stakes = build_situation(snapshot(AFTER, *factions(AFTER), *habs)).faction_stakes(
        DEFAULT_SETTINGS.narrative.significance.power, 0.5
    )
    assert stakes[ALIEN.entity_id] == 0.0  # the backdrop: Earth share alone, and it holds none
    assert 0 < stakes[HUMAN.entity_id] < 0.001  # two tier-1 stations hardly count


def appeared(*habs: EntityState) -> dict[str, Event]:
    before = snapshot(BEFORE, *factions(BEFORE))
    after = snapshot(AFTER, *factions(AFTER), *habs)
    found = assign_significance(analyze(HabAnalyzer(), before, after), before, after)
    return {str(event.entities[0].entity_id): event for event in found if event.event_type == "hab.appeared"}


def test_one_tier_three_hab_outweighs_a_tier_one_hab() -> None:
    found = appeared(state(HAB, "141", AFTER, faction=HUMAN, tier=3), state(HAB, "142", AFTER, faction=HUMAN, tier=1))
    big, small = found["space object:141"], found["space object:142"]
    assert big.score > small.score
    assert big.significance_basis is not None and big.significance_basis.measure == "hab"
    assert big.significance_basis.share == pytest.approx(9 / HAB_FLOOR)  # tier² over the human total, floored


def test_alien_habs_are_measured_against_the_human_total() -> None:
    found = appeared(state(HAB, "143", AFTER, faction=ALIEN, tier=3), state(HAB, "144", AFTER, faction=HUMAN, tier=1))
    assert found["space object:143"].significance_basis is not None
    assert found["space object:143"].significance_basis.share == pytest.approx(9 / HAB_FLOOR)


def test_a_large_fleet_swatting_a_scout_ranks_below_an_equal_clash() -> None:
    swat = scored(combat(0, (HUMAN, ((H, "HumanHull", 20),)), (ALIEN, ((A, "AlienHull", 1),))))[0]
    clash = scored(combat(0, (HUMAN, ((H, "HumanHull", 10),)), (OTHER, ((H, "HumanHull", 10),))))[0]
    assert swat.score < clash.score


def test_swapping_winner_and_loser_leaves_the_score_unchanged() -> None:
    forward = scored(combat(0, (HUMAN, ((H, "HumanHull", 5),)), (ALIEN, ((A, "AlienHull", 2),))))[0]
    backward = scored(combat(0, (ALIEN, ((A, "AlienHull", 2),)), (HUMAN, ((H, "HumanHull", 5),))))[0]
    assert forward.score == backward.score


def test_alien_ships_weigh_double() -> None:
    with_alien = scored(combat(0, (HUMAN, ((H, "HumanHull", 1),)), (ALIEN, ((A, "AlienHull", 1),))))[0]
    without = scored(combat(0, (HUMAN, ((H, "HumanHull", 1),)), (OTHER, ((H, "HumanHull", 1),))))[0]
    assert with_alien.significance_basis and without.significance_basis
    assert with_alien.significance_basis.share > without.significance_basis.share


def test_a_design_with_no_live_ship_falls_back_to_its_hull_class() -> None:
    known = scored(combat(0, (HUMAN, ((H, "HumanHull", 3),)), (ALIEN, ((A, "AlienHull", 3),))))[0]
    refit = scored(combat(0, (HUMAN, (("HumanDesign Refit 1", "HumanHull", 3),)), (ALIEN, ((A, "AlienHull", 3),))))[0]
    unknown = scored(combat(0, (HUMAN, (("Gone", "NoSuchHull", 3),)), (ALIEN, ((A, "AlienHull", 3),))))[0]
    assert refit.significance_basis and known.significance_basis and unknown.significance_basis
    assert refit.significance_basis.share == known.significance_basis.share
    assert unknown.significance_basis.share < known.significance_basis.share


def test_a_one_sided_record_stays_at_base_with_a_hab_and_has_no_contest_without() -> None:
    with_hab = scored(combat(0, (HUMAN, ((H, "HumanHull", 3),)), hab_faction=ALIEN))[0]
    without = scored(combat(0, (HUMAN, ((H, "HumanHull", 3),))))[0]
    assert with_hab.significance_basis is None and with_hab.score == KINDS["faction.combat_recorded"].base.base
    assert without.significance_basis is not None and without.significance_basis.share == 0
    assert without.score < with_hab.score


def test_design_ids_never_reach_the_event() -> None:
    event = only(
        scored(combat(0, (HUMAN, ((H, "HumanHull", 3),)), (ALIEN, ((A, "AlienHull", 3),)))), "faction.combat_recorded"
    )
    assert "HumanDesign" not in repr(event.attributes) and "AlienDesign" not in repr(event.to_dict())


def test_a_design_name_reused_by_another_faction_does_not_borrow_its_mass() -> None:
    other = [
        state(FLEET, "52", AFTER, faction=OTHER, ships=()),
        ship("62", AFTER, "52", "HumanDesign", 500),
    ]
    snap = snapshot(AFTER, *factions(AFTER), *fleets_and_ships(AFTER), *other)
    masses = ship_masses(snap)
    assert masses.of(HUMAN.entity_id, "HumanDesign", "HumanHull") == 5 * KG
    assert masses.of(OTHER.entity_id, "HumanDesign", "HumanHull") == 500 * KG


def test_a_defection_is_scaled_by_the_stake_of_the_faction_left() -> None:
    from tinarrative.analyzers.politics import CouncilorAnalyzer

    def save(name: str, faction: object) -> SaveSnapshot:
        return snapshot(
            name,
            *factions(name),
            state(EntityDomain.COUNCILOR, "100", name, faction=faction, status="Active", location=None),
        )

    before, after = save(BEFORE, HUMAN), save(AFTER, ALIEN)
    found = assign_significance(analyze(CouncilorAnalyzer(), before, after), before, after)
    event = only(found, "councilor.faction_changed")
    base = KINDS["councilor.faction_changed"].base.base
    # The faction left holds nothing here (no nations, habs or ships): the lowest stake.
    assert event.significance_basis is not None and event.significance_basis.share == 0
    assert event.score == base + DEFAULT_SETTINGS.narrative.significance.scale_min
