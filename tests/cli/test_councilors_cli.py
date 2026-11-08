"""Coverage for `tinarrative councilors`: the dry run (one save, a sequence, --player-only, the dossier and the
requests), `--send` with a fake transport, and the exit codes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures import FIXTURES_ROOT
from tests.narrative.support import loyalty_keys
from tinarrative.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_OUTPUT_ERROR,
    EXIT_PROVIDER_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    main,
)
from tinarrative.narrator.councilors import build_article_request, request_sha256
from tinarrative.narrator.transport import HttpResponse

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


# Sending

KEY = "sk-test-0123456789-secret"


class FakeTransport:
    """Answers Anthropic completions with one short article per call; ``stops`` gives the stop reason per call
    (``end_turn`` when exhausted)."""

    def __init__(self, *stops: str) -> None:
        self.stops = list(stops)
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        request = json.loads(body)
        self.calls.append((url, dict(headers), request))
        document = {
            "model": "reported-model",
            "content": [{"type": "text", "text": f"Profile {len(self.calls)}.\n\n#### Background\n\nBorn.\n"}],
            "stop_reason": self.stops.pop(0) if self.stops else "end_turn",
            "usage": {"input_tokens": 2000 + len(self.calls), "output_tokens": 300},
        }
        return HttpResponse(200, {}, json.dumps(document).encode("utf-8"))


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    fake = FakeTransport()
    monkeypatch.setattr("tinarrative.cli._transport", lambda: fake)
    monkeypatch.setattr("tinarrative.cli._sleep", lambda seconds: None)
    monkeypatch.setattr("tinarrative.cli._now", lambda: datetime(2026, 10, 22, 9, 0, tzinfo=UTC))
    monkeypatch.setenv("TEST_NARRATOR_KEY", KEY)
    return fake


@pytest.fixture
def sending(tmp_path: Path) -> str:
    """The selection of ``settings`` plus a provider."""
    path = tmp_path / "sending.toml"
    path.write_text(
        "[councilors]\nmin_tenure_days = 0\nrivals_per_faction = 1\n"
        '[llm]\nprovider = "anthropic"\nmodel = "some-model"\napi_key_env = "TEST_NARRATOR_KEY"\n',
        encoding="utf-8",
    )
    return str(path)


SEND_SAVE = "politics_before.json"
"""The fixture save whose dossier selects two councilors of two factions."""


def _send(tmp_path: Path, config: str, *options: str) -> int:
    return main(["councilors", SEND_SAVE, "--config", config, "--output", str(tmp_path / "out"), "--send", *options])


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.fixture
def test_a_dry_run_writes_one_request_per_councilor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], settings: str
) -> None:
    stale = tmp_path / "out" / "requests" / "09.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    dossier = _dossier(tmp_path, SEND_SAVE, "--config", settings)

    count = len(dossier["councilors"])  # type: ignore[arg-type]
    assert count == 2
    requests = sorted((tmp_path / "out" / "requests").iterdir())
    assert [path.name for path in requests] == [f"{index:02d}.json" for index in range(1, count + 1)]
    for index, path in enumerate(requests, start=1):
        expected = build_article_request(dossier, index)
        assert _read(path) == expected
        assert hashlib.sha256(path.read_bytes()).hexdigest() == request_sha256(expected)
    out = capsys.readouterr().out
    assert out.endswith(f"Wrote dossier.json and {count} requests to {tmp_path / 'out'}.\n")
    assert not (tmp_path / "out" / "responses").exists()


@pytest.mark.fixture
def test_send_writes_responses_articles_and_manifest(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str], sending: str
) -> None:
    assert _send(tmp_path, sending) == EXIT_SUCCESS

    out = tmp_path / "out"
    dossier = _read(out / "dossier.json")
    names = [entry["name"] for entry in dossier["councilors"]]
    responses = sorted((out / "responses").iterdir())
    assert len(responses) == len(names) == len(transport.calls)
    first = _read(responses[0])
    assert first == {
        "index": 1,
        "request_sha256": request_sha256(build_article_request(dossier, 1)),
        "provider": "anthropic",
        "model": "some-model",
        "max_output_tokens": 16000,
        "temperature": None,
        "reported_model": "reported-model",
        "finish": "complete",
        "input_tokens": 2001,
        "output_tokens": 300,
        "text": "Profile 1.\n\n#### Background\n\nBorn.\n",
    }
    url, headers, body = transport.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == KEY
    assert body["system"] == _read(out / "requests" / "01.json")["system"]
    assert body["messages"] == _read(out / "requests" / "01.json")["messages"]
    articles = (out / "councilors.md").read_text(encoding="utf-8")
    assert articles.startswith(
        "# Councilor profiles\n\n- Provider: anthropic\n- Model: reported-model (requested some-model)\n"
    )
    assert f"- Player faction: {dossier['player_faction']}\n" in articles
    assert articles.index(f"## {dossier['player_faction']}") < articles.index("### ")
    assert [line[4:] for line in articles.splitlines() if line.startswith("### ")] == names
    assert "Profile 1.\n\n#### Background" in articles
    manifest = _read(out / "manifest.json")
    assert all(row["written"] for row in manifest["articles"])
    assert (
        manifest["dossier_sha256"]
        == hashlib.sha256(json.dumps(dossier, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    )
    assert loyalty_keys(manifest) == []
    captured = capsys.readouterr()
    assert f"- 1 sent: complete, 2001 input and 300 output tokens ({names[0]})\n" in captured.out
    assert f"Wrote {len(names)} responses to {out / 'responses'}.\n" in captured.out
    assert captured.out.endswith(f"Wrote councilors.md and manifest.json to {out}.\n")
    assert captured.err == ""


def test_impossible_token_reservation_fails_before_sending_articles(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str], sending: str
) -> None:
    with Path(sending).open("a", encoding="utf-8") as config:
        config.write("tokens_per_minute = 1\n")

    assert _send(tmp_path, sending) == EXIT_PROVIDER_ERROR

    assert transport.calls == []
    assert "exceeds tokens_per_minute 1" in capsys.readouterr().err


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("stop", "message"), [("max_tokens", "stopped at max_output_tokens 16000"), ("refusal", "refused")]
)
def test_a_failed_article_is_skipped_and_the_run_exits_10_at_the_end(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str], sending: str, stop: str, message: str
) -> None:
    transport.stops = ["end_turn", stop]

    assert _send(tmp_path, sending) == EXIT_PROVIDER_ERROR

    out = tmp_path / "out"
    dossier = _read(out / "dossier.json")
    names = [entry["name"] for entry in dossier["councilors"]]
    assert len(transport.calls) == len(names)
    assert "02.json" not in [path.name for path in (out / "responses").iterdir()]
    assert len(list((out / "responses").iterdir())) == len(names) - 1
    articles = (out / "councilors.md").read_text(encoding="utf-8")
    assert f"### {names[1]}" not in articles and f"### {names[0]}" in articles
    manifest = _read(out / "manifest.json")
    row = manifest["articles"][1]
    assert row["written"] is False and row["finish"] == stop.replace("max_tokens", "length").replace(
        "refusal", "refused"
    )
    assert message in row["error"]
    err = capsys.readouterr().err
    assert f"tinarrative councilors: article 2: anthropic: {message}" in err or (
        "article 2: anthropic:" in err and message in err
    )
    assert f"1 of {len(names)} articles missing; see {out / 'manifest.json'}" in err


@pytest.mark.fixture
def test_an_http_failure_skips_the_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport: FakeTransport, capsys: pytest.CaptureFixture[str],
    sending: str,
) -> None:  # fmt: skip
    class Unauthorized:
        def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
            return HttpResponse(401, {}, b'{"error": {"message": "invalid x-api-key"}}')

    monkeypatch.setattr("tinarrative.cli._transport", Unauthorized)

    assert _send(tmp_path, sending) == EXIT_PROVIDER_ERROR

    out = tmp_path / "out"
    assert list((out / "responses").iterdir()) == []
    manifest = _read(out / "manifest.json")
    assert {row["finish"] for row in manifest["articles"]} == {"error"}
    assert all("HTTP 401: invalid x-api-key" in row["error"] for row in manifest["articles"])
    assert "## " not in (out / "councilors.md").read_text(encoding="utf-8")
    assert "article 1: anthropic: HTTP 401: invalid x-api-key" in capsys.readouterr().err


@pytest.mark.fixture
def test_a_rerun_reuses_the_stored_responses(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str], sending: str
) -> None:
    transport.stops = ["end_turn", "max_tokens"]
    assert _send(tmp_path, sending) == EXIT_PROVIDER_ERROR
    out = tmp_path / "out"
    count = len(_read(out / "dossier.json")["councilors"])
    first = (out / "responses" / "01.json").read_bytes()
    capsys.readouterr()

    assert _send(tmp_path, sending) == EXIT_SUCCESS

    captured = capsys.readouterr()
    assert len(transport.calls) == count + 1
    assert "- 1 kept: complete, 2001 input and 300 output tokens" in captured.out
    assert f"- 2 sent: complete, {2000 + count + 1} input and 300 output tokens" in captured.out
    assert f"Wrote 1 response to {out / 'responses'}, kept {count - 1} stored.\n" in captured.out
    assert captured.err == ""
    assert (out / "responses" / "01.json").read_bytes() == first
    assert all(row["written"] for row in _read(out / "manifest.json")["articles"])


@pytest.mark.fixture
@pytest.mark.parametrize("options", [["--force"], ["--model", "other-model"], ["--max-output-tokens", "8000"]])
def test_force_or_another_send_setting_sends_every_article_again(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str], sending: str, options: list[str]
) -> None:
    assert _send(tmp_path, sending) == EXIT_SUCCESS
    count = len(transport.calls)

    assert _send(tmp_path, sending, *options) == EXIT_SUCCESS

    assert len(transport.calls) == 2 * count
    assert "kept" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--force"], "--force re-sends articles, so it needs --send"),
        (["--send"], "--send needs --output DIR"),
        (["--send", "--output", "out", "--profile", "absent"], "unknown profile 'absent'"),
        (["--send", "--output", "out", "--model", ""], "--model: 'llm.model' must be a non-empty string"),
        (["--send", "--output", "out", "--provider", "ollama"], "no model"),
    ],
)
def test_send_usage_errors_contact_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transport: FakeTransport,
    capsys: pytest.CaptureFixture[str],
    settings: str,
    options: list[str],
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["councilors", *(str(FIXTURE_DIR / save) for save in SAVES), "--config", settings, *options]) == (
        EXIT_USAGE_ERROR
    )

    captured = capsys.readouterr()
    assert f"tinarrative councilors: {message}" in captured.err
    assert captured.out == ""
    assert transport.calls == []
    assert not (tmp_path / "out").exists()
