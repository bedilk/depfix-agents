"""The hosted LLM service: depfix's client side and the Lambda handler."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from proxy.handler import Limits, Service

from depfix.llm_proxy import LLMProxyError, ProxyMessagesClient, bedrock_messages_client

_URL = "https://llm.depfix.example"


@respx.mock
def test_client_sends_token_repo_and_parses_text() -> None:
    route = respx.post(f"{_URL}/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "fixed code"}],
                "usage": {"input_tokens": 12, "output_tokens": 3},
            },
        )
    )
    client = ProxyMessagesClient(url=_URL, token="ghs_abc", repo="acme/app")
    message = client.messages.create(
        model="m",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
        extra_body={"temperature": 0.1},
    )

    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer ghs_abc"
    assert sent.headers["X-Depfix-Repo"] == "acme/app"
    assert json.loads(sent.content)["temperature"] == 0.1
    assert message.content[0].text == "fixed code"
    assert (message.usage.input_tokens, message.usage.output_tokens) == (12, 3)


@respx.mock
def test_client_surfaces_service_refusals() -> None:
    respx.post(f"{_URL}/v1/messages").mock(return_value=httpx.Response(429, text="daily limit"))
    client = ProxyMessagesClient(url=_URL, token="ghs_abc", repo="acme/app")
    with pytest.raises(LLMProxyError, match="429"):
        client.messages.create(model="m", max_tokens=1, messages=[])


def test_client_needs_github_context() -> None:
    client = ProxyMessagesClient(url=_URL, token="", repo="acme/app")
    with pytest.raises(LLMProxyError, match="GITHUB_TOKEN"):
        client.messages.create(model="m", max_tokens=1, messages=[])


def test_factory_uses_the_proxy_only_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DEPFIX_LLM_PROXY_URL", _URL)
    assert isinstance(bedrock_messages_client(), ProxyMessagesClient)
    monkeypatch.delenv("DEPFIX_LLM_PROXY_URL")
    assert not isinstance(bedrock_messages_client(aws_region="us-east-1"), ProxyMessagesClient)


class _FakeBackend:
    def __init__(self, *, readable: bool = True, used: int = 0) -> None:
        self.readable = readable
        self.usage: dict[str, int] = {}
        self.used = used
        self.invocations: list[tuple[str, dict[str, Any]]] = []

    def can_read_repo(self, token: str, repo: str) -> bool:
        return self.readable

    def tokens_used(self, key: str) -> int:
        return self.used + self.usage.get(key, 0)

    def add_tokens(self, key: str, tokens: int) -> None:
        self.usage[key] = self.usage.get(key, 0) + tokens

    def invoke(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        self.invocations.append((model, body))
        return {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 40, "output_tokens": 2},
        }


_LIMITS = Limits(
    models=("sonnet", "haiku"),
    max_output_tokens=1000,
    repo_daily_tokens=100,
    global_daily_tokens=1000,
)


def _event(*, token: str = "ghs_x", repo: str = "acme/app", body: Any = None) -> dict:
    payload = (
        body
        if body is not None
        else {
            "model": "haiku",
            "max_tokens": 50_000,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": "hi"}],
        }
    )
    return {
        "rawPath": "/v1/messages",
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"authorization": f"Bearer {token}", "x-depfix-repo": repo},
        "body": json.dumps(payload),
    }


def test_service_forwards_a_capped_request_and_meters_it() -> None:
    backend = _FakeBackend()
    result = Service(backend=backend, limits=_LIMITS, today="2026-11-27").handle(_event())

    assert result["statusCode"] == 200
    model, body = backend.invocations[0]
    assert model == "haiku"
    assert body["max_tokens"] == 1000
    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert backend.usage == {"repo#acme/app#2026-11-27": 42, "global#2026-11-27": 42}


def test_service_replaces_an_unlisted_model_with_the_default() -> None:
    backend = _FakeBackend()
    event = _event(
        body={"model": "opus", "max_tokens": 10, "messages": [{"role": "user", "content": "x"}]}
    )
    Service(backend=backend, limits=_LIMITS).handle(event)
    assert backend.invocations[0][0] == "sonnet"


@pytest.mark.parametrize(
    ("event", "backend", "status"),
    [
        (_event(token="ghp_personal"), _FakeBackend(), 401),
        (_event(repo="not a repo"), _FakeBackend(), 400),
        (_event(body={"messages": []}), _FakeBackend(), 400),
        (_event(), _FakeBackend(readable=False), 403),
        (_event(), _FakeBackend(used=100), 429),
    ],
)
def test_service_refuses_without_calling_the_model(event, backend, status) -> None:
    result = Service(backend=backend, limits=_LIMITS).handle(event)
    assert result["statusCode"] == status
    assert backend.invocations == []


def test_service_serves_only_the_messages_route() -> None:
    event = _event() | {"rawPath": "/admin"}
    assert Service(backend=_FakeBackend(), limits=_LIMITS).handle(event)["statusCode"] == 404
