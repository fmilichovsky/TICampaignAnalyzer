"""One step function per narrator product; each states its own policy so the CLI only wires."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..config import NarratorSettings
from ..host import Host
from ..log import fields, get_logger
from .assembly import Assembly, assemble, parse_plan, stored_chapter
from .chapters import ChapterPlan
from .councilors import article_requests, assemble_articles, missing, request_sha256
from .providers import Endpoint
from .run_directory import RunDirectory
from .send_run import SendItem, SendOutcome, SendReporter, send_run

logger = get_logger(__name__)


class HistoryReadError(Exception):
    """The run directory cannot be read back for assembly; ``error`` is the ``OSError`` or ``ValueError``."""

    def __init__(self, error: OSError | ValueError) -> None:
        self.error = error
        super().__init__(str(error))


class RunReporter(SendReporter, Protocol):
    def written(self) -> None:
        """The plan or dossier and the requests are on disk; sending starts next."""


@dataclass(frozen=True)
class HistoryRun:
    outcomes: list[SendOutcome]
    assembly: Assembly | None
    """``None`` when a chapter failed: narrate stops there and assembles nothing."""


@dataclass(frozen=True)
class AssembledHistory:
    assembly: Assembly
    chapters: int


@dataclass(frozen=True)
class ArticlesRun:
    outcomes: list[SendOutcome]
    manifest: dict[str, Any]


def chapter_items(plan: ChapterPlan) -> list[SendItem]:
    return [
        SendItem(
            planned.index,
            planned.request,
            planned.request_sha256,
            {"estimate": planned.estimate},
            "chapter",
            str(planned.estimate),
        )
        for planned in plan.chapters
    ]


def article_items(dossier: Mapping[str, Any]) -> list[SendItem]:
    return [
        SendItem(index, request, request_sha256(request), {}, "article", entry["name"])
        for (index, request), entry in zip(article_requests(dossier), dossier["councilors"], strict=True)
    ]


def narrate_history(
    plan: ChapterPlan,
    settings: NarratorSettings,
    target: Endpoint,
    directory: Path,
    *,
    host: Host,
    reporter: RunReporter,
    force: bool,
    version: str,
) -> HistoryRun:
    """Write the plan and requests, send them stopping at the first failure, and assemble the history from the
    run directory only when every chapter succeeded.

    Raises :class:`RunDirectoryWriteError` on a failed write and :class:`HistoryReadError` when the finished run
    cannot be read back."""
    items = chapter_items(plan)
    RunDirectory(directory).write_plan(plan.to_dict(), [(item.index, item.request) for item in items])
    reporter.written()
    outcomes = send_run(
        items, settings, target, directory, host=host, reporter=reporter, force=force, stop_on_failure=True
    )
    if any(outcome.record is None for outcome in outcomes):
        return HistoryRun(outcomes, None)
    return HistoryRun(outcomes, assemble_history(directory, host=host, version=version).assembly)


def assemble_history(directory: Path, *, host: Host, version: str) -> AssembledHistory:
    """Write ``history.md`` and ``manifest.json`` from what the run directory holds, nothing else.

    Raises :class:`HistoryReadError` when the directory cannot be read and :class:`RunDirectoryWriteError` when
    the history cannot be written."""
    run_directory = RunDirectory(directory)
    try:
        plan = parse_plan(run_directory.read_plan())
        count = len(plan["chapters"])
        chapters = [
            stored_chapter(
                entry,
                run_directory.read_optional(run_directory.request_path(entry["index"], count)),
                run_directory.read_response(entry["index"], count),
            )
            for entry in plan["chapters"]
        ]
    except (OSError, ValueError) as error:
        raise HistoryReadError(error) from error
    assembly = assemble(chapters, plan, generated=host.now(), version=version)
    run_directory.write_history(assembly.history, json.dumps(assembly.manifest, ensure_ascii=False, indent=2) + "\n")
    audit = assembly.manifest["audit"]
    logger.info(
        "narrate assembled %s",
        fields(
            chapters=count,
            footnotes=audit["footnotes"],
            cited_ids=audit["cited_ids"],
            **{kind: len(audit[kind] or ()) for kind in ("unmatched", "uncited", "undefined", "unreferenced")},
        ),
    )
    return AssembledHistory(assembly, count)


def write_articles(
    dossier: dict[str, Any],
    settings: NarratorSettings,
    target: Endpoint,
    directory: Path,
    *,
    host: Host,
    reporter: RunReporter,
    force: bool,
    version: str,
) -> ArticlesRun:
    """Write the dossier and requests, send them carrying on after a failure, and assemble the articles from the
    outcomes and the dossier; a failed article is listed in the manifest with its finish and reason.

    Raises :class:`RunDirectoryWriteError` on a failed write."""
    items = article_items(dossier)
    run_directory = RunDirectory(directory)
    run_directory.write_dossier(dossier, [(item.index, item.request) for item in items])
    reporter.written()
    outcomes = send_run(items, settings, target, directory, host=host, reporter=reporter, force=force)
    return ArticlesRun(outcomes, _assemble_articles(run_directory, dossier, outcomes, settings, target, host, version))


def _assemble_articles(
    run_directory: RunDirectory,
    dossier: dict[str, Any],
    outcomes: Sequence[SendOutcome],
    settings: NarratorSettings,
    target: Endpoint,
    host: Host,
    version: str,
) -> dict[str, Any]:
    sent_with = run_directory.sent_with(
        target.provider, settings.model, settings.max_output_tokens, settings.temperature
    )
    stored: dict[int, dict[str, Any]] = {}
    for outcome in outcomes:
        if outcome.record is not None:
            stored[outcome.item.index] = outcome.record
        elif outcome.error is not None:
            stored[outcome.item.index] = run_directory.failure_record(sent_with, outcome.finish, outcome.error)
    markdown, manifest = assemble_articles(dossier, stored, generated=host.now(), version=version, sent_with=sent_with)
    run_directory.write_articles(markdown, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    total = len(manifest["articles"])
    absent = len(missing(manifest))
    logger.info("councilors assembled %s", fields(articles=total, written=total - absent, missing=absent))
    return manifest
