"""Coverage for tinarrative.narrator.request: the packaged prompt and deterministic request assembly."""

from __future__ import annotations

import ast
import hashlib
import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

import tinarrative.narrator
from tests.fixtures import FIXTURES_ROOT
from tinarrative.cli import EXIT_SUCCESS
from tinarrative.cli import main as cli_main
from tinarrative.narrator.request import REQUEST_KEYS, build_request, chapter_package, prompt_version, system_prompt

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"
GOLDEN = FIXTURES_ROOT / "sequence" / "terra_invicta_json_v1" / "politics_sequence.expected.narrator_messages.json"
SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]
NARRATOR_DOC = Path(__file__).resolve().parents[2] / "docs" / "narrator.md"
FORBIDDEN = ("tinarrative.parsing", "tinarrative.sequence", "tinarrative.model")
MINIMAL: dict[str, Any] = {"narrative": [], "glossary": []}


def _package(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    monkeypatch.chdir(FIXTURE_DIR)
    assert cli_main(["events", "--format", "json", "--narrative", "--constituents", "evidence", *SAVES]) == EXIT_SUCCESS
    return json.loads(capsys.readouterr().out)  # type: ignore[no-any-return]


def _embedded(request: dict[str, Any]) -> dict[str, Any]:
    content = request["messages"][0]["content"]
    return json.loads(content.partition("```json\n")[2].rpartition("\n```")[0])  # type: ignore[no-any-return]


def test_the_system_prompt_is_package_data() -> None:
    prompt = system_prompt()

    assert resources.files("tinarrative.narrator").joinpath("prompt.md").is_file()
    assert prompt.startswith("You are the narrative interpreter")
    assert "## Facts" in prompt and "```" not in prompt


def test_the_doc_points_at_the_packaged_prompt_instead_of_copying_it() -> None:
    doc = NARRATOR_DOC.read_text(encoding="utf-8")

    assert "src/tinarrative/narrator/prompt.md" in doc
    assert "```text" not in doc
    assert system_prompt().splitlines()[0] not in doc


def test_the_prompt_version_is_the_sha256_of_the_prompt() -> None:
    version = prompt_version()

    assert version == hashlib.sha256(system_prompt().encode("utf-8")).hexdigest()
    assert len(version) == 64


def test_the_request_matches_the_golden_and_is_deterministic(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(monkeypatch, capsys)

    request = build_request(package, {"period": "quarter", "audience": "public"})

    assert request == build_request(json.loads(json.dumps(package)), {"audience": "public", "period": "quarter"})
    assert request["system"] == system_prompt()
    assert request["messages"] == json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert request["messages"][0]["content"].startswith("period: quarter\naudience: public\n\n")
    assert _embedded(request) == package


def test_the_request_block_has_a_fixed_key_order_and_only_the_keys_set() -> None:
    options = {"focus": "ESA", "style": "headlines", "length": "2000 words", "period": "half", "citations": "none"}

    content = build_request(MINIMAL, options)["messages"][0]["content"]

    assert content.startswith("period: half\ncitations: none\nstyle: headlines\nlength: 2000 words\nfocus: ESA\n\n")
    assert "audience" not in content.partition("\n\n")[0]
    assert REQUEST_KEYS == ("chapter", "part", "covers", "period", "audience", "citations", "style", "length", "focus")


def test_an_empty_block_leaves_the_message_to_the_package() -> None:
    content = build_request(MINIMAL, {})["messages"][0]["content"]

    assert content.startswith("The narrator package follows.\n\n```json\n")


def test_notes_follow_the_keys() -> None:
    content = build_request(MINIMAL, {"style": "chronicle"}, notes=("sample: 2032",))["messages"][0]["content"]

    assert content.startswith("style: chronicle\nsample: 2032\n\n")


def test_bad_input_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="not a narrator package"):
        build_request({"narrative": None, "glossary": None}, {})
    with pytest.raises(ValueError, match="unknown request keys: tone"):
        build_request(MINIMAL, {"tone": "dry"})


def test_chapter_package_reads_back_the_package_a_request_carries() -> None:
    package = {**MINIMAL, "campaign": {"key": "c"}, "note": "```json inside a value```"}

    assert chapter_package(build_request(package, {"period": "year"})) == package
    with pytest.raises(ValueError, match="carries no narrator package"):
        chapter_package({"system": "s", "messages": [{"role": "user", "content": "no package"}]})
    with pytest.raises(ValueError, match="carries no narrator package"):
        chapter_package({"system": "s"})


def test_the_narrator_package_does_not_import_the_deterministic_half() -> None:
    directory = Path(tinarrative.narrator.__file__).parent
    imported: set[str] = set()
    for source in directory.glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = ["tinarrative", "narrator"][: 3 - node.level] if node.level else []
                module = ".".join([*base, *([node.module] if node.module else [])])
                imported.add(module)
                imported.update(f"{module}.{alias.name}" for alias in node.names)

    assert not {name for name in imported if name.startswith(FORBIDDEN)}
