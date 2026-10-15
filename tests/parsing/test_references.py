"""Conservative reference resolution: resolve only to a known ID in the expected domain."""

import logging

import pytest

from tinarrative.identity import STATE_PREFIX
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason
from tinarrative.parsing.references import ReferenceIndex


def pair(map_id: int) -> dict[str, object]:
    return {"Key": {"value": map_id}, "Value": {"ID": {"value": map_id}}}


GAMESTATES: dict[str, object] = {
    STATE_PREFIX + "TINationState": [pair(20)],
    STATE_PREFIX + "TIArmyState": [pair(50)],
    STATE_PREFIX + "TIMegafaunaArmyState": [pair(51)],
    STATE_PREFIX + "TIHabState": [pair(140)],
    STATE_PREFIX + "TIMissionState": [pair(80)],  # no entity domain: never resolves
    STATE_PREFIX + "TICouncilorState": [{"Key": {"value": 1}, "Value": {"ID": {"value": 2}}}],  # malformed, skipped
}
INDEX = ReferenceIndex.from_gamestates(GAMESTATES)


def test_index_covers_domain_state_types_and_skips_malformed_or_undomained_types() -> None:
    assert INDEX.owners == {
        20: (EntityDomain.NATION, "TINationState"),
        50: (EntityDomain.ARMY, "TIArmyState"),
        51: (EntityDomain.ARMY, "TIMegafaunaArmyState"),
        140: (EntityDomain.SPACE_OBJECT, "TIHabState"),
    }


def test_null_reference_is_a_known_none() -> None:
    assert INDEX.resolve(None, EntityDomain.NATION) is None


def test_resolved_reference_names_the_owning_state_type() -> None:
    assert INDEX.resolve({"value": 20}, EntityDomain.NATION) == EntityRef(
        EntityId(EntityDomain.NATION, "20"), IdentityConfidence.IN_SAVE_ID, state_type="TINationState"
    )
    armies = INDEX.resolve_list([{"value": 50}, {"value": 51, "$type": "x"}], EntityDomain.ARMY)
    assert isinstance(armies, tuple)
    assert [ref.state_type for ref in armies if isinstance(ref, EntityRef)] == ["TIArmyState", "TIMegafaunaArmyState"]


def test_unknown_id_wrong_domain_and_undomained_target_stay_unresolved_with_raw_value() -> None:
    raw = FrozenMap((("value", 999),))
    assert INDEX.resolve({"value": 999}, EntityDomain.NATION) == Unknown(UnknownReason.UNRESOLVED_REFERENCE, raw)
    assert INDEX.resolve({"value": 50}, EntityDomain.NATION) == Unknown(
        UnknownReason.UNRESOLVED_REFERENCE, FrozenMap((("value", 50),))
    )
    assert INDEX.resolve({"value": 80}, EntityDomain.NATION) == Unknown(
        UnknownReason.UNRESOLVED_REFERENCE, FrozenMap((("value", 80),))
    )
    assert INDEX.resolve("20", EntityDomain.NATION) == Unknown(UnknownReason.UNRESOLVED_REFERENCE, "20")


def test_list_with_one_unresolvable_element_is_wholly_unknown() -> None:
    value = [{"value": 20}, {"value": 999}]
    result = INDEX.resolve_list(value, EntityDomain.NATION)
    assert result == Unknown(
        UnknownReason.UNRESOLVED_REFERENCE, (FrozenMap((("value", 20),)), FrozenMap((("value", 999),)))
    )
    assert INDEX.resolve_list([], EntityDomain.NATION) == ()
    assert INDEX.resolve_list({"value": 20}, EntityDomain.NATION) == Unknown(
        UnknownReason.UNPARSEABLE, FrozenMap((("value", 20),))
    )


def test_a_field_may_name_several_target_domains_and_the_owner_decides_the_domain() -> None:
    place = frozenset((EntityDomain.REGION, EntityDomain.SPACE_OBJECT))
    assert INDEX.resolve({"value": 140, "$type": "x"}, place) == EntityRef(
        EntityId(EntityDomain.SPACE_OBJECT, "140"), IdentityConfidence.IN_SAVE_ID, state_type="TIHabState"
    )
    assert INDEX.resolve({"value": 20}, place) == Unknown(
        UnknownReason.UNRESOLVED_REFERENCE, FrozenMap((("value", 20),))
    )
    assert INDEX.resolve_list([{"value": 140}, {"value": 20}], place) == Unknown(
        UnknownReason.UNRESOLVED_REFERENCE, (FrozenMap((("value", 140),)), FrozenMap((("value", 20),)))
    )
    assert INDEX.resolve_list([{"value": 140}], frozenset((EntityDomain.SPACE_OBJECT,))) == (
        EntityRef(EntityId(EntityDomain.SPACE_OBJECT, "140"), IdentityConfidence.IN_SAVE_ID, state_type="TIHabState"),
    )


def test_skipped_malformed_container_is_explained_in_the_debug_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="tinarrative"):
        ReferenceIndex.from_gamestates(GAMESTATES)
    skipped = [record.getMessage() for record in caplog.records if "reference index skipped" in record.getMessage()]
    assert skipped == [
        "reference index skipped state_type=TICouncilorState "
        "reason='PavonisInteractive.TerraInvicta.TICouncilorState[0]: Key.value 1 != Value.ID.value 2'"
    ]
    assert "reference index built ids=4 other_ids=1 skipped_types=1" in caplog.text


def test_other_owners_name_ids_outside_the_entity_domains() -> None:
    assert INDEX.other_owners == {80: "TIMissionState"}
    nation = frozenset((EntityDomain.NATION,))
    assert INDEX.owner_state_type(50, nation) == "TIArmyState"  # exists, wrong domain
    assert INDEX.owner_state_type(80, nation) == "TIMissionState"  # exists, no domain
    assert INDEX.owner_state_type(20, nation) is None  # expected owner
    assert INDEX.owner_state_type(999, nation) is None  # absent


def test_skipped_containers_are_announced_through_the_callback() -> None:
    skipped: list[str] = []
    ReferenceIndex.from_gamestates(GAMESTATES, on_skipped=skipped.append)
    assert skipped == ["TICouncilorState"]
