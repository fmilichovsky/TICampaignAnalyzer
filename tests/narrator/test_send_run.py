from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.fake_host import FakeHost
from tinarrative.config import NarratorSettings
from tinarrative.host import HttpResponse
from tinarrative.narrator.providers import Endpoint
from tinarrative.narrator.run_directory import RunDirectory, RunDirectoryWriteError
from tinarrative.narrator.send_run import SendItem, SendOutcome, send_run


class HostTransport:
    def __init__(self, *, stop: str = "end_turn", status: int = 200) -> None:
        self.calls = 0
        self.stop = stop
        self.status = status

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        self.calls += 1
        request = json.loads(body)
        if url.endswith("/v1/messages"):
            result = {
                "model": "returned",
                "content": [{"type": "text", "text": "A response."}],
                "stop_reason": self.stop,
                "usage": {"input_tokens": 12, "output_tokens": 4},
            }
        else:
            raise AssertionError(request)
        return HttpResponse(self.status, {}, json.dumps(result).encode())


class Reporter:
    def __init__(self) -> None:
        self.events: list[str] = []

    def kept(self, outcome: SendOutcome, tokens: tuple[int | None, int | None]) -> None:
        self.events.append("kept")

    def sent(self, outcome: SendOutcome) -> None:
        self.events.append("sent")

    def failed(self, outcome: SendOutcome, provider: str) -> None:
        self.events.append("failed")

    def waiting(self, seconds: float) -> None:
        self.events.append("waiting")

    def ready(self) -> None:
        self.events.append("ready")

    def summary(self, outcomes: Sequence[SendOutcome], responses: Path, stopped: bool) -> None:
        self.events.append("summary")


def test_send_run_writes_then_keeps_matching_response_unless_forced(tmp_path: Path) -> None:
    transport = HostTransport()
    host = FakeHost(transport)
    settings = NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=100)
    endpoint = Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000)
    item = SendItem(
        1,
        {"system": "system", "messages": [{"role": "user", "content": "tell it"}]},
        "abc",
        {"estimate": 7},
        "chapter",
        "7",
    )
    directory = tmp_path / "run"
    RunDirectory(directory).write_requests([(1, item.request)])

    reporter = Reporter()
    outcomes = send_run([item], settings, endpoint, directory, host=host.bundle(), reporter=reporter, force=False)

    assert outcomes[0].record == {
        "index": 1,
        "request_sha256": "abc",
        "provider": "anthropic",
        "model": "chosen",
        "max_output_tokens": 100,
        "temperature": None,
        "reported_model": "returned",
        "finish": "complete",
        "estimate": 7,
        "input_tokens": 12,
        "output_tokens": 4,
        "text": "A response.",
    }
    assert reporter.events == ["sent", "summary"]
    assert transport.calls == 1

    reporter = Reporter()
    kept = send_run([item], settings, endpoint, directory, host=host.bundle(), reporter=reporter, force=False)
    assert kept[0].kept
    assert reporter.events == ["kept", "summary"]
    assert transport.calls == 1

    send_run([item], settings, endpoint, directory, host=host.bundle(), reporter=Reporter(), force=True)
    assert transport.calls == 2


def test_send_run_removes_responses_left_by_a_longer_run(tmp_path: Path) -> None:
    transport = HostTransport()
    host = FakeHost(transport)
    item = SendItem(1, {"system": "system", "messages": [{"role": "user", "content": "tell it"}]}, "abc", {}, "article")
    directory = tmp_path / "run"
    stale = directory / "responses" / "09.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    send_run(
        [item],
        NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=100),
        Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000),
        directory,
        host=host.bundle(),
        reporter=Reporter(),
        force=False,
    )

    assert sorted(path.name for path in (directory / "responses").iterdir()) == ["01.json"]


def test_send_run_paces_requests_and_reports_the_wait(tmp_path: Path) -> None:
    transport = HostTransport()
    host = FakeHost(transport)
    items = [
        SendItem(index, {"system": "s", "messages": [{"role": "user", "content": "u"}]}, str(index), {}, "chapter")
        for index in (1, 2)
    ]
    reporter = Reporter()
    settings = NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=10, requests_per_minute=1)

    send_run(
        items,
        settings,
        Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000),
        tmp_path / "run",
        host=host.bundle(),
        reporter=reporter,
        force=False,
    )

    assert host.waits == [60]
    assert reporter.events == ["sent", "waiting", "ready", "sent", "summary"]


@pytest.mark.parametrize(("stop", "finish"), [("max_tokens", "length"), ("refusal", "refused")])
def test_send_run_returns_length_and_refusal_as_failed_outcomes(tmp_path: Path, stop: str, finish: str) -> None:
    transport = HostTransport(stop=stop)
    reporter = Reporter()
    item = SendItem(1, {"system": "s", "messages": [{"role": "user", "content": "u"}]}, "abc", {}, "chapter")

    second = SendItem(2, {"system": "s", "messages": [{"role": "user", "content": "next"}]}, "next", {}, "chapter")
    result = send_run(
        [item, second],
        NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=10),
        Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000),
        tmp_path / "run",
        host=FakeHost(transport).bundle(),
        reporter=reporter,
        force=False,
        stop_on_failure=True,
    )

    assert result[0].finish == finish
    assert result[0].record is None
    assert result[1].item == second
    assert result[1].error == "not sent because an earlier item failed"
    assert reporter.events == ["failed", "summary"]


def test_send_run_returns_provider_errors_without_writing_a_response(tmp_path: Path) -> None:
    transport = HostTransport(status=500)
    reporter = Reporter()
    item = SendItem(1, {"system": "s", "messages": [{"role": "user", "content": "u"}]}, "abc", {}, "article")

    result = send_run(
        [item],
        NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=10),
        Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000),
        tmp_path / "run",
        host=FakeHost(transport).bundle(),
        reporter=reporter,
        force=False,
    )

    assert result[0].finish == "error"
    assert result[0].record is None
    assert not (tmp_path / "run" / "responses" / "01.json").exists()
    assert reporter.events == ["failed", "summary"]


def test_send_run_checks_token_limits_once_and_keeps_existing_responses(tmp_path: Path) -> None:
    transport = HostTransport()
    host = FakeHost(transport)
    settings = NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=10)
    endpoint = Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000)
    first = SendItem(1, {"system": "s", "messages": [{"role": "user", "content": "u"}]}, "one", {}, "chapter")
    second = SendItem(2, {"system": "s", "messages": [{"role": "user", "content": "v"}]}, "two", {}, "chapter")
    directory = tmp_path / "run"
    send_run([first], settings, endpoint, directory, host=host.bundle(), reporter=Reporter(), force=False)
    calls = transport.calls
    reporter = Reporter()

    result = send_run(
        [first, second],
        replace(settings, tokens_per_minute=1),
        endpoint,
        directory,
        host=host.bundle(),
        reporter=reporter,
        force=False,
    )

    assert transport.calls == calls
    assert result[0].kept and result[1].record is None
    assert result[1].finish == "error"
    assert "exceeds tokens_per_minute 1" in (result[1].error or "")
    assert reporter.events == ["failed", "summary"]


def test_send_run_raises_the_run_directory_write_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "run" / "responses" / "01.json"
    error = OSError("disk full")

    def fail_write(self: RunDirectory, index: int, count: int, record: Mapping[str, Any]) -> None:
        raise RunDirectoryWriteError(target, error)

    monkeypatch.setattr(RunDirectory, "write_response", fail_write)
    item = SendItem(1, {"system": "s", "messages": [{"role": "user", "content": "u"}]}, "abc", {}, "article")

    with pytest.raises(RunDirectoryWriteError, match="disk full") as caught:
        send_run(
            [item],
            NarratorSettings(provider="anthropic", model="chosen", max_output_tokens=10),
            Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000),
            tmp_path / "run",
            host=FakeHost(HostTransport()).bundle(),
            reporter=Reporter(),
            force=False,
        )

    assert caught.value.path == target
