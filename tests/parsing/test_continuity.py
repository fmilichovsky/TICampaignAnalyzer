"""Coverage of ``campaign_profile``: the continuity signals read from a raw save."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tinarrative.identity import STATE_PREFIX
from tinarrative.parsing.continuity import CampaignProfile, campaign_profile, campaign_profile_from_bytes
from tinarrative.parsing.errors import UnsupportedSaveShapeError
from tinarrative.parsing.raw_save import RawSave

START = {"year": 2026, "month": 1, "day": 4, "hour": 11, "minute": 37, "second": 51, "millisecond": 759}


def pair(map_id: int, **members: object) -> dict[str, object]:
    return {"Key": {"value": map_id}, "Value": {"ID": {"value": map_id}, **members}}


def player(map_id: int, *, ai: bool, faction: int | None = 15) -> dict[str, object]:
    return pair(map_id, isAI=ai, faction=None if faction is None else {"value": faction})


def profile(players: list[dict[str, object]], *, global_values: bool = True) -> CampaignProfile:
    gamestates: dict[str, object] = {
        STATE_PREFIX + "TIFactionState": [pair(15), pair(16)],
        STATE_PREFIX + "TIPlayerState": players,
        STATE_PREFIX + "TIMetadataState": [pair(1, playerFactionName="The Resistance")],
        STATE_PREFIX + "TITimeState": [
            pair(2, masterMetaTemplateName="FullScenario", scenarioMetaTemplateName="2026Scenario")
        ],
    }
    if global_values:
        gamestates[STATE_PREFIX + "TIGlobalValuesState"] = [pair(3, realWorldCampaignStart=START)]
    root: dict[str, object] = {"currentID": {"value": 1}, "gamestates": gamestates}
    return campaign_profile(RawSave("fragment.json", "terra_invicta_json_v1", None, root, 1))


def test_one_human_player_gives_the_full_identity() -> None:
    result = profile([player(60, ai=False), player(61, ai=True, faction=16)])

    assert result == CampaignProfile(
        human_faction=15,
        human_players=1,
        faction_name="The Resistance",
        scenario=("FullScenario", "2026Scenario"),
        started=datetime(2026, 1, 4, 11, 37, 51, 759000),
    )
    assert result.identity == (15, "The Resistance", ("FullScenario", "2026Scenario"), result.started)


def test_bytes_entry_point_matches_raw_save_entry_point() -> None:
    value = {"currentID": {"value": 1}, "gamestates": {}}
    value["gamestates"].update(
        {
            STATE_PREFIX + "TIFactionState": [pair(15)],
            STATE_PREFIX + "TIPlayerState": [player(60, ai=False)],
            STATE_PREFIX + "TIMetadataState": [pair(1, playerFactionName="The Resistance")],
            STATE_PREFIX + "TITimeState": [pair(2)],
            STATE_PREFIX + "TIGlobalValuesState": [pair(3, realWorldCampaignStart=START)],
        }
    )
    data = json.dumps(value).encode()
    raw = RawSave("fragment.json", "terra_invicta_json_v1", None, value, len(data))

    assert campaign_profile_from_bytes(data) == campaign_profile(raw)


@pytest.mark.parametrize(
    ("players", "humans"),
    [
        ([player(60, ai=True)], 0),
        ([player(60, ai=False), player(61, ai=False, faction=16)], 2),
        ([player(60, ai=False, faction=99)], 1),
        ([player(60, ai=False, faction=None)], 1),
    ],
    ids=["no-human", "two-humans", "unresolved-faction", "null-faction"],
)
def test_a_save_without_one_resolvable_human_player_is_unclassified(
    players: list[dict[str, object]], humans: int
) -> None:
    result = profile(players)

    assert (result.human_faction, result.human_players, result.identity) == (None, humans, None)


def test_a_missing_global_values_entry_leaves_the_start_unknown() -> None:
    result = profile([player(60, ai=False)], global_values=False)

    assert result.started is None
    assert result.identity == (15, "The Resistance", ("FullScenario", "2026Scenario"), None)


def test_a_malformed_player_container_is_an_unsupported_shape() -> None:
    with pytest.raises(UnsupportedSaveShapeError):
        profile([{"Key": {"value": 60}}])
