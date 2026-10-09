"""Fixture-driven coverage of ``normalize``: metadata, entity collections, research, references, provenance."""

import json
from datetime import datetime

import pytest

from tests.fixtures import fixture_path
from tinarrative.identity import STATE_PREFIX
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.snapshot import EntityState, ResearchState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason
from tinarrative.parsing.errors import UnsupportedSaveShapeError
from tinarrative.parsing.fields import ENTITY_FIELDS, NORMALIZED_DOMAINS, RESEARCH_STATE_TYPE
from tinarrative.parsing.normalization import game_datetime, normalize
from tinarrative.parsing.raw_save import RawSave

FIXTURE_SET = ("io", "terra_invicta_json_v1")


def load(name: str) -> SaveSnapshot:
    return normalize(load_raw_save(fixture_path(*FIXTURE_SET, name)))


def fragment(gamestates: dict[str, object]) -> SaveSnapshot:
    root: dict[str, object] = {"currentID": {"value": 1}, "gamestates": gamestates}
    return normalize(
        RawSave(source="fragment.json", format="terra_invicta_json_v1", game_version=None, root=root, size_bytes=1)
    )


def by_id(states: tuple[EntityState, ...], key: str) -> EntityState:
    return next(state for state in states if state.ref.entity_id.key == key)


def ref(domain: EntityDomain, key: str, state_type: str) -> EntityRef:
    return EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, state_type=state_type)


def tech_ref(name: str) -> EntityRef:
    return EntityRef(
        EntityId(EntityDomain.TECHNOLOGY, name), IdentityConfidence.NAME_KEY, state_type=RESEARCH_STATE_TYPE, name=name
    )


def unresolved(map_id: int, type_suffix: str | None = None) -> Unknown:
    raw: dict[str, object] = {"value": map_id}
    if type_suffix:
        raw["$type"] = STATE_PREFIX + type_suffix
    return Unknown(UnknownReason.UNRESOLVED_REFERENCE, FrozenMap(tuple(sorted(raw.items()))))


ATTRIBUTE_TYPES: dict[str, dict[str, EntityDomain]] = {}
for _domain, _short_type, _attribute in NORMALIZED_DOMAINS:
    ATTRIBUTE_TYPES.setdefault(_attribute, {})[_short_type] = _domain


@pytest.fixture(scope="module")
def political() -> SaveSnapshot:
    return load("political_control.json")


@pytest.fixture(scope="module")
def assets() -> SaveSnapshot:
    return load("campaign_assets.json")


@pytest.mark.fixture
def test_campaign_time_and_metadata_are_extracted(political: SaveSnapshot) -> None:
    assert political.timestamp == datetime(2031, 3, 1)
    assert political.date == "2031-03-01T00:00:00"
    assert political.campaign_day == 425
    assert political.campaign_quarter == 4
    assert political.game_version is None
    assert political.campaign.player_faction_name == "Fixture Resistance"
    assert political.campaign.difficulty == "Normal"
    assert political.campaign.played_with_mods is False
    assert political.campaign.game_time_string == "3/1/2031 12:00:00 AM"
    assert political.campaign.scenario_master_template == "FixtureMaster"
    assert political.campaign.scenario_template == "FixtureScenario"
    assert dict(political.raw_metadata)["current_id"] == 999
    state_types = dict(political.raw_metadata)["state_types"]
    assert isinstance(state_types, tuple) and STATE_PREFIX + "TIFixtureUnknownState" in state_types


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("fixture_name", "expected_counts"),
    [
        (
            "political_control.json",
            {"factions": 2, "nations": 2, "regions": 3, "control_points": 4, "councilors": 0, "armies": 2},
        ),
        (
            "campaign_assets.json",
            {
                "factions": 2,
                "nations": 1,
                "regions": 2,
                "councilors": 3,
                "armies": 3,
                "fleets": 2,
                "ships": 3,
                "habs": 2,
            },
        ),
    ],
)
def test_collections_are_typed_sorted_and_carry_provenance(fixture_name: str, expected_counts: dict[str, int]) -> None:
    snapshot = load(fixture_name)
    counts = {attribute: len(getattr(snapshot, attribute)) for attribute in ATTRIBUTE_TYPES}
    assert {attribute: counts[attribute] for attribute in expected_counts} == expected_counts
    for attribute, state_types in ATTRIBUTE_TYPES.items():
        states: tuple[EntityState, ...] = getattr(snapshot, attribute)
        assert [state.ref.entity_id for state in states] == sorted(state.ref.entity_id for state in states)
        positions: dict[str, int] = dict.fromkeys(state_types, 0)
        for state in states:
            short_type = state.ref.state_type
            assert short_type in state_types
            assert state.ref.entity_id.domain is state_types[short_type]
            assert state.ref.confidence is IdentityConfidence.IN_SAVE_ID
            assert state.location is not None
            assert state.location.save_id == snapshot.source
            assert state.location.provenance_key == f"{short_type}:{state.ref.entity_id.key}"
            assert state.location.path == f"/gamestates/{STATE_PREFIX}{short_type}/{positions[short_type]}/Value"
            positions[short_type] += 1
            assert {name for name, _ in state.fields} == set(ENTITY_FIELDS[short_type])


@pytest.mark.fixture
def test_control_point_ownership_is_copied_not_invented(political: SaveSnapshot) -> None:
    owned = by_id(political.control_points, "30")
    assert owned.get("nation") == ref(EntityDomain.NATION, "20", "TINationState")
    assert owned.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert owned.get("defended") is True
    assert isinstance(owned.get("crackdownExpiration"), FrozenMap)
    assert owned.ref.name == "Fixture CP 30"

    unowned = by_id(political.control_points, "31")
    assert unowned.get("faction") is None
    assert unowned.get("crackdownExpiration") is None

    missing_field = by_id(political.control_points, "32")
    assert missing_field.get("defended") == Unknown()
    assert missing_field.get("faction") == ref(EntityDomain.FACTION, "11", "TIFactionState")

    dangling = by_id(political.control_points, "33")
    assert dangling.get("nation") == Unknown(UnknownReason.UNRESOLVED_REFERENCE, FrozenMap((("value", 999),)))
    assert dangling.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")


@pytest.mark.fixture
def test_nation_and_region_references_resolve_through_documented_domains(political: SaveSnapshot) -> None:
    north = by_id(political.nations, "20")
    assert north.get("capital") == ref(EntityDomain.REGION, "40", "TIRegionState")
    assert north.get("regions") == (
        ref(EntityDomain.REGION, "40", "TIRegionState"),
        ref(EntityDomain.REGION, "41", "TIRegionState"),
    )
    assert north.get("allies") == (ref(EntityDomain.NATION, "21", "TINationState"),)
    assert north.get("rivals") == ()
    assert north.get("controlPoints") == (
        ref(EntityDomain.CONTROL_POINT, "30", "TIControlPoint"),
        ref(EntityDomain.CONTROL_POINT, "31", "TIControlPoint"),
    )
    assert north.get("armies") == (ref(EntityDomain.ARMY, "50", "TIArmyState"),)
    assert north.get("federation") is None
    assert north.get("GDP") == 1000.0
    assert north.get("fixtureOnlyUndocumentedField") == Unknown()  # undocumented fields are ignored
    assert "fixtureOnlyUndocumentedField" not in dict(north.fields)

    south = by_id(political.nations, "21")
    assert south.get("capital") is None
    assert south.get("federation") == FrozenMap((("value", 80),))  # target type has no domain: kept raw

    region = by_id(political.regions, "42")
    assert region.get("nation") == ref(EntityDomain.NATION, "21", "TINationState")
    assert region.get("armies") == (ref(EntityDomain.ARMY, "51", "TIMegafaunaArmyState"),)
    assert region.get("alienFacility") == FrozenMap((("value", 70),))
    assert region.get("leadOccupier") is None

    faction = by_id(political.factions, "10")
    assert faction.get("controlPoints") == tuple(
        ref(EntityDomain.CONTROL_POINT, key, "TIControlPoint") for key in ("30", "31", "33")
    )
    assert faction.get("player") == FrozenMap((("value", 60),))
    assert faction.get("resources") == FrozenMap((("Influence", 2.5), ("Money", 10.0)))


@pytest.mark.fixture
def test_normalization_is_deterministic_and_json_serializable(political: SaveSnapshot) -> None:
    assert political == load("political_control.json")
    data = political.to_dict()
    assert json.loads(json.dumps(data)) == data
    dangling = next(item for item in data["control_points"] if item["id"] == "control point:33")
    assert dangling["fields"]["nation"] == {"unknown": "unresolved_reference", "raw": {"value": 999}}
    assert dangling["location"]["state_type"] == "TIControlPoint"


@pytest.mark.fixture
def test_representative_fixture_without_observed_time_fields_has_unknown_chronology() -> None:
    snapshot = load("representative_campaign.json")
    assert snapshot.date == Unknown()
    assert snapshot.timestamp is None
    assert snapshot.campaign_day == Unknown()
    assert snapshot.campaign.player_faction_name == "Fixture Resistance"
    assert snapshot.campaign.scenario_template == Unknown()
    assert (len(snapshot.factions), len(snapshot.nations), snapshot.regions, snapshot.control_points) == (1, 1, (), ())
    assert by_id(snapshot.nations, "4").get("templateName") == Unknown()


def test_empty_gamestates_give_an_empty_snapshot() -> None:
    snapshot = fragment({})
    assert snapshot.date == Unknown()
    assert snapshot.campaign.difficulty == Unknown()
    assert all(getattr(snapshot, attribute) == () for _, _, attribute in NORMALIZED_DOMAINS)
    assert snapshot.technologies == ()
    assert snapshot.research == ResearchState()


@pytest.mark.fixture
def test_councilors_carry_membership_location_and_unknowns(assets: SaveSnapshot) -> None:
    affiliated = by_id(assets.councilors, "100")
    assert affiliated.ref.name == "Fixture Councilor 100"
    assert affiliated.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert affiliated.get("location") == ref(EntityDomain.REGION, "40", "TIRegionState")
    assert affiliated.get("homeRegion") == ref(EntityDomain.REGION, "40", "TIRegionState")
    assert affiliated.get("orgs") == (ref(EntityDomain.ORGANIZATION, "70", "TIOrgState"),)
    assert affiliated.get("status") == "Available"
    assert affiliated.get("XP") == 12
    assert affiliated.get("agentForFaction") is None
    assert affiliated.get("priorLocation") is None
    attributes = affiliated.get("attributes")
    assert isinstance(attributes, FrozenMap) and dict(attributes.items)["Loyalty"] == 5

    unaffiliated = by_id(assets.councilors, "101")
    assert unaffiliated.get("faction") is None
    assert unaffiliated.get("orgs") == ()
    assert unaffiliated.get("recruitDate") is None
    # a councilor location may be a region or a hab; the owner's domain decides
    assert unaffiliated.get("location") == ref(EntityDomain.SPACE_OBJECT, "140", "TIHabState")

    partial = by_id(assets.councilors, "102")
    assert partial.get("location") == unresolved(999, "TIRegionState")
    assert partial.get("priorLocation") == ref(EntityDomain.REGION, "41", "TIRegionState")
    assert partial.get("status") == Unknown()
    assert partial.get("XP") == Unknown()
    assert partial.get("activeMission") == FrozenMap((("value", 998),))  # mission type has no domain: raw
    assert by_id(assets.factions, "10").get("councilors") == (
        ref(EntityDomain.COUNCILOR, "100", "TICouncilorState"),
        ref(EntityDomain.COUNCILOR, "102", "TICouncilorState"),
    )


@pytest.mark.fixture
def test_armies_merge_both_state_types_and_keep_destruction_literal(
    assets: SaveSnapshot, political: SaveSnapshot
) -> None:
    assert [(state.ref.entity_id.key, state.ref.state_type) for state in assets.armies] == [
        ("110", "TIArmyState"),
        ("111", "TIArmyState"),
        ("112", "TIMegafaunaArmyState"),
    ]
    active = by_id(assets.armies, "110")
    assert active.get("currentRegion") == ref(EntityDomain.REGION, "40", "TIRegionState")
    assert active.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert active.get("strength") == 3.5
    assert active.get("destroyed") is False
    assert active.get("destinationQueue") == ()
    assert active.get("operationTarget") is None
    assert "bonusTechLevel" not in dict(active.fields)

    assert by_id(assets.armies, "111").get("destroyed") is True

    megafauna = by_id(assets.armies, "112")
    assert megafauna.ref.entity_id.domain is EntityDomain.ARMY
    assert megafauna.get("bonusTechLevel") == 1.5
    assert megafauna.get("currentRegion") == unresolved(999)
    assert megafauna.get("faction") == ref(EntityDomain.FACTION, "11", "TIFactionState")

    # metadata-only entries normalize with every domain field unknown rather than failing
    bare = by_id(political.armies, "50")
    assert bare.get("templateName") == "FixtureArmy"
    assert all(bare.get(name) == Unknown() for name in ("currentRegion", "faction", "strength", "destroyed"))


@pytest.mark.fixture
def test_fleets_keep_ship_composition_and_expose_stale_parent_ids(assets: SaveSnapshot) -> None:
    fleet = by_id(assets.fleets, "120")
    assert fleet.get("ships") == (
        ref(EntityDomain.SHIP, "130", "TISpaceShipState"),
        ref(EntityDomain.SHIP, "131", "TISpaceShipState"),
    )
    assert fleet.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert fleet.get("parentFleet") is None
    assert fleet.get("orbitState") == ref(EntityDomain.SPACE_OBJECT, "60", "TIOrbitState")
    assert fleet.get("barycenter") == ref(EntityDomain.SPACE_OBJECT, "50", "TISpaceBodyState")
    assert fleet.get("dockedLocation") == ref(EntityDomain.SPACE_OBJECT, "140", "TIHabState")
    assert fleet.get("inCombat") is False
    assert fleet.get("inAccelerationPhase") is False
    assert fleet.get("homeport") is None
    assert isinstance(fleet.get("trajectory"), FrozenMap)
    assert fleet.get("globalPosition") == FrozenMap((("x", 1.0), ("y", 2.0), ("z", 3.0)))

    merged_child = by_id(assets.fleets, "121")
    assert merged_child.get("ships") == ()
    assert merged_child.get("parentFleet") == unresolved(999)  # fleet IDs are not carried over merges
    assert merged_child.get("orbitState") is None
    assert merged_child.get("trajectory") == Unknown()
    assert by_id(assets.factions, "11").get("fleets") == (ref(EntityDomain.FLEET, "121", "TISpaceFleetState"),)


@pytest.mark.fixture
def test_ships_reference_their_fleet_and_keep_measurements(assets: SaveSnapshot) -> None:
    ship = by_id(assets.ships, "131")
    assert ship.get("fleet") == ref(EntityDomain.FLEET, "120", "TISpaceFleetState")
    assert ship.get("propellant_tons") == 100.0
    assert ship.get("currentDeltaV_kps") == 20.0
    assert ship.get("currentMass_kg") == 5000.0
    assert ship.get("kills") == ()
    assert ship.get("officers") == ()
    assert ship.get("storedFaction") is None
    assert isinstance(ship.get("lastRefitDate"), FrozenMap)
    assert ship.get("damagedSystems") == FrozenMap((("Bridge", 0.5),))
    armor = ship.get("armor")
    assert isinstance(armor, FrozenMap) and set(dict(armor.items)) == {"Nose", "Left", "Right", "Tail"}
    assert by_id(assets.ships, "130").get("lastRefitDate") is None

    orphan = by_id(assets.ships, "132")
    assert orphan.get("fleet") == unresolved(999)
    assert orphan.get("propellant_tons") == Unknown()
    assert orphan.get("kills") == ("FixtureKill",)


@pytest.mark.fixture
def test_habs_are_space_objects_with_resolved_ownership_and_docking(assets: SaveSnapshot) -> None:
    hab = by_id(assets.habs, "140")
    assert hab.ref.entity_id == EntityId(EntityDomain.SPACE_OBJECT, "140")
    assert hab.ref.state_type == "TIHabState"
    assert hab.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert hab.get("orbitState") == ref(EntityDomain.SPACE_OBJECT, "60", "TIOrbitState")
    assert hab.get("habSite") is None
    assert hab.get("dockedFleets") == (ref(EntityDomain.FLEET, "120", "TISpaceFleetState"),)
    assert hab.get("councilorsOnBoard") == (ref(EntityDomain.COUNCILOR, "101", "TICouncilorState"),)
    assert hab.get("sectors") == (FrozenMap((("value", 160),)),)  # sector type has no domain: raw
    assert hab.get("districts") is None
    assert hab.get("tier") == 1
    assert hab.get("habType") == "Station"

    site_hab = by_id(assets.habs, "141")
    assert site_hab.get("faction") == unresolved(999)
    assert site_hab.get("orbitState") is None
    assert site_hab.get("habSite") == ref(EntityDomain.SPACE_OBJECT, "61", "TIHabSiteState")
    assert site_hab.get("dockedFleets") == ()


@pytest.mark.fixture
def test_technologies_are_name_keyed_and_derived_from_the_research_singleton(assets: SaveSnapshot) -> None:
    research = assets.research
    assert research.finished_techs_names == ("FixtureTechA", "FixtureTechB", "FixtureTechC")
    assert research.finished_one_time_only_project_names == ("FixtureProject",)
    assert research.campaign_start_year == 2030
    assert isinstance(research.tech_progress, tuple) and len(research.tech_progress) == 3
    assert research.tech_progress[2] == FrozenMap((("accumulatedResearch", 1.0),))  # no name: no identity
    assert research.location is not None
    value_path = f"/gamestates/{STATE_PREFIX}{RESEARCH_STATE_TYPE}/0/Value"
    assert research.location.path == value_path
    assert research.location.provenance_key == f"{RESEARCH_STATE_TYPE}:150"

    assert [state.ref for state in assets.technologies] == [
        tech_ref("FixtureTechA"),
        tech_ref("FixtureTechB"),
        tech_ref("FixtureTechC"),
        tech_ref("FixtureTechD"),
    ]
    finished_only = by_id(assets.technologies, "FixtureTechA")
    assert finished_only.get("finished") is True
    assert finished_only.get("progress") == Unknown()
    assert finished_only.location is not None
    assert finished_only.location.path == f"{value_path}/finishedTechsNames/0"
    assert finished_only.location.map_id == 150

    both = by_id(assets.technologies, "FixtureTechB")
    assert both.get("finished") is True
    progress = both.get("progress")
    assert isinstance(progress, FrozenMap) and dict(progress.items)["techTemplateName"] == "FixtureTechB"
    assert both.location is not None and both.location.path == f"{value_path}/finishedTechsNames/1"

    in_progress = by_id(assets.technologies, "FixtureTechD")
    assert in_progress.get("finished") is False
    assert isinstance(in_progress.get("progress"), FrozenMap)
    assert in_progress.location is not None and in_progress.location.path == f"{value_path}/techProgress/1"

    data = assets.to_dict()
    assert json.loads(json.dumps(data)) == data
    tech = next(item for item in data["technologies"] if item["id"] == "technology:FixtureTechD")
    assert tech["confidence"] == "name-key"
    assert data["research"]["campaign_start_year"] == 2030


def test_malformed_research_lists_create_no_identities_but_stay_visible() -> None:
    research_state = {
        "Key": {"value": 5},
        "Value": {
            "ID": {"value": 5},
            "finishedTechsNames": "not-a-list",
            "techProgress": [{"techTemplateName": 7}, {"techTemplateName": "Dup"}, {"techTemplateName": "Dup"}],
        },
    }
    snapshot = fragment({STATE_PREFIX + RESEARCH_STATE_TYPE: [research_state]})
    assert snapshot.research.finished_techs_names == "not-a-list"
    assert snapshot.research.campaign_start_year == Unknown()
    assert [state.ref for state in snapshot.technologies] == [tech_ref("Dup")]
    assert snapshot.technologies[0].get("finished") is False
    assert snapshot.technologies[0].location is not None
    assert snapshot.technologies[0].location.path.endswith("/techProgress/1")


@pytest.mark.parametrize(
    ("components", "expected"),
    [
        (
            {"year": 2031, "month": 3, "day": 1, "hour": 4, "minute": 5, "second": 6, "millisecond": 7},
            datetime(2031, 3, 1, 4, 5, 6, 7000),
        ),
        ({"year": 2031, "month": 3, "day": 1, "hour": 0, "minute": 0, "second": 0}, datetime(2031, 3, 1)),
        ({"year": 2031, "month": 13, "day": 1, "hour": 0, "minute": 0, "second": 0, "millisecond": 0}, None),
        ({"year": "2031", "month": 3, "day": 1, "hour": 0, "minute": 0, "second": 0, "millisecond": 0}, None),
        ({"year": 2031}, None),
        ("2031-03-01T00:00:00", None),
        (None, None),
    ],
)
def test_game_datetime_accepts_only_complete_integer_components(components: object, expected: datetime | None) -> None:
    assert game_datetime(components) == expected


def test_unparseable_time_keeps_the_raw_value() -> None:
    time_state = {"Key": {"value": 2}, "Value": {"ID": {"value": 2}, "currentDateTime": {"year": 2031}}}
    snapshot = fragment({STATE_PREFIX + "TITimeState": [time_state]})
    assert snapshot.timestamp is None
    assert snapshot.date == Unknown(UnknownReason.UNPARSEABLE, FrozenMap((("year", 2031),)))


def test_malformed_normalized_container_is_rejected_as_unsupported_shape() -> None:
    bad = [{"Key": {"value": 1}, "Value": {"ID": {"value": 2}}}]
    with pytest.raises(UnsupportedSaveShapeError, match="TIControlPoint"):
        fragment({STATE_PREFIX + "TIControlPoint": bad})
