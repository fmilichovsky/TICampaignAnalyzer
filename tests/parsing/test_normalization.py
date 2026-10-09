"""Fixture-driven coverage of ``normalize``: metadata, four entity collections, references, provenance."""

import json
from datetime import datetime

import pytest

from tests.fixtures import fixture_path
from tinarrative.identity import STATE_PREFIX
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason
from tinarrative.parsing.errors import UnsupportedSaveShapeError
from tinarrative.parsing.fields import ENTITY_FIELDS, NORMALIZED_DOMAINS
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


@pytest.fixture(scope="module")
def political() -> SaveSnapshot:
    return load("political_control.json")


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
def test_collections_are_typed_sorted_and_carry_provenance(political: SaveSnapshot) -> None:
    assert [len(getattr(political, attribute)) for _, _, attribute in NORMALIZED_DOMAINS] == [2, 2, 3, 4]
    for domain, short_type, attribute in NORMALIZED_DOMAINS:
        states: tuple[EntityState, ...] = getattr(political, attribute)
        assert [state.ref.entity_id for state in states] == sorted(state.ref.entity_id for state in states)
        for index, state in enumerate(states):
            assert state.ref.entity_id.domain is domain
            assert state.ref.confidence is IdentityConfidence.IN_SAVE_ID
            assert state.ref.state_type == short_type
            assert state.location is not None
            assert state.location.save_id == political.source
            assert state.location.provenance_key == f"{short_type}:{state.ref.entity_id.key}"
            assert state.location.path == f"/gamestates/{STATE_PREFIX}{short_type}/{index}/Value"
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
