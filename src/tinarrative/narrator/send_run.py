"""Provider sending for narrator run directories."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..config import NarratorSettings
from ..host import Host
from ..log import fields, get_logger
from .providers import Endpoint, ProviderError, complete, completion_request
from .rate_limit import RateLimiter, estimate_tokens
from .run_directory import RunDirectory

logger = get_logger(__name__)


@dataclass(frozen=True)
class SendItem:
    index: int
    request: dict[str, Any]
    request_sha256: str
    extra: dict[str, Any]
    tag: str
    subject: str | None = None


@dataclass(frozen=True)
class SendOutcome:
    item: SendItem
    record: dict[str, Any] | None
    kept: bool
    finish: str | None
    error: str | None


class SendReporter(Protocol):
    def kept(self, outcome: SendOutcome, tokens: tuple[int | None, int | None]) -> None: ...
    def sent(self, outcome: SendOutcome) -> None: ...
    def failed(self, outcome: SendOutcome, provider: str) -> None: ...
    def waiting(self, seconds: float) -> None: ...
    def ready(self) -> None: ...
    def summary(self, outcomes: Sequence[SendOutcome], responses: Path, stopped: bool) -> None: ...


def send_run(
    items: Sequence[SendItem],
    settings: NarratorSettings,
    target: Endpoint,
    directory: Path,
    *,
    host: Host,
    reporter: SendReporter,
    force: bool,
    stop_on_failure: bool = False,
) -> list[SendOutcome]:
    run_directory = RunDirectory(directory)
    count = len(items)
    responses = run_directory.prepare_responses(count)
    prepared: list[tuple[SendItem, Any, dict[str, Any] | None, int, dict[str, Any]]] = []
    impossible: dict[int, int] = {}
    for item in items:
        request = completion_request(item.request, settings)
        sent_with = run_directory.sent_with(
            target.provider, request.model, request.max_output_tokens, request.temperature
        )
        stored = (
            None
            if force
            else run_directory.kept_response(item.index, count, request_sha256=item.request_sha256, sent_with=sent_with)
        )
        reserved = estimate_tokens(request.system, request.user, settings.chars_per_token, settings.max_output_tokens)
        if stored is None and settings.tokens_per_minute is not None and reserved > settings.tokens_per_minute:
            impossible[item.index] = reserved
        prepared.append((item, request, stored, reserved, sent_with))

    outcomes: list[SendOutcome] = []
    if impossible:
        for item, _, stored, _, _ in prepared:
            if stored is not None:
                finish, _, _ = run_directory.response_progress(stored)
                outcome = SendOutcome(item, stored, True, finish, None)
                outcomes.append(outcome)
            else:
                reason = (
                    f"estimated request reservation {impossible[item.index]} tokens exceeds "
                    f"tokens_per_minute {settings.tokens_per_minute}"
                    if item.index in impossible
                    else "not sent because another request exceeds tokens_per_minute"
                )
                outcome = SendOutcome(item, None, False, "error", reason)
                outcomes.append(outcome)
                reporter.failed(outcome, target.provider)
        reporter.summary(outcomes, responses, True)
        return outcomes

    limiter = RateLimiter(
        settings.requests_per_minute,
        settings.tokens_per_minute,
        clock=host.monotonic,
        sleep=host.sleep,
        on_wait=reporter.waiting,
        on_ready=reporter.ready,
    )
    stopped = False
    for position, (item, request, stored, reserved, sent_with) in enumerate(prepared):
        command = "narrate" if item.tag == "chapter" else "councilors"
        if stored is not None:
            finish, input_tokens, output_tokens = run_directory.response_progress(stored)
            outcome = SendOutcome(item, stored, True, finish, None)
            outcomes.append(outcome)
            logger.info(
                "%s kept %s", command, fields(**{item.tag: item.index}, provider=target.provider, finish=finish)
            )
            reporter.kept(outcome, (input_tokens, output_tokens))
            continue
        failure: tuple[str, str] | None = None
        completion = None
        try:

            def before_attempt(reservation: int = reserved) -> None:
                limiter.acquire(reservation)

            completion = complete(
                request,
                target,
                host.transport,
                sleep=host.sleep,
                now=host.now,
                before_attempt=before_attempt,
                chapter=item.index,
            )
            failure_reason = {
                "length": (f"the completion stopped at max_output_tokens {request.max_output_tokens}"),
                "refused": "the model refused the request",
                "empty": "the completion has no text",
            }.get(completion.finish)
            failure = (completion.finish, failure_reason) if failure_reason else None
        except ProviderError as error:
            logger.info(
                "%s send failed %s",
                command,
                fields(**{item.tag: item.index}, provider=target.provider, kind=error.kind, status=error.status),
            )
            failure = ("error", str(error))
        if failure:
            if completion is not None:
                logger.info(
                    "%s send failed %s",
                    command,
                    fields(**{item.tag: item.index}, provider=target.provider, finish=failure[0]),
                )
            outcome = SendOutcome(item, None, False, failure[0], failure[1])
            outcomes.append(outcome)
            reporter.failed(outcome, target.provider)
            if stop_on_failure:
                stopped = True
                outcomes.extend(
                    SendOutcome(remaining, None, False, None, "not sent because an earlier item failed")
                    for remaining, _, _, _, _ in prepared[position + 1 :]
                )
                break
            continue
        assert completion is not None
        record = run_directory.response_record(
            index=item.index,
            request_sha256=item.request_sha256,
            sent_with=sent_with,
            reported_model=completion.model,
            finish=completion.finish,
            extra=item.extra,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            text=completion.text,
        )
        run_directory.write_response(item.index, count, record)
        outcome = SendOutcome(item, record, False, completion.finish, None)
        outcomes.append(outcome)
        logger.info(
            "%s sent %s",
            command,
            fields(
                **{item.tag: item.index},
                provider=target.provider,
                finish=completion.finish,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                **item.extra,
                characters=len(completion.text),
            ),
        )
        reporter.sent(outcome)
    reporter.summary(outcomes, responses, stopped)
    return outcomes
