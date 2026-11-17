"""Coverage for tinarrative.narrator.runs: the policy of each product, through its step function.

Inputs are hand-built narrator packages and dossiers and the shared fake host; no save is parsed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.fake_host import FakeHost
from tests.narrator.test_chapters import _budget, _plan, _quarterly
from tests.narrator.test_councilors import DOSSIER
from tinarrative.config import NarratorSettings
from tinarrative.host import HttpResponse
from tinarrative.narrator.chapters import ChapterPlan
from tinarrative.narrator.providers import Endpoint
from tinarrative.narrator.run_directory import RunDirectory, RunDirectoryWriteError
from tinarrative.narrator.runs import HistoryReadError, assemble_history, narrate_history, write_articles
from tinarrative.narrator.send_run import SendOutcome

TARGET = Endpoint("anthropic", "https://api.anthropic.com", "key", 10, 1000)
NOW = datetime(2030, 1, 1, tzinfo=UTC)


class ScriptedTransport:
    """Answers each call with the next stop reason (``end_turn`` when exhausted)."""

    def __init__(self, *stops: str) -> None:
        self.stops = list(stops)
        self.calls = 0

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        self.calls += 1
        document = {
            "model": "reported",
            "content": [{"type": "text", "text": f"Prose {self.calls}."}],
            "stop_reason": self.stops.pop(0) if self.stops else "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        return HttpResponse(200, {}, json.dumps(document).encode())


class Reporter:
    def __init__(self) -> None:
        self.events: list[str] = []

    def written(self) -> None:
        self.events.append("written")

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


def _settings() -> NarratorSettings:
    return replace(_budget(30_000), provider="anthropic", model="chosen", max_output_tokens=100)


def _chapters() -> ChapterPlan:
    plan = _plan(_quarterly({position: 20_000 for position in range(4)}), _settings())
    assert len(plan.chapters) > 1
    return plan


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_narrate_history_sends_every_chapter_and_assembles_from_the_run_directory(tmp_path: Path) -> None:
    plan = _chapters()
    reporter = Reporter()

    run = narrate_history(
        plan,
        _settings(),
        TARGET,
        tmp_path,
        host=FakeHost(ScriptedTransport(), now=NOW).bundle(),
        reporter=reporter,
        force=False,
        version="1",
    )

    assert run.assembly is not None
    assert reporter.events == ["written", *["sent"] * len(plan.chapters), "summary"]
    assert (tmp_path / "history.md").read_text(encoding="utf-8") == run.assembly.history
    assert _json(tmp_path / "manifest.json") == run.assembly.manifest
    assert _json(tmp_path / "plan.json") == plan.to_dict()


def test_narrate_history_stops_at_the_first_failure_and_does_not_assemble(tmp_path: Path) -> None:
    plan = _chapters()
    transport = ScriptedTransport("max_tokens")
    reporter = Reporter()

    run = narrate_history(
        plan,
        _settings(),
        TARGET,
        tmp_path,
        host=FakeHost(transport, now=NOW).bundle(),
        reporter=reporter,
        force=False,
        version="1",
    )

    assert run.assembly is None
    assert transport.calls == 1
    assert [outcome.record is None for outcome in run.outcomes] == [True] * len(plan.chapters)
    assert reporter.events == ["written", "failed", "summary"]
    assert not (tmp_path / "history.md").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_narrate_history_names_the_path_of_a_failed_write(tmp_path: Path) -> None:
    blocker = tmp_path / "run"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(RunDirectoryWriteError) as error:
        narrate_history(
            _chapters(),
            _settings(),
            TARGET,
            blocker,
            host=FakeHost(ScriptedTransport(), now=NOW).bundle(),
            reporter=Reporter(),
            force=False,
            version="1",
        )

    assert blocker in (error.value.path, *error.value.path.parents)


def test_assemble_history_works_from_a_run_directory_alone(tmp_path: Path) -> None:
    plan = _chapters()
    sent = tmp_path / "sent"
    narrate_history(
        plan,
        _settings(),
        TARGET,
        sent,
        host=FakeHost(ScriptedTransport(), now=NOW).bundle(),
        reporter=Reporter(),
        force=False,
        version="1",
    )
    kept = {name: (sent / name).read_bytes() for name in ("history.md", "manifest.json")}
    for name in kept:
        (sent / name).unlink()

    assembled = assemble_history(sent, host=FakeHost(ScriptedTransport(), now=NOW).bundle(), version="1")

    assert assembled.chapters == len(plan.chapters)
    assert {name: (sent / name).read_bytes() for name in kept} == kept


def test_assemble_history_without_a_plan_is_unreadable(tmp_path: Path) -> None:
    with pytest.raises(HistoryReadError):
        assemble_history(tmp_path, host=FakeHost(ScriptedTransport(), now=NOW).bundle(), version="1")


def test_write_articles_carries_on_after_a_failure_and_lists_it_in_the_manifest(tmp_path: Path) -> None:
    transport = ScriptedTransport("end_turn", "max_tokens", "end_turn")
    reporter = Reporter()

    run = write_articles(
        DOSSIER,
        _settings(),
        TARGET,
        tmp_path,
        host=FakeHost(transport, now=NOW).bundle(),
        reporter=reporter,
        force=False,
        version="1",
    )

    assert transport.calls == len(DOSSIER["councilors"]) == 3
    assert [outcome.record is None for outcome in run.outcomes] == [False, True, False]
    assert reporter.events == ["written", "sent", "failed", "sent", "summary"]
    rows = run.manifest["articles"]
    assert [row["written"] for row in rows] == [True, False, True]
    assert rows[1]["finish"] == "length" and rows[1]["error"]
    assert _json(tmp_path / "manifest.json") == run.manifest
    assert (tmp_path / "councilors.md").exists()
    assert _json(tmp_path / "dossier.json") == DOSSIER


def test_write_articles_names_the_path_of_a_failed_write(tmp_path: Path) -> None:
    blocker = tmp_path / "run"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(RunDirectoryWriteError):
        write_articles(
            DOSSIER,
            _settings(),
            TARGET,
            blocker,
            host=FakeHost(ScriptedTransport(), now=NOW).bundle(),
            reporter=Reporter(),
            force=False,
            version="1",
        )

    assert not RunDirectory(blocker).manifest_path.exists()
