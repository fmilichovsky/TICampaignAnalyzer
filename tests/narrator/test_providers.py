"""The providers of `narrate --send` against a fake transport: wire formats, response mapping, errors and retries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import pytest

from tinarrative.config import NarratorSettings
from tinarrative.narrator.providers import (
    MAX_ATTEMPTS,
    Completion,
    CompletionRequest,
    Endpoint,
    ProviderError,
    complete,
    completion_request,
    endpoint,
)
from tinarrative.narrator.rate_limit import RateLimiter
from tinarrative.narrator.transport import HttpResponse, TransportError

REQUEST = CompletionRequest(system="SYSTEM", user="USER", model="some-model", max_output_tokens=900)


class FakeTransport:
    """Answers each post with the next item: an ``HttpResponse`` or a ``TransportError`` to raise."""

    def __init__(self, *answers: HttpResponse | TransportError) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict[str, str], dict[str, Any], float]] = []

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        self.calls.append((url, dict(headers), json.loads(body), timeout))
        answer = self.answers.pop(0)
        if isinstance(answer, TransportError):
            raise answer
        return answer


def ok(document: Any, status: int = 200, **headers: str) -> HttpResponse:
    return HttpResponse(status, headers, json.dumps(document).encode("utf-8"))


def target(provider: str, *, key: str | None = "KEY", base_url: str | None = None) -> Endpoint:
    urls = {
        "anthropic": "https://api.anthropic.com",
        "openai": "https://api.openai.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
    }
    return Endpoint(provider, base_url or urls.get(provider, "http://localhost:11434"), key, 30.0, 12_000)


def anthropic_response(stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "model": "reported-model",
        "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": "Once "},
            {"type": "text", "text": "upon"},
        ],
        "stop_reason": stop_reason,
        "usage": {"input_tokens": 1200, "output_tokens": 340},
    }


def openai_response(finish_reason: str = "stop", refusal: str | None = None) -> dict[str, Any]:
    message = {"role": "assistant", "content": "Once upon", "refusal": refusal}
    return {
        "model": "reported-model",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 340},
    }


def ollama_response(done_reason: str = "stop") -> dict[str, Any]:
    return {
        "model": "reported-model",
        "message": {"role": "assistant", "content": "Once upon"},
        "done": True,
        "done_reason": done_reason,
        "prompt_eval_count": 1200,
        "eval_count": 340,
    }


def send(transport: FakeTransport, provider: str, request: CompletionRequest = REQUEST, **kwargs: Any) -> Completion:
    waits: list[float] = kwargs.pop("waits", [])
    return complete(request, target(provider, **kwargs), transport, sleep=waits.append)


# Wire formats


def test_anthropic_wire_format_and_mapping() -> None:
    transport = FakeTransport(ok(anthropic_response()))

    completion = send(transport, "anthropic")

    url, headers, body, timeout = transport.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers == {"content-type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": "KEY"}
    assert body == {
        "model": "some-model",
        "max_tokens": 900,
        "system": "SYSTEM",
        "messages": [{"role": "user", "content": "USER"}],
    }
    assert timeout == 30.0
    assert completion == Completion("Once upon", "complete", "reported-model", 1200, 340)


def test_openai_wire_format_and_mapping() -> None:
    transport = FakeTransport(ok(openai_response()))

    completion = send(transport, "openai", replace(REQUEST, temperature=0.5))

    url, headers, body, _ = transport.calls[0]
    assert url == "https://api.openai.com/v1/chat/completions"
    assert headers == {"content-type": "application/json", "authorization": "Bearer KEY"}
    assert body == {
        "model": "some-model",
        "messages": [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}],
        "max_completion_tokens": 900,
        "temperature": 0.5,
    }
    assert completion == Completion("Once upon", "complete", "reported-model", 1200, 340)


def test_openai_compatible_server_without_key() -> None:
    transport = FakeTransport(ok(openai_response()))

    send(transport, "openai", key=None, base_url="http://127.0.0.1:1234/v1")

    url, headers, _, _ = transport.calls[0]
    assert url == "http://127.0.0.1:1234/v1/chat/completions"
    assert "authorization" not in headers


def test_openrouter_wire_format_and_mapping() -> None:
    transport = FakeTransport(ok(openai_response()))

    completion = send(transport, "openrouter", replace(REQUEST, temperature=0.5))

    url, headers, body, _ = transport.calls[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert headers == {"content-type": "application/json", "authorization": "Bearer KEY"}
    assert body == {
        "model": "some-model",
        "messages": [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}],
        "max_completion_tokens": 900,
        "temperature": 0.5,
    }
    assert completion == Completion("Once upon", "complete", "reported-model", 1200, 340)


def test_ollama_sets_the_context_length_from_budget_and_output() -> None:
    transport = FakeTransport(ok(ollama_response()))

    completion = send(transport, "ollama", key=None)

    url, headers, body, _ = transport.calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert headers == {"content-type": "application/json"}
    assert body == {
        "model": "some-model",
        "messages": [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}],
        "stream": False,
        "options": {"num_ctx": 12_000, "num_predict": 900},
    }
    assert completion == Completion("Once upon", "complete", "reported-model", 1200, 340)


def test_temperature_is_sent_only_when_set() -> None:
    transport = FakeTransport(ok(anthropic_response()), ok(ollama_response()))

    send(transport, "anthropic", replace(REQUEST, temperature=0.0))
    send(transport, "ollama", replace(REQUEST, temperature=0.2))

    assert transport.calls[0][2]["temperature"] == 0.0
    assert transport.calls[1][2]["options"]["temperature"] == 0.2


# Finish reasons


@pytest.mark.parametrize(
    ("stop_reason", "finish"),
    [
        ("end_turn", "complete"),
        ("stop_sequence", "complete"),
        ("max_tokens", "length"),
        ("model_context_window_exceeded", "length"),
        ("refusal", "refused"),
        ("pause_turn", "other"),
    ],
)
def test_anthropic_finish_reasons(stop_reason: str, finish: str) -> None:
    assert send(FakeTransport(ok(anthropic_response(stop_reason))), "anthropic").finish == finish


@pytest.mark.parametrize(
    ("finish_reason", "refusal", "finish"),
    [
        ("stop", None, "complete"),
        ("length", None, "length"),
        ("content_filter", None, "refused"),
        ("stop", "I can't help with that.", "refused"),
        ("tool_calls", None, "other"),
    ],
)
def test_openai_finish_reasons(finish_reason: str, refusal: str | None, finish: str) -> None:
    assert send(FakeTransport(ok(openai_response(finish_reason, refusal))), "openai").finish == finish


@pytest.mark.parametrize(("done_reason", "finish"), [("stop", "complete"), ("length", "length"), ("unload", "other")])
def test_ollama_finish_reasons(done_reason: str, finish: str) -> None:
    assert send(FakeTransport(ok(ollama_response(done_reason))), "ollama", key=None).finish == finish


def test_missing_usage_gives_no_counts() -> None:
    document = {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]}

    completion = send(FakeTransport(ok(document)), "openai")

    assert completion == Completion("", "complete", None, None, None)


# Errors and retries


@pytest.mark.parametrize("status", [401, 403])
def test_an_auth_failure_is_not_retried(status: int) -> None:
    transport = FakeTransport(
        ok({"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}, status)
    )

    with pytest.raises(ProviderError) as raised:
        send(transport, "anthropic")

    assert (raised.value.kind, raised.value.status, str(raised.value)) == ("auth", status, f"HTTP {status}: bad key")
    assert len(transport.calls) == 1


def test_a_client_error_carries_the_shortened_provider_message() -> None:
    transport = FakeTransport(
        ok({"error": {"message": "model not found " + "x" * 300}}, 400), ok({"error": "gone"}, 404)
    )

    with pytest.raises(ProviderError) as raised:
        send(transport, "openai")
    with pytest.raises(ProviderError) as ollama:
        send(transport, "ollama")

    assert raised.value.kind == "http"
    assert str(raised.value).startswith("HTTP 400: model not found xxx") and str(raised.value).endswith("...")
    assert len(str(raised.value)) < 250
    assert str(ollama.value) == "HTTP 404: gone"


@pytest.mark.parametrize(
    ("provider", "body"),
    [
        ("anthropic", b"not json"),
        ("anthropic", b"[]"),
        ("anthropic", json.dumps({"content": "text"}).encode()),
        ("openai", json.dumps({"choices": []}).encode()),
        ("ollama", json.dumps({"message": "text"}).encode()),
    ],
)
def test_a_success_without_a_completion_is_an_invalid_response(provider: str, body: bytes) -> None:
    with pytest.raises(ProviderError) as raised:
        send(FakeTransport(HttpResponse(200, {}, body)), provider)

    assert raised.value.kind == "invalid_response"


def test_a_rate_limit_waits_as_retry_after_asks() -> None:
    transport = FakeTransport(ok({}, 429, **{"retry-after": "7"}), ok(anthropic_response()))
    waits: list[float] = []
    limiter_waits: list[float] = []
    clock = [0.0]

    def rate_sleep(seconds: float) -> None:
        limiter_waits.append(seconds)
        clock[0] += seconds

    limiter = RateLimiter(1, None, clock=lambda: clock[0], sleep=rate_sleep)

    completion = complete(
        REQUEST,
        target("anthropic"),
        transport,
        sleep=waits.append,
        before_attempt=lambda: limiter.acquire(1),
    )

    assert completion.finish == "complete"
    assert waits == [7.0]
    assert len(transport.calls) == 2
    assert limiter_waits == [60.0]


def test_retry_after_as_a_date_and_capped() -> None:
    later = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    transport = FakeTransport(
        ok({}, 429, **{"retry-after": later}), ok({}, 529, **{"retry-after": "3600"}), ok(anthropic_response())
    )
    waits: list[float] = []

    send(transport, "anthropic", waits=waits)

    assert 20 < waits[0] <= 30
    assert waits[1] == 60.0


def test_server_errors_back_off_and_give_up_after_the_limit() -> None:
    transport = FakeTransport(*[ok({"error": {"message": "overloaded"}}, 503)] * MAX_ATTEMPTS)
    waits: list[float] = []

    with pytest.raises(ProviderError) as raised:
        send(transport, "openai", waits=waits)

    assert (raised.value.kind, raised.value.status) == ("http", 503)
    assert waits == [2.0, 4.0, 8.0]
    assert len(transport.calls) == MAX_ATTEMPTS


def test_a_connection_failure_is_retried_and_a_timeout_is_not() -> None:
    refused = TransportError("Connection refused", timeout=False)
    transport = FakeTransport(refused, ok(ollama_response()), TransportError("timed out", timeout=True))
    waits: list[float] = []

    assert send(transport, "ollama", key=None, waits=waits).finish == "complete"
    with pytest.raises(ProviderError) as raised:
        send(transport, "ollama", key=None, waits=waits)

    assert waits == [2.0]
    assert (raised.value.kind, str(raised.value)) == ("network", "no response: timed out")


# Endpoint


def settings(**changes: Any) -> NarratorSettings:
    return replace(NarratorSettings(), **changes)


def test_endpoint_resolves_defaults_and_the_key() -> None:
    resolved = endpoint(
        settings(provider="anthropic", model="m", api_key_env="MY_KEY", max_input_tokens=10_000), {"MY_KEY": "secret"}
    )

    assert resolved == Endpoint("anthropic", "https://api.anthropic.com", "secret", 600.0, 26_000)
    assert endpoint(settings(provider="ollama", model="m", base_url="http://box:11434/"), {}).base_url == (
        "http://box:11434"
    )
    assert endpoint(settings(provider="openai", model="m", base_url="http://127.0.0.1:1234/v1"), {}).key is None
    assert endpoint(settings(provider="openrouter", model="m", api_key_env="MY_KEY"), {"MY_KEY": "secret"}) == Endpoint(
        "openrouter", "https://openrouter.ai/api/v1", "secret", 600.0, 216_000
    )


@pytest.mark.parametrize(
    ("changes", "environ", "message"),
    [
        ({"model": "m"}, {}, "no provider"),
        ({"provider": "ollama"}, {}, "no model"),
        ({"provider": "anthropic", "model": "m"}, {}, "anthropic needs an API key"),
        ({"provider": "openai", "model": "m"}, {}, "openai needs an API key"),
        ({"provider": "openrouter", "model": "m"}, {}, "openrouter needs an API key"),
        ({"provider": "openai", "model": "m", "api_key_env": "MY_KEY"}, {"MY_KEY": ""}, "MY_KEY"),
        ({"provider": "ollama", "model": "m", "base_url": "file:///etc"}, {}, "http:// or https://"),
        (
            {"provider": "ollama", "model": "m", "max_input_tokens": 30_000, "context_window": 32_768},
            {},
            "max_input_tokens 30000 plus max_output_tokens 16000 is 46000, over context_window 32768",
        ),
    ],
)
def test_endpoint_rejects_settings_that_cannot_send(
    changes: dict[str, Any], environ: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        endpoint(settings(**changes), environ)


def test_completion_request_joins_the_chapter_request_with_the_settings() -> None:
    request = {"system": "SYSTEM", "messages": [{"role": "user", "content": "USER"}]}

    neutral = completion_request(request, settings(model="m", max_output_tokens=500, temperature=0.3))

    assert neutral == CompletionRequest("SYSTEM", "USER", "m", 500, 0.3)
