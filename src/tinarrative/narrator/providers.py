"""The providers of ``tinarrative narrate --send``. See architecture 20.5.

The API key, request text and response text are never logged.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from ..config import NarratorSettings
from ..log import fields, get_logger
from .transport import HttpResponse, Transport, TransportError

logger = get_logger(__name__)

FINISHES = ("complete", "length", "refused", "other")
DEFAULT_URLS = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434",
}
ANTHROPIC_VERSION = "2023-06-01"
MAX_ATTEMPTS = 4
"""One request and at most three retries."""
RETRIED_STATUSES = frozenset({408, 409, 429})
"""Retried besides every 5xx status."""
MAX_WAIT_SECONDS = 60.0
DETAIL_LIMIT = 200
"""A provider's error message is shown up to this many characters."""


@dataclass(frozen=True)
class CompletionRequest:
    system: str
    user: str
    model: str
    max_output_tokens: int
    temperature: float | None = None


@dataclass(frozen=True)
class Completion:
    text: str
    finish: str
    model: str | None
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class Endpoint:
    provider: str
    base_url: str
    key: str | None
    timeout: float
    context_length: int


class ProviderError(Exception):
    """``kind`` is ``auth`` (401, 403), ``http`` (another status), ``network`` (no response) or
    ``invalid_response`` (a success status whose body is not the provider's response)."""

    def __init__(self, kind: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


def endpoint(settings: NarratorSettings, environ: Mapping[str, str]) -> Endpoint:
    """Raises ``ValueError`` naming the setting when the settings cannot send."""
    provider = settings.provider
    if provider is None:
        raise ValueError("no provider: set narrator.provider (or a profile's provider) or give --provider")
    if settings.model is None:
        raise ValueError("no model: set narrator.model (or a profile's model) or give --model")
    needed = settings.max_input_tokens + settings.max_output_tokens
    if settings.context_window is not None and needed > settings.context_window:
        raise ValueError(
            f"max_input_tokens {settings.max_input_tokens} plus max_output_tokens {settings.max_output_tokens} is "
            f"{needed}, over context_window {settings.context_window}"
        )
    base_url = settings.base_url or DEFAULT_URLS[provider]
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("base_url must start with http:// or https://")
    name = settings.api_key_env
    if name is None and (
        provider in {"anthropic", "openrouter"} or (provider == "openai" and settings.base_url is None)
    ):
        raise ValueError(
            f"{provider} needs an API key: set narrator.api_key_env to the name of the environment variable that "
            "holds it"
        )
    key = None
    if name is not None:
        key = environ.get(name, "")
        if not key:
            raise ValueError(f"the environment variable {name} (narrator.api_key_env) is not set")
    return Endpoint(provider, base_url.rstrip("/"), key, float(settings.timeout_seconds), needed)


def completion_request(request: Mapping[str, Any], settings: NarratorSettings) -> CompletionRequest:
    if settings.model is None:
        raise ValueError("no model")
    return CompletionRequest(
        system=request["system"],
        user="\n\n".join(message["content"] for message in request["messages"]),
        model=settings.model,
        max_output_tokens=settings.max_output_tokens,
        temperature=settings.temperature,
    )


def complete(
    request: CompletionRequest,
    target: Endpoint,
    transport: Transport,
    *,
    sleep: Callable[[float], None] = time.sleep,
    before_attempt: Callable[[], None] | None = None,
    chapter: int | None = None,
) -> Completion:
    """Retries rate limits and server errors, honouring ``Retry-After``; raises ``ProviderError`` once the retries
    are used up."""
    adapter = ADAPTERS[target.provider]
    url = target.base_url + adapter.path
    headers = {"content-type": "application/json", **adapter.headers(target.key)}
    body = json.dumps(adapter.body(request, target), ensure_ascii=False).encode("utf-8")
    attempt = 0
    while True:
        attempt += 1
        if before_attempt is not None:
            before_attempt()
        try:
            response = transport.post(url, headers, body, target.timeout)
        except TransportError as error:
            logger.info(
                "provider no response %s",
                fields(provider=target.provider, chapter=chapter, attempt=attempt, timeout=error.timeout),
            )
            if error.timeout or attempt >= MAX_ATTEMPTS:
                reason = "timed out" if error.timeout else str(error)
                raise ProviderError("network", f"no response: {reason}") from None
            wait = _backoff(attempt)
        else:
            logger.info(
                "provider response %s",
                fields(
                    provider=target.provider,
                    chapter=chapter,
                    attempt=attempt,
                    status=response.status,
                    sent=len(body),
                    received=len(response.body),
                ),
            )
            if 200 <= response.status < 300:
                return _decode(adapter, response)
            retried = response.status in RETRIED_STATUSES or response.status >= 500
            if not retried or attempt >= MAX_ATTEMPTS:
                raise _status_error(response)
            hinted = _retry_after(response.headers)
            wait = _backoff(attempt) if hinted is None else hinted
        logger.info("provider retry %s", fields(provider=target.provider, chapter=chapter, attempt=attempt, wait=wait))
        sleep(wait)


# Adapters


@dataclass(frozen=True)
class _Adapter:
    path: str
    headers: Callable[[str | None], dict[str, str]]
    body: Callable[[CompletionRequest, Endpoint], dict[str, Any]]
    decode: Callable[[Mapping[str, Any]], Completion]


def _bearer(key: str | None) -> dict[str, str]:
    return {} if key is None else {"authorization": f"Bearer {key}"}


def _anthropic_headers(key: str | None) -> dict[str, str]:
    return {"anthropic-version": ANTHROPIC_VERSION, **({} if key is None else {"x-api-key": key})}


def _anthropic_body(request: CompletionRequest, target: Endpoint) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": request.model,
        "max_tokens": request.max_output_tokens,
        "system": request.system,
        "messages": [{"role": "user", "content": request.user}],
    }
    if request.temperature is not None:
        body["temperature"] = request.temperature
    return body


_ANTHROPIC_FINISH = {
    "end_turn": "complete",
    "stop_sequence": "complete",
    "max_tokens": "length",
    "model_context_window_exceeded": "length",
    "refusal": "refused",
}


def _anthropic_decode(document: Mapping[str, Any]) -> Completion:
    content = document["content"]
    if not isinstance(content, list):
        raise TypeError("content")
    text = "".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )
    usage = document.get("usage") or {}
    return Completion(
        text=text,
        finish=_ANTHROPIC_FINISH.get(_text(document.get("stop_reason")) or "", "other"),
        model=_text(document.get("model")),
        input_tokens=_count(usage.get("input_tokens")),
        output_tokens=_count(usage.get("output_tokens")),
    )


def _openai_body(request: CompletionRequest, target: Endpoint) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": request.model,
        "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": request.user}],
        "max_completion_tokens": request.max_output_tokens,
    }
    if request.temperature is not None:
        body["temperature"] = request.temperature
    return body


def _openai_decode(document: Mapping[str, Any]) -> Completion:
    choice = document["choices"][0]
    message = choice["message"]
    reason = choice.get("finish_reason")
    if message.get("refusal") or reason == "content_filter":
        finish = "refused"
    else:
        finish = {"stop": "complete", "length": "length"}.get(reason, "other")
    usage = document.get("usage") or {}
    return Completion(
        text=_text(message.get("content")) or "",
        finish=finish,
        model=_text(document.get("model")),
        input_tokens=_count(usage.get("prompt_tokens")),
        output_tokens=_count(usage.get("completion_tokens")),
    )


# Ollama truncates input silently when the context is smaller than the request, so the context length is set per
# request to fit the whole budget.
def _ollama_body(request: CompletionRequest, target: Endpoint) -> dict[str, Any]:
    options: dict[str, Any] = {"num_ctx": target.context_length, "num_predict": request.max_output_tokens}
    if request.temperature is not None:
        options["temperature"] = request.temperature
    return {
        "model": request.model,
        "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": request.user}],
        "stream": False,
        "options": options,
    }


def _ollama_decode(document: Mapping[str, Any]) -> Completion:
    message = document["message"]
    return Completion(
        text=_text(message.get("content")) or "",
        finish={"stop": "complete", "length": "length"}.get(_text(document.get("done_reason")) or "", "other"),
        model=_text(document.get("model")),
        input_tokens=_count(document.get("prompt_eval_count")),
        output_tokens=_count(document.get("eval_count")),
    )


ADAPTERS = {
    "anthropic": _Adapter("/v1/messages", _anthropic_headers, _anthropic_body, _anthropic_decode),
    "openai": _Adapter("/chat/completions", _bearer, _openai_body, _openai_decode),
    "openrouter": _Adapter("/chat/completions", _bearer, _openai_body, _openai_decode),
    "ollama": _Adapter("/api/chat", _bearer, _ollama_body, _ollama_decode),
}


# Responses


def _decode(adapter: _Adapter, response: HttpResponse) -> Completion:
    document = _json(response.body)
    if not isinstance(document, dict):
        raise ProviderError("invalid_response", "the response is not a JSON object", status=response.status)
    try:
        return adapter.decode(document)
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError(
            "invalid_response", "the response is not a completion of this provider", status=response.status
        ) from None


def _status_error(response: HttpResponse) -> ProviderError:
    kind = "auth" if response.status in (401, 403) else "http"
    detail = _detail(_json(response.body))
    message = f"HTTP {response.status}" + (f": {detail}" if detail else "")
    return ProviderError(kind, message, status=response.status)


def _detail(document: Any) -> str | None:
    """``error.message`` (Anthropic, OpenAI) or ``error`` (Ollama), shortened."""
    error = document.get("error") if isinstance(document, dict) else None
    message = error.get("message") if isinstance(error, dict) else error
    if not isinstance(message, str) or not message:
        return None
    message = " ".join(message.split())
    return message if len(message) <= DETAIL_LIMIT else f"{message[:DETAIL_LIMIT]}..."


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _retry_after(headers: Mapping[str, str]) -> float | None:
    """Accepts seconds or an HTTP date; capped at ``MAX_WAIT_SECONDS``."""
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            moment = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        seconds = (moment - datetime.now(UTC)).total_seconds()
    return min(max(seconds, 0.0), MAX_WAIT_SECONDS)


def _backoff(attempt: int) -> float:
    return min(2.0**attempt, MAX_WAIT_SECONDS)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
