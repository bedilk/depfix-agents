"""Shared HTTP client construction.

One place to set the User-Agent and attach a GitHub token. Unauthenticated
GitHub is 60 req/hr, which one provider with two GitHub feeds exhausts in a
day of cron ticks; authenticated is 5000.
"""

from __future__ import annotations

import httpx

from depfix.config import get_settings

USER_AGENT = "depfix/0.3 (+https://github.com/your-org/depfix)"


def build_http_client(timeout: float | None = None) -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        timeout=timeout if timeout is not None else settings.http_timeout,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
        follow_redirects=True,
    )


def github_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers
