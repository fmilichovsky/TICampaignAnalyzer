"""Synthetic campaign variants: a checked-in politics save with its continuity signals edited, written to a temp dir."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.fixtures import fixture_path
from tinarrative.identity import STATE_PREFIX

FIXTURE_SET = "terra_invicta_json_v1"
POLITICS = ("politics_before.json", "politics_after.json", "politics_reverted.json")
"""Three saves of one synthetic campaign (human faction 15, "Fixture Resistance"), dated 2032-01/04/07."""
OTHER_FACTION = 16
"""The second ``TIFactionState`` of the politics fixtures."""
GLOBAL_VALUES_ID = 9001


def _components(moment: datetime) -> dict[str, int]:
    return {
        "year": moment.year,
        "month": moment.month,
        "day": moment.day,
        "hour": moment.hour,
        "minute": moment.minute,
        "second": moment.second,
        "millisecond": moment.microsecond // 1000,
    }


def write_variant(
    directory: Path,
    name: str,
    base: str = POLITICS[0],
    *,
    faction: int | None = None,
    faction_name: str | None = None,
    scenario: str | None = None,
    started: datetime | None = None,
    humans: int | None = None,
) -> Path:
    """Copy ``base`` to ``directory/name`` with the given signals changed; ``None`` keeps the fixture's value.

    ``started`` adds a ``TIGlobalValuesState`` holding ``realWorldCampaignStart``; ``humans`` replaces the player list
    with that many non-AI players of the human faction (0 makes the only player an AI).
    """
    root: dict[str, Any] = json.loads(fixture_path("io", FIXTURE_SET, base).read_text(encoding="utf-8"))
    gamestates: dict[str, Any] = root["gamestates"]
    players: list[dict[str, Any]] = gamestates[STATE_PREFIX + "TIPlayerState"]
    if faction is not None:
        players[0]["Value"]["faction"] = {"value": faction}
    if humans is not None:
        template = players[0]
        if humans == 0:
            template["Value"]["isAI"] = True
        else:
            players[:] = [
                {"Key": {"value": 60 + n}, "Value": {**template["Value"], "ID": {"value": 60 + n}}}
                for n in range(humans)
            ]
    if faction_name is not None:
        gamestates[STATE_PREFIX + "TIMetadataState"][0]["Value"]["playerFactionName"] = faction_name
    if scenario is not None:
        gamestates[STATE_PREFIX + "TITimeState"][0]["Value"]["scenarioMetaTemplateName"] = scenario
    if started is not None:
        gamestates[STATE_PREFIX + "TIGlobalValuesState"] = [
            {
                "Key": {"value": GLOBAL_VALUES_ID},
                "Value": {"ID": {"value": GLOBAL_VALUES_ID}, "realWorldCampaignStart": _components(started)},
            }
        ]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(root), encoding="utf-8")
    return path


def write_campaign(directory: Path, prefix: str, **signals: Any) -> list[Path]:
    """All three politics saves as one campaign with the same edited signals."""
    return [write_variant(directory, f"{prefix}_{base}", base, **signals) for base in POLITICS]
