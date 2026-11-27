"""depfix hosted LLM service: an AWS Lambda behind a function URL.

The depfix GitHub Action sends Claude requests here instead of to Bedrock, so
repositories using it need no key. A caller proves it is a GitHub Actions run
for a repository by sending that run's ``GITHUB_TOKEN`` and the repository name;
the token must be able to read that repository. Spend is capped per repository
and in total, per UTC day.

Only the standard library and boto3 (built into the Lambda runtime) are used.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# Installation tokens: GitHub Actions' GITHUB_TOKEN and GitHub App tokens.
# Personal access tokens (ghp_, github_pat_) are refused.
_TOKEN_PREFIX = "ghs_"
_VERIFY_TTL_SECONDS = 600
_MAX_PROMPT_CHARS = 600_000


@dataclass(frozen=True)
class Limits:
    models: tuple[str, ...]
    max_output_tokens: int
    repo_daily_tokens: int
    global_daily_tokens: int

    @classmethod
    def from_env(cls) -> Limits:
        models = tuple(
            m.strip()
            for m in os.environ.get(
                "ALLOWED_MODELS",
                "us.anthropic.claude-sonnet-4-6,us.anthropic.claude-haiku-4-5-20251001-v1:0",
            ).split(",")
            if m.strip()
        )
        return cls(
            models=models,
            max_output_tokens=int(os.environ.get("MAX_OUTPUT_TOKENS", "16384")),
            repo_daily_tokens=int(os.environ.get("REPO_DAILY_TOKENS", "1000000")),
            global_daily_tokens=int(os.environ.get("GLOBAL_DAILY_TOKENS", "5000000")),
        )


class Backend(Protocol):
    def can_read_repo(self, token: str, repo: str) -> bool: ...
    def tokens_used(self, key: str) -> int: ...
    def add_tokens(self, key: str, tokens: int) -> None: ...
    def invoke(self, model: str, body: dict[str, Any]) -> dict[str, Any]: ...


class AwsBackend:
    def __init__(self) -> None:
        import boto3

        self._table = boto3.resource("dynamodb").Table(
            os.environ.get("USAGE_TABLE", "depfix-proxy-usage")
        )
        self._bedrock = boto3.client(
            "bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-east-1")
        )
        self._verified: dict[str, float] = {}

    def can_read_repo(self, token: str, repo: str) -> bool:
        cache_key = hashlib.sha256(f"{token}\0{repo}".encode()).hexdigest()
        if self._verified.get(cache_key, 0.0) > time.time():
            return True
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "depfix-llm-proxy",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 - fixed https host
                ok = resp.status == 200
        except urllib.error.URLError:
            ok = False
        if ok:
            self._verified[cache_key] = time.time() + _VERIFY_TTL_SECONDS
        return ok

    def tokens_used(self, key: str) -> int:
        item = self._table.get_item(Key={"pk": key}).get("Item") or {}
        return int(item.get("tokens", 0))

    def add_tokens(self, key: str, tokens: int) -> None:
        self._table.update_item(
            Key={"pk": key},
            UpdateExpression="ADD tokens :n SET expires_at = :e",
            ExpressionAttributeValues={":n": tokens, ":e": int(time.time()) + 3 * 86400},
        )

    def invoke(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = self._bedrock.invoke_model(
            modelId=model,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(resp["body"].read())


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _error(status: int, message: str) -> dict[str, Any]:
    return _response(status, {"type": "error", "error": {"message": message}})


def _prompt_chars(messages: list[Any]) -> int:
    total = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            total += sum(len(str(block.get("text", ""))) for block in content)
    return total


@dataclass
class Service:
    backend: Backend
    limits: Limits
    today: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d"))

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        if method != "POST" or event.get("rawPath") != "/v1/messages":
            return _error(404, "only POST /v1/messages is served")

        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        token = headers.get("authorization", "").removeprefix("Bearer ").strip()
        repo = headers.get("x-depfix-repo", "").strip()
        if not token.startswith(_TOKEN_PREFIX):
            return _error(401, "send the workflow's GITHUB_TOKEN as a Bearer token")
        if not _REPO_RE.match(repo):
            return _error(400, "send the repository as X-Depfix-Repo: OWNER/NAME")

        raw = event.get("body") or ""
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            return _error(400, "body must be JSON")
        messages = request.get("messages")
        if not isinstance(messages, list) or not messages:
            return _error(400, "messages must be a non-empty list")
        if any(m.get("role") not in ("user", "assistant") for m in messages):
            return _error(400, "message roles must be user or assistant")
        if _prompt_chars(messages) > _MAX_PROMPT_CHARS:
            return _error(413, "prompt too large")

        if not self.backend.can_read_repo(token, repo):
            return _error(403, f"token cannot read {repo}")

        repo_key, global_key = f"repo#{repo.lower()}#{self.today}", f"global#{self.today}"
        if self.backend.tokens_used(repo_key) >= self.limits.repo_daily_tokens:
            return _error(429, "daily limit reached for this repository; retry tomorrow")
        if self.backend.tokens_used(global_key) >= self.limits.global_daily_tokens:
            return _error(429, "the depfix service's daily limit is reached; retry tomorrow")

        model = request.get("model")
        if model not in self.limits.models:
            model = self.limits.models[0]
        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max(
                1, min(int(request.get("max_tokens", 4096)), self.limits.max_output_tokens)
            ),
            "messages": messages,
        }
        if isinstance(request.get("system"), str):
            body["system"] = request["system"]
        if isinstance(request.get("temperature"), (int, float)):
            body["temperature"] = min(max(float(request["temperature"]), 0.0), 1.0)

        try:
            result = self.backend.invoke(model, body)
        except Exception as exc:
            logger.exception("bedrock call failed for %s", repo)
            return _error(502, f"model call failed: {type(exc).__name__}")

        usage = result.get("usage") or {}
        spent = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        self.backend.add_tokens(repo_key, spent)
        self.backend.add_tokens(global_key, spent)
        logger.info(json.dumps({"repo": repo, "model": model, "tokens": spent}))
        return _response(200, result)


_backend: AwsBackend | None = None


def lambda_handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    global _backend
    if _backend is None:
        _backend = AwsBackend()
    return Service(backend=_backend, limits=Limits.from_env()).handle(event)
