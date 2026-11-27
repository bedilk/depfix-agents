"""Client for Claude-on-Bedrock calls: direct with the caller's AWS credentials,
or through depfix's hosted LLM service when ``DEPFIX_LLM_PROXY_URL`` is set.

The hosted service holds the Bedrock access, so a repository running the
depfix GitHub Action needs no key of its own: it authenticates with its
workflow's ``GITHUB_TOKEN`` and names its repository.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import httpx

PROXY_URL_ENV = "DEPFIX_LLM_PROXY_URL"


class LLMProxyError(RuntimeError):
    """The hosted LLM service refused or failed a request."""


class ProxyMessagesClient:
    """The slice of the Anthropic client surface depfix uses (``messages.create``),
    sent to the hosted service instead of to Bedrock."""

    def __init__(self, *, url: str, token: str, repo: str, timeout: float = 300.0) -> None:
        self._url = url.rstrip("/") + "/v1/messages"
        self._token = token
        self._repo = repo
        self._timeout = timeout

    @property
    def messages(self) -> ProxyMessagesClient:
        return self

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
        **_: Any,
    ) -> SimpleNamespace:
        if not self._token or not self._repo:
            raise LLMProxyError(
                "the depfix LLM service needs GITHUB_TOKEN and GITHUB_REPOSITORY; "
                "both are set automatically inside GitHub Actions"
            )
        payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
        payload.update(extra_body or {})
        try:
            resp = httpx.post(
                self._url,
                json=payload,
                headers={"Authorization": f"Bearer {self._token}", "X-Depfix-Repo": self._repo},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMProxyError(f"depfix LLM service unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise LLMProxyError(
                f"depfix LLM service returned {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        usage = data.get("usage") or {}
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text=str(block.get("text", "")))
                for block in data.get("content") or []
                if block.get("type") == "text"
            ],
            usage=SimpleNamespace(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
        )


def proxy_url() -> str:
    return os.environ.get(PROXY_URL_ENV, "").strip()


def bedrock_messages_client(
    *,
    aws_access_key: str = "",
    aws_secret_key: str = "",
    aws_region: str = "us-east-1",
    aws_profile: str = "",
) -> Any:
    """An object with ``.messages.create(...)`` for Claude on Bedrock."""
    url = proxy_url()
    if url:
        return ProxyMessagesClient(
            url=url,
            token=os.environ.get("GITHUB_TOKEN", ""),
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
        )
    from anthropic import AnthropicBedrock

    kwargs: dict[str, Any] = {"aws_region": aws_region}
    if aws_access_key and aws_secret_key:
        kwargs["aws_access_key"] = aws_access_key
        kwargs["aws_secret_key"] = aws_secret_key
    elif aws_profile:
        kwargs["aws_profile"] = aws_profile
    return AnthropicBedrock(**kwargs)
