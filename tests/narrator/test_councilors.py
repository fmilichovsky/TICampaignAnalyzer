"""Coverage for tinarrative.narrator.councilors: the packaged prompt, article requests and their assembly."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from tinarrative.narrator import request as narrator_request
from tinarrative.narrator.brief import councilor_brief
from tinarrative.narrator.councilors import (
    assemble_articles,
    build_article_request,
    missing,
    prompt_version,
    request_sha256,
    system_prompt,
)
from tinarrative.narrator.request import digest, render_request

NARRATOR_DOC = Path(__file__).resolve().parents[2] / "docs" / "narrator.md"
GENERATED = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


def _entry(name: str, faction: str, *, player: bool, key: str) -> dict[str, Any]:
    return {
        "id": f"councilor:{key}",
        "name": name,
        "faction": faction,
        "player": player,
        "profession": "diplomat",
        "traits": {"reputation": ["Famous"]},
        "skills": {"Persuasion": 9, "Administration": 4},
        "xp": 12,
        "orgs": [],
        "prominence": {"org_share": 0.0, "skill_sum": 13, "rank_in_faction": 1},
        "career": [],
    }


DOSSIER: dict[str, Any] = {
    "as_of": "2034-06-01T00:00:00",
    "source": "latest.json",
    "player_faction": "Fixture Resistance",
    "selection": {
        "player_only": False,
        "rivals_per_faction": 1,
        "min_tenure_days": 0,
        "missions_per_councilor": 3,
        "article_words": 120,
    },
    "councilors": [
        _entry("Ada One", "Fixture Resistance", player=True, key="1"),
        _entry("Bo Two", "Fixture Resistance", player=True, key="2"),
        _entry("Cy Three", "Fixture Servants", player=False, key="3"),
    ],
}


def _record(index: int, text: str, **changes: Any) -> dict[str, Any]:
    record = {
        "index": index,
        "request_sha256": request_sha256(build_article_request(DOSSIER, index)),
        "provider": "anthropic",
        "model": "some-model",
        "max_output_tokens": 2000,
        "temperature": None,
        "reported_model": "reported-model",
        "finish": "complete",
        "input_tokens": 1000 + index,
        "output_tokens": 200,
        "text": text,
    }
    record.update(changes)
    return record


def test_the_councilor_prompt_is_package_data() -> None:
    prompt = system_prompt()

    assert resources.files("tinarrative.narrator").joinpath("councilor_prompt.md").is_file()
    assert prompt.strip() and "```" not in prompt


def test_the_prompt_version_is_its_sha256_and_not_the_narrator_prompt() -> None:
    version = prompt_version()

    assert version == hashlib.sha256(system_prompt().encode("utf-8")).hexdigest()
    assert version != narrator_request.prompt_version()


def test_the_doc_points_at_the_packaged_councilor_prompt_instead_of_copying_it() -> None:
    doc = NARRATOR_DOC.read_text(encoding="utf-8")

    assert "src/tinarrative/narrator/councilor_prompt.md" in doc
    assert system_prompt().splitlines()[0] not in doc


def test_the_article_request_holds_the_brief_of_one_entry() -> None:
    request = build_article_request(DOSSIER, 3)

    assert request == build_article_request(json.loads(json.dumps(DOSSIER)), 3)
    assert request["system"] == system_prompt()
    content = request["messages"][0]["content"]
    assert content.startswith("councilor: Cy Three\nfaction: Fixture Servants\nlength: about 120 words\n\n")
    embedded = json.loads(content.partition("```json\n")[2].rpartition("\n```")[0])
    assert embedded == councilor_brief(DOSSIER, DOSSIER["councilors"][2])
    assert request_sha256(request) == hashlib.sha256(render_request(request).encode("utf-8")).hexdigest()


def test_options_and_bad_input() -> None:
    content = build_article_request(DOSSIER, 1, {"length": "about 50 words"})["messages"][0]["content"]

    assert content.startswith("councilor: Ada One\nfaction: Fixture Resistance\nlength: about 50 words\n\n")
    with pytest.raises(ValueError, match="unknown request keys: councilor"):
        build_article_request(DOSSIER, 1, {"councilor": "Someone"})
    with pytest.raises(ValueError, match="article 4: the dossier has 3 councilors"):
        build_article_request(DOSSIER, 4)
    with pytest.raises(ValueError, match="article 0"):
        build_article_request(DOSSIER, 0)
    with pytest.raises(ValueError, match="not a councilor dossier"):
        build_article_request({"councilors": "no"}, 1)


def test_assembly_groups_by_faction_in_dossier_order() -> None:
    stored = {1: _record(1, "# Ada One\n\nAda leads.\n"), 2: _record(2, "Bo follows.  \n\n"), 3: _record(3, "Cy.")}

    markdown, manifest = assemble_articles(DOSSIER, stored, generated=GENERATED, version="0.1.0")

    assert markdown == (
        "# Councilor profiles\n\n"
        "- Provider: anthropic\n"
        "- Model: reported-model (requested some-model)\n"
        f"- Prompt version: {prompt_version()}\n"
        "- As of: 2034-06-01\n"
        "- Player faction: Fixture Resistance\n"
        "- Generated: 2026-10-22T09:00:00Z\n\n"
        "## Fixture Resistance\n\n"
        "### Ada One\n\nAda leads.\n\n"
        "### Bo Two\n\nBo follows.\n\n"
        "## Fixture Servants\n\n"
        "### Cy Three\n\nCy.\n"
    )
    assert [row["written"] for row in manifest["articles"]] == [True, True, True]
    assert missing(manifest) == []
    assert manifest["tokens"] == {"input_tokens": 3006, "output_tokens": 600}


def test_a_missing_article_is_in_the_manifest_only() -> None:
    stub = {"provider": "anthropic", "model": "some-model", "finish": "length", "error": "stopped at 2000"}
    stored = {1: _record(1, "Ada."), 2: stub, 3: _record(3, "Cy.")}

    markdown, manifest = assemble_articles(DOSSIER, stored, generated=GENERATED, version="0.1.0")

    assert "### Bo Two" not in markdown and "Bo" not in markdown
    assert "### Ada One" in markdown and "### Cy Three" in markdown
    row = manifest["articles"][1]
    assert row["index"] == 2 and row["name"] == "Bo Two" and row["written"] is False
    assert row["finish"] == "length" and row["error"] == "stopped at 2000" and "text" not in row
    assert row["request_sha256"] == request_sha256(build_article_request(DOSSIER, 2))
    assert missing(manifest) == [2]
    assert manifest["tokens"] == {"input_tokens": 2004, "output_tokens": 400}
    assert manifest["prompt_version"] == prompt_version()
    assert manifest["dossier_sha256"] == digest(DOSSIER)
    assert manifest["settings"] == {
        **DOSSIER["selection"],
        "provider": "anthropic",
        "model": "some-model",
        "max_output_tokens": 2000,
        "temperature": None,
    }
    assert manifest["program"] == {"name": "tinarrative", "version": "0.1.0"}


def test_a_stale_or_never_sent_article_is_not_written() -> None:
    stored = {1: _record(1, "Old.", request_sha256="0" * 64)}
    sent_with = {"provider": "ollama", "model": "local", "max_output_tokens": 500, "temperature": 0.2}

    markdown, manifest = assemble_articles(DOSSIER, stored, generated=GENERATED, version="0.1.0", sent_with=sent_with)

    assert markdown.startswith("# Councilor profiles\n\n- Provider: ollama\n- Model: not reported (requested local)\n")
    assert "##" not in markdown
    assert missing(manifest) == [1, 2, 3]
    assert manifest["articles"][0]["finish"] == "complete" and manifest["articles"][1]["finish"] is None
    assert manifest["settings"]["model"] == "local"
    assert manifest["tokens"] == {"input_tokens": None, "output_tokens": None}
