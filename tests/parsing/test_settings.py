"""Coverage of ``campaign_settings_from_states``: the game settings a save records about its campaign."""

from __future__ import annotations

from tinarrative.identity import STATE_PREFIX
from tinarrative.parsing.settings import CampaignSettings, campaign_settings_from_states

FACTIONS = ["ResistCouncil", "AppeaseCouncil"]


def pair(map_id: int, **members: object) -> dict[str, object]:
    return {"Key": {"value": map_id}, "Value": {"ID": {"value": map_id}, **members}}


def gamestates(metadata: dict[str, object], global_values: dict[str, object] | None = None) -> dict[str, object]:
    return {
        STATE_PREFIX + "TIFactionState": [pair(15, templateName="AppeaseCouncil"), pair(16, templateName="Other")],
        STATE_PREFIX + "TIPlayerState": [pair(60, isAI=False, faction={"value": 15}), pair(61, isAI=True)],
        STATE_PREFIX + "TIMetadataState": [pair(1, **metadata)],
        STATE_PREFIX + "TITimeState": [
            pair(2, masterMetaTemplateName="FullScenario", scenarioMetaTemplateName="2026Scenario")
        ],
        STATE_PREFIX + "TIGlobalValuesState": [pair(3, **(global_values or {}))],
    }


def test_every_recorded_setting_is_read() -> None:
    states = gamestates(
        {
            "difficulty": "Veteran",
            "customDifficulty": False,
            "playedWithMods": False,
            "selectedFactionsForScenario": FACTIONS,
            "alienProgressionSpeed": "150%",
            "researchSpeedMultiplier": "100%",
        },
        {"moddingUsedAnytime": False},
    )

    assert campaign_settings_from_states(states) == CampaignSettings(
        player_faction="AppeaseCouncil",
        difficulty="Veteran",
        custom_difficulty=False,
        scenario="FullScenario/2026Scenario",
        factions=("AppeaseCouncil", "ResistCouncil"),
        mods=False,
        alien_progression_speed=1.5,
        research_speed=1.0,
    )


def test_a_setting_the_save_does_not_carry_is_unknown() -> None:
    assert campaign_settings_from_states(gamestates({})) == CampaignSettings(
        player_faction="AppeaseCouncil", scenario="FullScenario/2026Scenario"
    )


def test_a_speed_that_is_not_a_percentage_is_unknown() -> None:
    settings = campaign_settings_from_states(gamestates({"alienProgressionSpeed": "fast"}))

    assert settings.alien_progression_speed is None


def test_modding_used_at_any_time_counts_as_mods() -> None:
    settings = campaign_settings_from_states(gamestates({"playedWithMods": False}, {"moddingUsedAnytime": True}))

    assert settings.mods is True
