"""Coverage for `tinarrative councilors`: one save, a sequence, --player-only, the written dossier and exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT
from tests.narrative.support import loyalty_keys
from tinarrative.cli import EXIT_CONFIG_ERROR, EXIT_INPUT_ERROR, EXIT_OUTPUT_ERROR, EXIT_SUCCESS, main

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"
SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]


@pytest.fixture
def settings(tmp_path: Path) -> str:
    """The fixture councilors were recruited months before the saves, so the tenure cut is lifted."""
    path = tmp_path / "settings.toml"
    path.write_text("[councilors]\nmin_tenure_days = 0\nrivals_per_faction = 1\n", encoding="utf-8")
    return str(path)


@pytest.fixture(autouse=True)
def in_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(FIXTURE_DIR)


def _dossier(tmp_path: Path, *argv: str) -> dict[str, object]:
    assert main(["councilors", *argv, "--output", str(tmp_path / "out")]) == EXIT_SUCCESS
    document: dict[str, object] = json.loads((tmp_path / "out" / "dossier.json").read_text(encoding="utf-8"))
    return document


@pytest.mark.fixture
def test_one_save_gives_a_portrait_without_a_career(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], settings: str
) -> None:
    document = _dossier(tmp_path, "politics_before.json", "--config", settings)
    councilors = document["councilors"]
    assert isinstance(councilors, list) and councilors
    assert all(entry["career"] == [] for entry in councilors)
    assert document["source"] == "politics_before.json"
    assert "councilors selected" in capsys.readouterr().out


@pytest.mark.fixture
def test_a_sequence_adds_the_career_of_the_latest_save(tmp_path: Path, settings: str) -> None:
    document = _dossier(tmp_path, *SAVES, "--config", settings)
    assert document["source"] == "politics_reverted.json"
    careers = [entry["career"] for entry in document["councilors"]]  # type: ignore[attr-defined]
    assert any(careers)


@pytest.mark.fixture
def test_player_only_drops_the_rivals(tmp_path: Path, settings: str) -> None:
    everyone = _dossier(tmp_path, "politics_before.json", "--config", settings)["councilors"]
    only = _dossier(tmp_path, "politics_before.json", "--config", settings, "--player-only")["councilors"]
    assert {entry["player"] for entry in everyone} == {True, False}  # type: ignore[attr-defined]
    assert {entry["player"] for entry in only} == {True}  # type: ignore[attr-defined]


@pytest.mark.fixture
def test_the_dossier_never_names_loyalty(tmp_path: Path, settings: str) -> None:
    _dossier(tmp_path, *SAVES, "--config", settings)
    assert loyalty_keys(json.loads((tmp_path / "out" / "dossier.json").read_text(encoding="utf-8"))) == []


@pytest.mark.fixture
def test_without_output_only_the_summary_is_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], settings: str
) -> None:
    assert main(["councilors", *SAVES, "--config", settings]) == EXIT_SUCCESS
    assert "councilors selected" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


@pytest.mark.fixture
def test_it_never_uses_the_network(monkeypatch: pytest.MonkeyPatch, settings: str) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("the dry run must not open a connection")

    monkeypatch.setattr("socket.socket.connect", refuse)
    assert main(["councilors", *SAVES, "--config", settings]) == EXIT_SUCCESS


@pytest.mark.fixture
def test_exit_codes(tmp_path: Path, settings: str) -> None:
    assert main(["councilors", "missing.json"]) == EXIT_INPUT_ERROR
    bad = tmp_path / "bad.toml"
    bad.write_text("[councilors]\narticle_words = 0\n", encoding="utf-8")
    assert main(["councilors", "politics_before.json", "--config", str(bad)]) == EXIT_CONFIG_ERROR
    blocked = tmp_path / "file"
    blocked.write_text("x", encoding="utf-8")
    assert (
        main(["councilors", "politics_before.json", "--config", settings, "--output", str(blocked)])
        == EXIT_OUTPUT_ERROR
    )
