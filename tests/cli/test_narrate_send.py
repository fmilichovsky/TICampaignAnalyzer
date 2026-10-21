"""Coverage for `tinarrative narrate --send` with a fake transport: responses, profiles, failures and the log."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures import FIXTURES_ROOT
from tinarrative.cli import EXIT_PROVIDER_ERROR, EXIT_SUCCESS, EXIT_USAGE_ERROR, main
from tinarrative.narrator.transport import HttpResponse

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"
SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]
KEY = "sk-test-0123456789-secret"
PROSE = "The Resistance quietly took the capital."


class FakeTransport:
    """Answers Anthropic or Ollama completions by URL; ``stops`` gives the Anthropic stop reason per call
    (``end_turn`` when exhausted)."""

    def __init__(self, *stops: str) -> None:
        self.stops = list(stops)
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        self.calls.append((url, dict(headers), json.loads(body)))
        text = f"{PROSE} ({len(self.calls)})"
        document: dict[str, Any] = {
            "model": "reported-model",
            "content": [{"type": "text", "text": text}],
            "stop_reason": self.stops.pop(0) if self.stops else "end_turn",
            "usage": {"input_tokens": 2000 + len(self.calls), "output_tokens": 300},
        }
        if url.endswith("/api/chat"):
            document = {"model": "local", "message": {"content": text}, "done_reason": "stop", "eval_count": 9}
        return HttpResponse(200, {}, json.dumps(document).encode("utf-8"))


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    fake = FakeTransport()
    monkeypatch.setattr("tinarrative.cli._transport", lambda: fake)
    monkeypatch.setattr("tinarrative.cli._sleep", lambda seconds: None)
    monkeypatch.setenv("TEST_NARRATOR_KEY", KEY)
    monkeypatch.chdir(FIXTURE_DIR)
    return fake


def _settings(tmp_path: Path, text: str = "") -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(
        '[narrator]\nmax_input_tokens = 9000\nprovider = "anthropic"\nmodel = "some-model"\n'
        'api_key_env = "TEST_NARRATOR_KEY"\n' + text,
        encoding="utf-8",
    )
    return path


def _narrate(tmp_path: Path, *options: str, settings: Path | None = None) -> int:
    config = settings or _settings(tmp_path)
    return main(["narrate", *SAVES, "--config", str(config), "--output", str(tmp_path / "out"), *options])


@pytest.mark.fixture
def test_send_writes_one_response_per_chapter(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str]
) -> None:
    stale = tmp_path / "out" / "responses" / "07.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    assert _narrate(tmp_path, "--send") == EXIT_SUCCESS

    out = capsys.readouterr().out
    plan = json.loads((tmp_path / "out" / "plan.json").read_text(encoding="utf-8"))
    responses = sorted((tmp_path / "out" / "responses").iterdir())
    assert [path.name for path in responses] == ["01.json", "02.json"]
    first = json.loads(responses[0].read_text(encoding="utf-8"))
    assert first == {
        "index": 1,
        "request_sha256": plan["chapters"][0]["request_sha256"],
        "provider": "anthropic",
        "model": "some-model",
        "max_output_tokens": 16000,
        "temperature": None,
        "reported_model": "reported-model",
        "finish": "complete",
        "estimate": plan["chapters"][0]["estimate"],
        "input_tokens": 2001,
        "output_tokens": 300,
        "text": f"{PROSE} (1)",
    }
    request = json.loads((tmp_path / "out" / "requests" / "01.json").read_text(encoding="utf-8"))
    url, headers, body = transport.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == KEY
    assert body["system"] == request["system"]
    assert body["messages"] == request["messages"]
    assert "- 1 sent: complete, 2001 input and 300 output tokens" in out
    assert out.endswith(f"Wrote 2 responses to {tmp_path / 'out' / 'responses'}.\n")


@pytest.mark.fixture
def test_the_provider_settings_never_change_the_plan_or_the_requests(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = tmp_path / "plain.toml"
    plain.write_text("[narrator]\nmax_input_tokens = 9000\n", encoding="utf-8")

    assert main(["narrate", *SAVES, "--config", str(plain), "--output", str(tmp_path / "plain")]) == EXIT_SUCCESS
    assert _narrate(tmp_path, "--send", "--model", "other-model") == EXIT_SUCCESS

    for name in ("plan.json", "requests/01.json", "requests/02.json"):
        assert (tmp_path / "plain" / name).read_bytes() == (tmp_path / "out" / name).read_bytes()


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("stop", "message"), [("max_tokens", "stopped at max_output_tokens 16000"), ("refusal", "refused")]
)
def test_a_failed_chapter_stops_the_run_and_keeps_the_completed_ones(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str], stop: str, message: str
) -> None:
    transport.stops = ["end_turn", stop]

    assert _narrate(tmp_path, "--send") == EXIT_PROVIDER_ERROR

    err = capsys.readouterr().err
    assert "chapter 2: anthropic: " in err and message in err
    assert [path.name for path in (tmp_path / "out" / "responses").iterdir()] == ["01.json"]


@pytest.mark.fixture
def test_an_http_failure_is_a_provider_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport: FakeTransport, capsys: pytest.CaptureFixture[str]
) -> None:
    class Unauthorized:
        def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
            return HttpResponse(401, {}, b'{"error": {"message": "invalid x-api-key"}}')

    monkeypatch.setattr("tinarrative.cli._transport", Unauthorized)

    assert _narrate(tmp_path, "--send") == EXIT_PROVIDER_ERROR

    assert "chapter 1: anthropic: HTTP 401: invalid x-api-key" in capsys.readouterr().err
    assert list((tmp_path / "out" / "responses").iterdir()) == []


@pytest.mark.fixture
def test_a_profile_and_flags_override_the_narrator_keys(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _settings(
        tmp_path,
        '\n[narrator.profiles.local]\nprovider = "ollama"\nmodel = "local-model"\nbase_url = "http://box:11434"\n'
        "max_input_tokens = 200000\nmax_output_tokens = 4000\ntemperature = 0.4\n",
    )

    code = _narrate(tmp_path, "--send", "--profile", "local", "--max-output-tokens", "5000", settings=settings)

    assert code == EXIT_SUCCESS
    url, headers, body = transport.calls[0]
    assert url == "http://box:11434/api/chat"
    assert body["model"] == "local-model"
    assert body["options"] == {"num_ctx": 205_000, "num_predict": 5000, "temperature": 0.4}
    assert headers["authorization"] == f"Bearer {KEY}"
    assert "1 chapter by quarter, max_input_tokens 200000" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("options", "settings_text", "message"),
    [
        (["--send", "--profile", "absent"], None, "unknown profile 'absent' (the settings define: none)"),
        (["--max-input-tokens", "10"], None, "--max-input-tokens: 'narrator.max_input_tokens' must be at least 1000"),
        (["--send", "--model", ""], None, "--model: 'narrator.model' must be a non-empty string"),
        (["--send"], "[narrator]\nprovider = 'ollama'\n", "no model"),
        (["--send"], "[narrator]\nprovider = 'anthropic'\nmodel = 'm'\n", "anthropic needs an API key"),
        (
            ["--send"],
            "[narrator]\nprovider = 'openai'\nmodel = 'm'\napi_key_env = 'TEST_UNSET_KEY'\n",
            "TEST_UNSET_KEY (narrator.api_key_env) is not set",
        ),
        (
            ["--send"],
            "[narrator]\nprovider = 'ollama'\nmodel = 'm'\nmax_input_tokens = 30000\ncontext_window = 32768\n",
            "over context_window 32768",
        ),
    ],
)
def test_send_usage_errors_contact_nothing(
    tmp_path: Path,
    transport: FakeTransport,
    capsys: pytest.CaptureFixture[str],
    options: list[str],
    settings_text: str | None,
    message: str,
) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(settings_text or "", encoding="utf-8")

    assert main(["narrate", *SAVES, "--config", str(config), "--output", str(tmp_path / "out"), *options]) == (
        EXIT_USAGE_ERROR
    )

    captured = capsys.readouterr()
    assert message in captured.err
    assert captured.out == ""
    assert transport.calls == []
    assert not (tmp_path / "out").exists()


def test_send_needs_an_output_directory(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["narrate", *SAVES, "--config", str(_settings(tmp_path)), "--send"]) == EXIT_USAGE_ERROR

    assert "--send needs --output DIR" in capsys.readouterr().err
    assert transport.calls == []


@pytest.mark.fixture
def test_the_log_carries_no_request_response_or_key(
    tmp_path: Path, transport: FakeTransport, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--log-level", "debug", "narrate", *SAVES, "--config", str(_settings(tmp_path)),
                 "--output", str(tmp_path / "out"), "--send"]) == EXIT_SUCCESS  # fmt: skip

    err = capsys.readouterr().err
    request = json.loads((tmp_path / "out" / "requests" / "01.json").read_text(encoding="utf-8"))
    lines = err.splitlines()
    assert any("narrate sent" in line and "chapter=1" in line for line in lines)
    assert any("provider response" in line and "status=200" in line for line in lines)
    assert KEY not in err
    assert PROSE not in err
    assert request["system"].splitlines()[0] not in err
    assert "Fixture Resistance" not in err
