"""Fixture-driven coverage of ``normalize``: metadata, entity collections, research, references, provenance."""

import json
from dataclasses import replace
from datetime import datetime

import pytest

from tests.fixtures import fixture_path
from tinarrative.diff.state_diff import compare_values, diff_states
from tinarrative.identity import STATE_PREFIX
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.changes import ChangeKind, MapDetail
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.snapshot import EntityState, ResearchState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason, freeze
from tinarrative.parsing.errors import UnsupportedSaveShapeError
from tinarrative.parsing.fields import DERIVED_FIELDS, ENTITY_FIELDS, NORMALIZED_DOMAINS, RESEARCH_STATE_TYPE
from tinarrative.parsing.normalization import game_datetime, normalize
from tinarrative.parsing.raw_save import RawSave
from tinarrative.parsing.unknowns import ShapeSummary, UnknownCollector, UnknownReport

FIXTURE_SET = ("io", "terra_invicta_json_v1")


def load(name: str) -> SaveSnapshot:
    return normalize(load_raw_save(fixture_path(*FIXTURE_SET, name)))


def fragment_raw(gamestates: dict[str, object]) -> RawSave:
    root: dict[str, object] = {"currentID": {"value": 1}, "gamestates": gamestates}
    return RawSave(source="fragment.json", format="terra_invicta_json_v1", game_version=None, root=root, size_bytes=1)


def fragment(gamestates: dict[str, object]) -> SaveSnapshot:
    return normalize(fragment_raw(gamestates))


def collect(raw: RawSave) -> tuple[SaveSnapshot, UnknownReport]:
    collector = UnknownCollector()
    snapshot = normalize(raw, collector=collector)
    return snapshot, collector.report()


def keys(report: UnknownReport) -> list[tuple[str, str, str, str]]:
    return [finding.key for finding in report.findings]


def pair(map_id: int, **members: object) -> dict[str, object]:
    return {"Key": {"value": map_id}, "Value": {"ID": {"value": map_id}, **members}}


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
                "missions": 3,
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
            assert {name for name, _ in state.fields} == {
                *ENTITY_FIELDS[short_type],
                *DERIVED_FIELDS.get(short_type, ()),
            }


@pytest.mark.fixture
def test_control_point_ownership_is_copied_not_invented(political: SaveSnapshot) -> None:
    owned = by_id(political.control_points, "30")
    assert owned.get("nation") == ref(EntityDomain.NATION, "20", "TINationState")
    assert owned.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert owned.ref.name == "Fixture CP 30"

    unowned = by_id(political.control_points, "31")
    assert unowned.get("faction") is None

    missing_field = by_id(political.control_points, "32")
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
    assert south.get("federation") == ref(EntityDomain.FEDERATION, "80", "TIFederationState")
    (federation,) = political.federations
    assert federation.get("members") == (ref(EntityDomain.NATION, "21", "TINationState"),)
    assert political.wars == ()  # serialized as an empty {} container

    region = by_id(political.regions, "42")
    assert region.get("nation") == ref(EntityDomain.NATION, "21", "TINationState")
    assert region.get("armies") == (ref(EntityDomain.ARMY, "51", "TIMegafaunaArmyState"),)
    assert region.get("leadOccupier") is None

    faction = by_id(political.factions, "10")
    assert faction.get("controlPoints") == tuple(
        ref(EntityDomain.CONTROL_POINT, key, "TIControlPoint") for key in ("30", "31", "33")
    )
    assert faction.get("player") == FrozenMap((("value", 60),))


def test_region_alien_sub_states_resolve_and_retained_scalars_are_copied() -> None:
    region = pair(
        40,
        nation={"value": 20},
        antiSpaceDefenses=True,
        boostPerYear_dekatons=1.5,
        missionControl=2,
        numSTOFighters=3,
        nuclearDetonations=0,
        underBombardment=False,
        permanentlyDecolonized=False,
        coreEconomicRegion=True,
        oilRegion=False,
        resourceRegion=True,
    )
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TINationState": [pair(20), pair(21)],
        STATE_PREFIX + "TIRegionState": [
            region,
            pair(41),
            pair(42),
        ],
        STATE_PREFIX + "TIRegionUFOCrashdownState": [pair(110, region={"value": 40})],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert [key for key in keys(report) if key[1] == "TIRegionState"] == []

    full = by_id(snapshot.regions, "40")
    # The retained alien sub-state keeps its back-reference to the region.
    crashdown = by_id(snapshot.region_alien_states, "110")
    assert crashdown.get("region") == ref(EntityDomain.REGION, "40", "TIRegionState")
    assert full.get("boostPerYear_dekatons") == 1.5
    assert full.get("numSTOFighters") == 3
    assert full.get("underBombardment") is False
    assert full.get("resourceRegion") is True

    dangling = by_id(snapshot.regions, "41")
    assert dangling.get("nuclearDetonations") == Unknown()  # omitted by the save


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
    assert snapshot.records == ()


def test_organizations_carry_resolved_references_and_scalars() -> None:
    org = pair(
        70,
        templateName="FixtureOrg",
        displayName="Fixture Org",
        assignedCouncilor={"value": 100},
        factionOrbit=None,
        homeRegion={"value": 40},
        tier=2,
        costMoney=1.5,
        orgIconPath="ignored",
    )
    gamestates: dict[str, object] = {STATE_PREFIX + "TIOrgState": [org], STATE_PREFIX + "TICouncilorState": [pair(100)]}
    snapshot, report = collect(fragment_raw(gamestates))
    state = by_id(snapshot.organizations, "70")
    assert state.ref.name == "Fixture Org"
    assert state.get("assignedCouncilor") == ref(EntityDomain.COUNCILOR, "100", "TICouncilorState")
    assert state.get("factionOrbit") is None
    assert isinstance(state.get("homeRegion"), Unknown)  # no region entity in this fragment
    assert state.get("tier") == 2
    assert report.total == 0  # the icon path is acknowledged presentation data


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
    assert partial.get("status") == Unknown()
    assert partial.get("XP") == Unknown()
    assert by_id(assets.factions, "10").get("councilors") == (
        ref(EntityDomain.COUNCILOR, "100", "TICouncilorState"),
        ref(EntityDomain.COUNCILOR, "102", "TICouncilorState"),
    )


@pytest.mark.fixture
def test_missions_resolve_their_councilor_and_cross_domain_target(assets: SaveSnapshot) -> None:
    propaganda = by_id(assets.missions, "200")
    assert propaganda.get("councilor") == ref(EntityDomain.COUNCILOR, "100", "TICouncilorState")
    assert propaganda.get("target") == ref(EntityDomain.NATION, "20", "TINationState")
    aborted = by_id(assets.missions, "201")
    assert aborted.get("target") == ref(EntityDomain.COUNCILOR, "101", "TICouncilorState")


def test_councilor_dates_are_iso_text_and_malformed_ones_are_reported() -> None:
    gamestates = {
        STATE_PREFIX + "TICouncilorState": [
            pair(100, recruitDate={"year": 2030, "month": 6, "day": 1, "hour": 0, "minute": 0, "second": 0}),
            pair(101, recruitDate={"year": 2030}),
        ]
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert by_id(snapshot.councilors, "100").get("recruitDate") == "2030-06-01T00:00:00"
    assert by_id(snapshot.councilors, "101").get("recruitDate") == Unknown(
        UnknownReason.UNPARSEABLE, FrozenMap((("year", 2030),))
    )
    assert report.total > 0


def design(name: str, **members: object) -> dict[str, object]:
    return {"dataName": name, "hullName": "FixtureHull", "friendlyName": None, **members}


def test_faction_flags_counters_orgs_and_name_keyed_ship_designs() -> None:
    faction = pair(
        10,
        unassignedOrgs=[{"value": 70}, {"value": 71}],
        shipDesigns=[design("FixtureDesignB", refitIteration=1), design("FixtureDesignA")],
    )
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TIFactionState": [faction],
        STATE_PREFIX + "TIOrgState": [pair(70), pair(71)],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert report.total == 0
    state = by_id(snapshot.factions, "10")
    # resolved like councilor ``orgs``
    org_refs = (ref(EntityDomain.ORGANIZATION, "70", "TIOrgState"), ref(EntityDomain.ORGANIZATION, "71", "TIOrgState"))
    assert state.get("unassignedOrgs") == org_refs
    designs = state.get("shipDesigns")
    assert isinstance(designs, FrozenMap)
    assert [name for name, _ in designs.items] == ["FixtureDesignA", "FixtureDesignB"]
    assert dict(designs.items)["FixtureDesignB"] == freeze(design("FixtureDesignB", refitIteration=1))


def test_missing_faction_fields_are_unknown_and_malformed_ship_designs_stay_raw() -> None:
    malformed = [design("FixtureDesignA"), design("FixtureDesignA")]  # a repeated key cannot be keyed
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TIFactionState": [pair(10), pair(11, shipDesigns=malformed), pair(12, shipDesigns=None)],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    missing = by_id(snapshot.factions, "10")
    for name in ENTITY_FIELDS["TIFactionState"]:
        assert missing.get(name) == Unknown(), name
    assert by_id(snapshot.factions, "11").get("shipDesigns") == Unknown(UnknownReason.UNPARSEABLE, freeze(malformed))
    assert by_id(snapshot.factions, "12").get("shipDesigns") == Unknown(UnknownReason.UNPARSEABLE, None)
    assert keys(report) == [("unexpected_field_shape", "TIFactionState", "shipDesigns", "array_of_keyed_objects")]
    assert report.findings[0].occurrences == 2


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
    assert "bonusTechLevel" not in dict(active.fields)

    assert by_id(assets.armies, "111").get("destroyed") is True

    megafauna = by_id(assets.armies, "112")
    assert megafauna.ref.entity_id.domain is EntityDomain.ARMY
    assert megafauna.get("currentRegion") == unresolved(999)
    assert megafauna.get("faction") == ref(EntityDomain.FACTION, "11", "TIFactionState")

    # metadata-only entries normalize with every domain field unknown rather than failing
    bare = by_id(political.armies, "50")
    assert bare.get("templateName") == "FixtureArmy"
    assert all(bare.get(name) == Unknown() for name in ("currentRegion", "faction", "strength", "destroyed"))


@pytest.mark.fixture
def test_space_bodies_are_named_reference_targets_with_a_parent() -> None:
    assets = load("assets_after.json")
    assert [str(state.ref.entity_id) for state in assets.space_bodies] == ["space body:50", "space body:51"]
    body, moon = by_id(assets.space_bodies, "50"), by_id(assets.space_bodies, "51")
    assert (body.ref.name, body.ref.state_type, body.get("templateName")) == (
        "Fixture Body",
        "TISpaceBodyState",
        "FixtureBody",
    )
    assert body.get("barycenter") is None
    assert moon.ref.name == "Fixture Moon"
    assert moon.get("barycenter") == ref(EntityDomain.SPACE_BODY, "50", "TISpaceBodyState")


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
    assert fleet.get("barycenter") == ref(EntityDomain.SPACE_BODY, "50", "TISpaceBodyState")
    assert fleet.get("dockedLocation") == ref(EntityDomain.SPACE_OBJECT, "140", "TIHabState")
    assert fleet.get("inCombat") is False

    merged_child = by_id(assets.fleets, "121")
    assert merged_child.get("ships") == ()
    assert merged_child.get("parentFleet") == unresolved(999)  # fleet IDs are not carried over merges
    assert merged_child.get("orbitState") is None
    assert by_id(assets.factions, "11").get("fleets") == (ref(EntityDomain.FLEET, "121", "TISpaceFleetState"),)


@pytest.mark.fixture
def test_ships_reference_their_fleet_and_keep_measurements(assets: SaveSnapshot) -> None:
    ship = by_id(assets.ships, "131")
    assert ship.get("fleet") == ref(EntityDomain.FLEET, "120", "TISpaceFleetState")
    assert ship.get("kills") == ()
    assert isinstance(ship.get("lastRefitDate"), FrozenMap)
    assert by_id(assets.ships, "130").get("lastRefitDate") is None

    orphan = by_id(assets.ships, "132")
    assert orphan.get("fleet") == unresolved(999)
    assert orphan.get("kills") == ("FixtureKill",)


@pytest.mark.fixture
def test_habs_are_space_objects_with_resolved_ownership_and_docking(assets: SaveSnapshot) -> None:
    hab = by_id(assets.habs, "140")
    assert hab.ref.entity_id == EntityId(EntityDomain.SPACE_OBJECT, "140")
    assert hab.ref.state_type == "TIHabState"
    assert hab.get("faction") == ref(EntityDomain.FACTION, "10", "TIFactionState")
    assert hab.get("orbitState") == ref(EntityDomain.SPACE_OBJECT, "60", "TIOrbitState")
    assert hab.get("dockedFleets") == (ref(EntityDomain.FLEET, "120", "TISpaceFleetState"),)
    assert hab.get("tier") == 1
    assert hab.get("habType") == "Station"
    assert hab.get("coreConstructionCompleted") is True
    assert hab.get("coreCompletionDate") == "2030-11-21T00:00:00"

    site_hab = by_id(assets.habs, "141")
    assert site_hab.get("faction") == unresolved(999)
    assert site_hab.get("orbitState") is None
    assert site_hab.get("dockedFleets") == ()


@pytest.mark.fixture
def test_mission_control_facilities_are_entities_and_resolve_both_reference_paths() -> None:
    snapshot = load("mission_control_facilities.json")
    facility = by_id(snapshot.mission_control_facilities, "20")
    assert facility.ref.entity_id == EntityId(EntityDomain.MISSION_CONTROL_FACILITY, "20")
    assert facility.ref.name == "Fixture Mission Control"
    assert facility.get("displayName") == "Fixture Mission Control"
    assert facility.get("spaceFacilityType") == "MissionControl"
    assert facility.get("region") == ref(EntityDomain.REGION, "10", "TIRegionState")
    assert by_id(snapshot.regions, "10").get("missionControlFacility") == ref(
        EntityDomain.MISSION_CONTROL_FACILITY, "20", "TIMissionControlFacilityState"
    )
    assert by_id(snapshot.missions, "12").get("target") == ref(
        EntityDomain.MISSION_CONTROL_FACILITY, "20", "TIMissionControlFacilityState"
    )

    changed_facility = replace(
        facility,
        fields=tuple(
            (name, "Changed Type" if name == "spaceFacilityType" else value) for name, value in facility.fields
        ),
    )
    changed_snapshot = replace(snapshot, mission_control_facilities=(changed_facility,))
    changes = diff_states(snapshot, changed_snapshot).changes
    assert [(change.domain, change.field) for change in changes] == [
        (EntityDomain.MISSION_CONTROL_FACILITY, "spaceFacilityType")
    ]


@pytest.mark.fixture
def test_mission_control_facility_references_preserve_null_and_unresolved_states() -> None:
    facility_fields = {
        "Key": {"value": 20},
        "Value": {
            "ID": {"value": 20},
            "$type": STATE_PREFIX + "TIMissionControlFacilityState",
            "region": None,
            "spaceFacilityType": "MissionControl",
        },
    }
    region_null = pair(10, missionControlFacility=None, **{"$type": STATE_PREFIX + "TIRegionState"})
    region_missing_target = pair(
        11,
        missionControlFacility={"value": 999},
        **{"$type": STATE_PREFIX + "TIRegionState"},
    )
    snapshot = fragment(
        {
            STATE_PREFIX + "TIMissionControlFacilityState": [facility_fields],
            STATE_PREFIX + "TIRegionState": [region_null, region_missing_target],
        }
    )
    assert by_id(snapshot.mission_control_facilities, "20").get("region") is None
    assert by_id(snapshot.regions, "10").get("missionControlFacility") is None
    assert by_id(snapshot.regions, "11").get("missionControlFacility") == unresolved(999)


CORE_FIELDS = DERIVED_FIELDS["TIHabState"]
PRIOR = {"year": 2040, "month": 2, "day": 20, "hour": 6, "minute": 0, "second": 0, "millisecond": 250}


def core_save(*habs: dict[str, object], sectors: list[dict[str, object]], modules: list[dict[str, object]]) -> RawSave:
    return fragment_raw(
        {
            STATE_PREFIX + "TIHabState": list(habs),
            STATE_PREFIX + "TISectorState": sectors,
            STATE_PREFIX + "TIHabModuleState": modules,
        }
    )


def test_a_habs_core_module_is_copied_from_slot_zero_of_its_first_sector() -> None:
    raw = core_save(
        pair(140, sectors=[{"value": 160}, {"value": 161}]),
        sectors=[pair(160, habModules=[{"value": 170}, {"value": 171}]), pair(161, habModules=[{"value": 172}])],
        modules=[
            pair(
                170,
                slot=0,
                constructionCompleted=False,
                startBuildDate="2041-02-25T00:00:00.0000000",
                completionDate="2041-03-17T12:30:00.1234567",
                priorModuleCompletionDate=PRIOR,
            ),
            pair(171, slot=1, constructionCompleted=True, startBuildDate="2040-01-01T00:00:00.0000000"),
            pair(172, slot=0, constructionCompleted=True),
        ],
    )
    snapshot, report = collect(raw)
    hab = by_id(snapshot.habs, "140")
    assert [hab.get(name) for name in CORE_FIELDS] == [
        False,
        "2041-02-25T00:00:00",
        "2041-03-17T12:30:00.123456",
        "2040-02-20T06:00:00.250000",
    ]
    assert not report.findings


def test_a_template_created_core_has_no_dates_and_a_hab_without_sectors_no_core() -> None:
    raw = core_save(
        pair(140, sectors=[{"value": 160}]),
        pair(141, sectors=[]),
        pair(142),
        sectors=[pair(160, habModules=[{"value": 170}])],
        modules=[
            pair(
                170,
                slot=0,
                constructionCompleted=True,
                startBuildDate="0001-01-01T00:00:00.0000000",
                completionDate="0001-01-01T00:00:00.0000000",
                priorModuleCompletionDate=None,
            )
        ],
    )
    snapshot, report = collect(raw)
    assert [by_id(snapshot.habs, "140").get(name) for name in CORE_FIELDS] == [True, None, None, None]
    for key in ("141", "142"):
        assert all(by_id(snapshot.habs, key).get(name) == Unknown() for name in CORE_FIELDS)
    assert not report.findings


def test_a_broken_core_chain_or_an_unparseable_core_date_is_reported_on_the_habs_sectors() -> None:
    raw = core_save(
        pair(140, sectors=[{"value": 160}]),
        pair(141, sectors=[{"value": 161}]),
        pair(142, sectors=[{"value": 999}]),
        sectors=[pair(160, habModules=[{"value": 170}]), pair(161, habModules=[{"value": 171}])],
        modules=[
            pair(170, slot=1, constructionCompleted=True),
            pair(171, slot=0, constructionCompleted=True, completionDate="soon", priorModuleCompletionDate="later"),
        ],
    )
    snapshot, report = collect(raw)
    for key in ("140", "142"):
        hab = by_id(snapshot.habs, key)
        assert all(hab.get(name) == Unknown(UnknownReason.UNRESOLVED_REFERENCE) for name in CORE_FIELDS)
    dated = by_id(snapshot.habs, "141")
    assert dated.get("coreCompletionDate") == Unknown(UnknownReason.UNPARSEABLE, "soon")
    assert dated.get("corePriorCompletionDate") == Unknown(UnknownReason.UNPARSEABLE, "later")
    assert dated.get("coreStartBuildDate") == Unknown()
    assert sorted(key[3] for key in keys(report) if key[1:3] == ("TIHabState", "sectors")) == [
        "componentized_date",
        "core_module",
        "module_date",
    ]


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


def test_game_datetime_repeats_give_the_same_result_and_a_cached_int_date_never_answers_for_bools() -> None:
    components = {"year": 2031, "month": 1, "day": 1, "hour": 1, "minute": 0, "second": 0}
    assert game_datetime(components) == game_datetime(dict(components)) == datetime(2031, 1, 1, 1)
    assert game_datetime({**components, "day": True}) is None
    assert game_datetime({**components, "millisecond": False}) is None
    invalid = {**components, "month": 13}
    assert game_datetime(invalid) is None
    assert game_datetime(invalid) is None


def test_unparseable_time_keeps_the_raw_value() -> None:
    time_state = {"Key": {"value": 2}, "Value": {"ID": {"value": 2}, "currentDateTime": {"year": 2031}}}
    snapshot = fragment({STATE_PREFIX + "TITimeState": [time_state]})
    assert snapshot.timestamp is None
    assert snapshot.date == Unknown(UnknownReason.UNPARSEABLE, FrozenMap((("year", 2031),)))


def test_scenario_faction_list_is_copied_as_template_names_without_resolution() -> None:
    names = ["FixtureResistTemplate", "FixtureExploitTemplate"]
    metadata = pair(1, playerFactionName="Fixture Resistance", selectedFactionsForScenario=names)
    snapshot, report = collect(fragment_raw({STATE_PREFIX + "TIMetadataState": [metadata]}))
    assert snapshot.campaign.selected_factions_for_scenario == tuple(names)
    assert snapshot.to_dict()["campaign"]["selected_factions_for_scenario"] == names
    assert report.findings == ()


def test_missing_scenario_faction_list_is_unknown() -> None:
    metadata = pair(1, playerFactionName="Fixture Resistance")
    snapshot = fragment({STATE_PREFIX + "TIMetadataState": [metadata]})
    assert snapshot.campaign.player_faction_name == "Fixture Resistance"
    assert snapshot.campaign.selected_factions_for_scenario == Unknown()
    assert snapshot.to_dict()["campaign"]["selected_factions_for_scenario"] == {"unknown": "missing"}


def test_malformed_normalized_container_is_rejected_as_unsupported_shape() -> None:
    bad = [{"Key": {"value": 1}, "Value": {"ID": {"value": 2}}}]
    with pytest.raises(UnsupportedSaveShapeError, match="TIControlPoint"):
        fragment({STATE_PREFIX + "TIControlPoint": bad})


# --- unknown structures -------------------------------------------------------------------------------------------


@pytest.mark.fixture
def test_fixture_unknowns_are_reported_and_leave_the_snapshot_unchanged(political: SaveSnapshot) -> None:
    raw = load_raw_save(fixture_path(*FIXTURE_SET, "political_control.json"))
    snapshot, report = collect(raw)
    assert snapshot == political
    assert keys(report) == [
        ("unknown_field", "TINationState", "fixtureOnlyUndocumentedField", ""),
        ("unknown_state_type", "TIFixtureUnknownState", "", ""),
    ]
    field, state_type = report.findings
    assert field.occurrences == 1 and field.shape == ShapeSummary(("number",))
    assert state_type.occurrences == 1
    assert "Fixture Resistance" not in json.dumps(report.to_dict())  # the type name is schema, values are not
    _assets, clean = collect(load_raw_save(fixture_path(*FIXTURE_SET, "campaign_assets.json")))
    assert clean.total == 0


def test_reference_fields_report_unexpected_shapes_and_owners_while_resolving_as_before() -> None:
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TIFactionState": [pair(10)],
        STATE_PREFIX + "TIMissionPhaseState": [pair(998)],  # inventory type without an entity domain
        STATE_PREFIX + "TIRegionState": [pair(40)],
        STATE_PREFIX + "TINationState": [
            pair(20, capital={"value": 10}, regions={"value": 40}, allies=[None], rivals=["x"]),
            pair(21, capital={"value": 998}, breakawayParent={"value": 999}, regions=[{"value": 40}]),
            pair(22, capital="40"),
        ],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert keys(report) == [
        ("unexpected_field_shape", "TINationState", "allies", "reference_object"),
        ("unexpected_field_shape", "TINationState", "capital", "reference_object"),
        ("unexpected_field_shape", "TINationState", "regions", "array_of_references"),
        ("unexpected_field_shape", "TINationState", "rivals", "reference_object"),
        ("unexpected_reference_domain", "TINationState", "capital", "TIFactionState"),
        ("unexpected_reference_domain", "TINationState", "capital", "TIMissionPhaseState"),
    ]
    assert by_id(snapshot.nations, "20").get("capital") == unresolved(10)
    assert by_id(snapshot.nations, "20").get("regions") == Unknown(
        UnknownReason.UNPARSEABLE, FrozenMap((("value", 40),))
    )
    assert by_id(snapshot.nations, "21").get("capital") == unresolved(998)
    assert by_id(snapshot.nations, "21").get("breakawayParent") == unresolved(999)  # absent ID: no finding
    assert by_id(snapshot.nations, "21").get("regions") == (ref(EntityDomain.REGION, "40", "TIRegionState"),)
    assert by_id(snapshot.nations, "22").get("capital") == Unknown(UnknownReason.UNRESOLVED_REFERENCE, "40")
    assert snapshot == fragment(gamestates)


FIRE_MISSION = {"year": 2031, "month": 5, "day": 1, "hour": 0, "minute": 0, "second": 0, "millisecond": 0}
FLEET_OPERATION = {
    "operationDataName": "FixtureOperation",
    "target": {"$type": STATE_PREFIX + "TISpaceFleetState", "value": 81},
    "startDate": FIRE_MISSION,
    "completionDate": {"$ref": "1"},
}
COUNCILOR_IDENTITY = {
    "gender": "Female",
    "dateBorn": {"year": 1990, "month": 4, "day": 2, "hour": 0, "minute": 0, "second": 0, "millisecond": 0},
}


def test_councilor_location_and_retained_details_are_normalized() -> None:
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TIFactionState": [pair(10), pair(11)],
        STATE_PREFIX + "TISpaceShipState": [pair(60)],
        STATE_PREFIX + "TICouncilorState": [
            pair(
                100,
                location={"$type": STATE_PREFIX + "TISpaceShipState", "value": 60},
                **COUNCILOR_IDENTITY,
            ),
            pair(101),
        ],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert report.total == 0
    onboard = by_id(snapshot.councilors, "100")
    ship = ref(EntityDomain.SHIP, "60", "TISpaceShipState")
    assert onboard.get("location") == ship
    assert onboard.get("gender") == "Female"
    born = onboard.get("dateBorn")
    assert born == "1990-04-02T00:00:00"

    quiet = by_id(snapshot.councilors, "101")
    for name in COUNCILOR_IDENTITY:
        assert quiet.get(name) == Unknown()  # missing, not coerced


NATION_SCALARS = {
    "advisingCouncilors": [],
    "aggregateNation": False,
    "alienNation": False,
    "military": True,
    "nuclearProgram": True,
    "numNuclearWeapons": 4,
    "spaceFlightProgram": True,
    "spaceFunding_year": 12.5,
    "sustainability": 3.0,
    "numControlPoints": 3,
    "policy_closedBorders": False,
    "policy_noMineralDevelopment": False,
    "policy_noNukes": False,
    "policy_noOilDevelopment": False,
    "tracker_CohesionChangeReason_AllTime": {"CohesionReason_Coup": -1.5, "CohesionReason_WarEnded": 0.25},
    "tracker_DemocracyChangeReason_AllTime": {"DemReason_Coup": -2.0},
    "tracker_EducationChangeReason_AllTime": {},
    "tracker_GDPChangeReason_AllTime": {"GDPReason_ClimateChange": -0.5},
    "tracker_InequalityChangeReason_AllTime": {"InqReason_ClimateChange": 0.1},
    "tracker_UnrestChangeReason_AllTime": {"UnrestReason_Coup": 1.0},
}


def test_nation_flags_trackers_claims_and_unrest_attempts_are_normalized() -> None:
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TIFactionState": [pair(10)],
        STATE_PREFIX + "TIRegionState": [pair(40), pair(41)],
        STATE_PREFIX + "TINationState": [
            pair(
                20,
                originalCapital={"value": 40},
                hostileClaims=[{"value": 41}],
                factionUnrestAttempts=[{"Key": {"value": 10}, "Value": 2}],
                tracker_PCGDP_ByQuarter=[{"Key": 1, "Value": 1.5}, {"Key": -1, "Value": 0.5}, {"Key": 0, "Value": 1.0}],
                **NATION_SCALARS,
            ),
            pair(21, originalCapital=None, hostileClaims=[], factionUnrestAttempts={}, tracker_PCGDP_ByQuarter=[]),
        ],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert report.total == 0
    nation = by_id(snapshot.nations, "20")
    assert nation.get("originalCapital") == ref(EntityDomain.REGION, "40", "TIRegionState")
    assert nation.get("hostileClaims") == (ref(EntityDomain.REGION, "41", "TIRegionState"),)
    assert nation.get("factionUnrestAttempts") == FrozenMap((("faction:10", 2),))
    quarters = nation.get("tracker_PCGDP_ByQuarter")  # a quarter -> value map, whatever the serialized order
    assert quarters == FrozenMap((("-1", 0.5), ("0", 1.0), ("1", 1.5)))
    for name, value in NATION_SCALARS.items():
        assert nation.get(name) == freeze(value)
    coups = nation.get("tracker_CohesionChangeReason_AllTime")
    assert isinstance(coups, FrozenMap) and dict(coups.items)["CohesionReason_Coup"] == -1.5

    empty = by_id(snapshot.nations, "21")
    assert empty.get("originalCapital") is None and empty.get("hostileClaims") == ()
    assert empty.get("factionUnrestAttempts") == FrozenMap() and empty.get("tracker_PCGDP_ByQuarter") == FrozenMap()
    for name in NATION_SCALARS:
        assert empty.get(name) == Unknown()  # missing, not coerced

    # a new quarter is one added key, not a rewritten series
    later = FrozenMap((("-1", 0.5), ("0", 1.0), ("1", 1.5), ("2", 1.75)))
    assert compare_values(quarters, later) == (ChangeKind.MAP, MapDetail(added=("2",)))


def test_integer_keyed_pair_maps_report_non_integer_and_repeated_keys() -> None:
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TINationState": [
            pair(20, tracker_PCGDP_ByQuarter=[{"Key": "1", "Value": 1.0}]),
            pair(21, tracker_PCGDP_ByQuarter=[{"Key": True, "Value": 1.0}]),
            pair(22, tracker_PCGDP_ByQuarter=[{"Key": 1, "Value": 1.0}, {"Key": 1, "Value": 2.0}]),
            pair(23, tracker_PCGDP_ByQuarter=[1.0, 2.0]),
        ],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert keys(report) == [("unexpected_field_shape", "TINationState", "tracker_PCGDP_ByQuarter", "pair_map")]
    assert report.findings[0].occurrences == 4
    for nation in snapshot.nations:
        value = nation.get("tracker_PCGDP_ByQuarter")
        assert isinstance(value, Unknown) and value.reason is UnknownReason.UNPARSEABLE


def test_singletons_dates_and_research_lists_report_their_unexpected_structures() -> None:
    time_entries = [
        pair(2, currentDateTime="2031-03-01T00:00:00", nextTurn=1),
        pair(3, currentDateTime={"year": 2031}),
    ]
    research = pair(5, finishedTechsNames="not-a-list", techProgress=[{"techTemplateName": "Dup"}])
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TITimeState": time_entries,
        STATE_PREFIX + RESEARCH_STATE_TYPE: [research],
    }
    snapshot, report = collect(fragment_raw(gamestates))
    assert keys(report) == [
        ("unexpected_field_shape", RESEARCH_STATE_TYPE, "finishedTechsNames", "array"),
        ("unexpected_field_shape", "TITimeState", "currentDateTime", "componentized_date"),
        ("unexpected_singleton_count", "TITimeState", "", ""),
        ("unknown_field", "TITimeState", "nextTurn", ""),
    ]
    singleton = next(finding for finding in report.findings if finding.kind.value == "unexpected_singleton_count")
    assert singleton.occurrences == 2 and singleton.shape is None
    date_shape = next(finding for finding in report.findings if finding.field == "currentDateTime")
    assert date_shape.shape == ShapeSummary(("string",))
    assert snapshot.date == Unknown(UnknownReason.UNPARSEABLE, "2031-03-01T00:00:00")
    assert snapshot.research.finished_techs_names == "not-a-list"


def test_unknown_structures_are_summarized_in_the_log_without_a_collector(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger="tinarrative"):
        fragment({STATE_PREFIX + "TINationState": [pair(20, secretField="Fixture Value")]})
    assert (
        "unknown structures total=1 state_types=0 fields=1 envelope_keys=0 field_shapes=0 reference_domains=0 "
        "singletons=0 containers=0"
    ) in caplog.text
    assert "secretField" not in caplog.text and "Fixture" not in caplog.text


@pytest.mark.fixture
def test_wars_and_federations_normalize_with_provenance_and_resolved_references() -> None:
    raw = load_raw_save(fixture_path(*FIXTURE_SET, "wars_before.json"))
    collector = UnknownCollector()
    snapshot = normalize(raw, collector=collector)
    assert collector.report().findings == ()

    def nation(key: str) -> EntityRef:
        return ref(EntityDomain.NATION, key, "TINationState")

    war = by_id(snapshot.wars, "90")
    assert war.ref.entity_id == EntityId(EntityDomain.WAR, "90") and war.ref.name == "Fixture War 90"
    assert war.location is not None and war.location.state_type == "TIWarState"
    assert war.location.path == "/gamestates/PavonisInteractive.TerraInvicta.TIWarState/0/Value"
    assert war.get("attacker") == nation("20") and war.get("defender") == nation("21")
    assert war.get("_attackingAlliance") == (nation("20"),)
    records = {(record.owner.entity_id.key, record.field): record for record in snapshot.records}
    start = records[("90", "startDate")]
    assert [entry.value for entry in start.entries] == ["2031-06-01T00:00:00"]  # type: ignore[union-attr]
    assert ("90", "dateOfLastFighting") in records and "startDate" not in dict(war.fields)

    federation = by_id(snapshot.federations, "80")
    assert federation.get("members") == (nation("24"), nation("25"))
    assert federation.get("federationName") == "Fixture Federation"
    assert "flagResource" not in dict(federation.fields)  # acknowledged UI cache
    assert by_id(snapshot.nations, "24").get("federation") == ref(EntityDomain.FEDERATION, "80", "TIFederationState")


GLOBAL_VALUES_TYPE = STATE_PREFIX + "TIGlobalValuesState"


@pytest.mark.fixture
def test_the_global_values_singleton_normalizes_as_one_entity_with_provenance() -> None:
    raw = load_raw_save(fixture_path(*FIXTURE_SET, "global_values_before.json"))
    collector = UnknownCollector()
    snapshot = normalize(raw, collector=collector)
    assert collector.report().findings == ()

    (singleton,) = snapshot.global_values
    assert singleton.ref.entity_id == EntityId(EntityDomain.GLOBAL_VALUES, "70")
    assert singleton.ref.confidence is IdentityConfidence.IN_SAVE_ID
    assert singleton.location is not None and singleton.location.path == f"/gamestates/{GLOBAL_VALUES_TYPE}/0/Value"
    assert singleton.get("interstateWars") == (
        ref(EntityDomain.WAR, "90", "TIWarState"),
        ref(EntityDomain.WAR, "91", "TIWarState"),
    )
    assert singleton.get("nuclearStrikes") == 0 and singleton.get("globalSeaLevelRise1Triggered") is False
    fields = dict(singleton.fields)
    for acknowledged in (
        "difficulty",
        "narrativeEvents",
        "pastEarthAtmosphericCO2_ppm",
        "showFinderArmies",
        "latestSaveVersion",
        "bestGlobalHumanEducation",
        "campaignStartVersion",
        "realWorldCampaignStart",
    ):
        assert acknowledged not in fields
    owned = {record.field for record in snapshot.records if record.owner.entity_id == singleton.ref.entity_id}
    assert owned == {
        "globalMilestones",
        "triggeredOncePerCampaignEvents",
        "triggeredOncePerTargetEvents",
    }
    assert "globalMilestones" not in fields


def test_a_missing_save_version_is_unknown() -> None:
    raw = fragment_raw({GLOBAL_VALUES_TYPE: [pair(70, campaignStartVersion="fixture-build-1")]})
    snapshot = normalize(raw)
    (singleton,) = snapshot.global_values
    assert "latestSaveVersion" not in dict(singleton.fields)
    assert "campaignStartVersion" not in dict(singleton.fields)


def test_a_second_global_values_entry_is_reported_and_kept() -> None:
    snapshot, report = collect(fragment_raw({GLOBAL_VALUES_TYPE: [pair(70), pair(71)]}))
    assert [state.ref.entity_id.key for state in snapshot.global_values] == ["70", "71"]
    assert keys(report) == [("unexpected_singleton_count", "TIGlobalValuesState", "", "")]


NOTIFICATION_QUEUE_TYPE = STATE_PREFIX + "TINotificationQueueState"


@pytest.mark.fixture
def test_the_notification_queue_normalizes_as_one_entity_owning_the_notification_log() -> None:
    raw = load_raw_save(fixture_path(*FIXTURE_SET, "notifications_after.json"))
    collector = UnknownCollector()
    snapshot = normalize(raw, collector=collector)
    assert collector.report().findings == ()

    (queue,) = snapshot.notification_queue
    assert queue.ref.entity_id == EntityId(EntityDomain.NOTIFICATION_QUEUE, "80")
    assert queue.location is not None and queue.location.path == f"/gamestates/{NOTIFICATION_QUEUE_TYPE}/0/Value"
    fields = dict(queue.fields)
    for acknowledged in ("alienEvents", "firstTimeTracker", "panelSummaryQueue", "timerNotificationQueue"):
        assert acknowledged not in fields
    (log,) = [record for record in snapshot.records if record.owner.entity_id == queue.ref.entity_id]
    assert log.field == "notificationSummaryQueue" and "notificationSummaryQueue" not in fields
    assert not isinstance(log.entries, Unknown) and len(log.entries) == 8


def test_a_second_notification_queue_entry_is_reported_and_kept() -> None:
    snapshot, report = collect(fragment_raw({NOTIFICATION_QUEUE_TYPE: [pair(80), pair(81)]}))
    assert [state.ref.entity_id.key for state in snapshot.notification_queue] == ["80", "81"]
    assert keys(report) == [("unexpected_singleton_count", "TINotificationQueueState", "", "")]


@pytest.mark.fixture
def test_the_combat_fixture_pair_normalizes_its_combat_logs_without_findings() -> None:
    for name, sizes in (("combat_before.json", [2, 0, 0]), ("combat_after.json", [4, 1, 0])):
        collector = UnknownCollector()
        snapshot = normalize(load_raw_save(fixture_path(*FIXTURE_SET, name)), collector=collector)
        assert collector.report().findings == ()
        logs = [record for record in snapshot.records if record.field == "CombatLogs"]
        assert [len(log.entries) for log in logs if not isinstance(log.entries, Unknown)] == sizes
        assert "CombatLogs" not in dict(snapshot.factions[0].fields)
