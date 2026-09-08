"""GitHub App authentication.

Two credentials, deliberately:

- **App JWT** -- RS256, signed locally with the App's private key, <=10 min
  TTL, sent only to ``/app/*`` endpoints (list installations, mint tokens).
- **Installation Access Token** -- minted via the JWT, ~1hr TTL, scoped to
  specific repositories and permissions requested at mint time.

Least privilege: :meth:`GitHubAppAuth.installation_token` always requests
``{"contents": "read"}`` and a single repository by default, regardless of
what the installation itself was granted. A token minted by this process can
read exactly the one repo it needs and nothing else, so a leaked token's
blast radius is one repo's file contents -- not "everything this App can
see."
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx
import jwt

from depfix.gh.models import Installation, InstallationToken, Repository

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_API_URL = "https://api.github.com"

# JWT TTL well under GitHub's 10-minute ceiling, with room for clock skew.
_JWT_TTL_SECONDS = 570
# Backdate `iat` so a local clock that runs a little fast doesn't produce a
# token GitHub considers "not yet valid".
_JWT_CLOCK_BACKDATE_SECONDS = 60


class GitHubAppError(RuntimeError):
    """Raised for any GitHub App auth/API failure, with an actionable message."""


class GitHubAppAuth:
    """Mints and caches installation tokens from a GitHub App's private key."""

    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        api_url: str = DEFAULT_GITHUB_API_URL,
        http_timeout: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._api_url = api_url.rstrip("/")
        self._client = client or httpx.Client(timeout=http_timeout)
        self._owns_client = client is None
        # (installation_id, repo scope) -> token. Scope is part of the key
        # because a token minted for repo A must never be handed out for repo B.
        self._token_cache: dict[tuple[int, tuple[str, ...]], InstallationToken] = {}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GitHubAppAuth:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- App-level JWT ----------------------------------------------------------

    def _app_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - _JWT_CLOCK_BACKDATE_SECONDS,
            "exp": now + _JWT_TTL_SECONDS,
            "iss": self._app_id,
        }
        try:
            return jwt.encode(payload, self._private_key, algorithm="RS256")
        except Exception as exc:
            raise GitHubAppError(
                f"failed to sign App JWT: {exc}. Check that GITHUB_APP_PRIVATE_KEY "
                "is a valid PEM-encoded RSA private key."
            ) from exc

    def _app_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # -- HTTP plumbing ------------------------------------------------------------

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise GitHubAppError(
                "GitHub rejected the App JWT (401 Unauthorized). Most likely cause: "
                "local clock skew -- the JWT's iat/exp must be within a few minutes "
                "of GitHub's clock. Check `date` on this machine, and that "
                "GITHUB_APP_PRIVATE_KEY matches GITHUB_APP_ID."
            )
        if resp.status_code == 404:
            raise GitHubAppError(
                f"GitHub App resource not found: {resp.request.url}. The App may not "
                "be installed on the target account/repository."
            )
        if resp.status_code == 422:
            raise GitHubAppError(
                f"GitHub rejected the request as unprocessable (422): {resp.text[:300]}. "
                "Most likely cause: requesting a permission the installation was not "
                "granted (this integration only needs Contents: Read-only), or a repo "
                "not covered by the installation's repository selection."
            )
        if resp.status_code >= 400:
            raise GitHubAppError(f"GitHub API error {resp.status_code}: {resp.text[:300]}")

    def _paginate(
        self, url: str, headers: dict[str, str], *, list_key: str | None = None
    ) -> list[dict]:
        items: list[dict] = []
        next_url: str | None = url
        while next_url:
            resp = self._client.get(next_url, headers=headers)
            self._raise_for_status(resp)
            data = resp.json()
            page = data.get(list_key, []) if list_key else data
            items.extend(page)
            next_url = _next_link(resp.headers.get("Link"))
        return items

    # -- App-level endpoints --------------------------------------------------

    def list_installations(self) -> list[Installation]:
        raw = self._paginate(f"{self._api_url}/app/installations", self._app_headers())
        return [_installation_from_dict(item) for item in raw]

    def resolve_installation_for_repo(self, owner: str, repo: str) -> Installation:
        resp = self._client.get(
            f"{self._api_url}/repos/{owner}/{repo}/installation", headers=self._app_headers()
        )
        if resp.status_code == 404:
            raise GitHubAppError(
                f"no GitHub App installation found for {owner}/{repo}. Install the "
                "App on this repository (or its owning org) first."
            )
        self._raise_for_status(resp)
        return _installation_from_dict(resp.json())

    # -- Installation tokens --------------------------------------------------

    def installation_token(
        self,
        installation_id: int,
        *,
        repositories: tuple[str, ...] = (),
        permissions: dict[str, str] | None = None,
    ) -> InstallationToken:
        """Mint (or return a cached, unexpired) least-privilege token.

        Defaults to ``{"contents": "read"}`` scoped to ``repositories``,
        regardless of what the installation itself was granted.
        """
        cache_key = (installation_id, repositories)
        cached = self._token_cache.get(cache_key)
        if cached is not None and not cached.is_expired():
            return cached

        payload: dict[str, object] = {"permissions": permissions or {"contents": "read"}}
        if repositories:
            payload["repositories"] = list(repositories)

        resp = self._client.post(
            f"{self._api_url}/app/installations/{installation_id}/access_tokens",
            headers=self._app_headers(),
            json=payload,
        )
        self._raise_for_status(resp)
        data = resp.json()
        token = InstallationToken(
            token=data["token"],
            expires_at=datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00")).astimezone(
                UTC
            ),
            installation_id=installation_id,
            repositories=repositories,
        )
        self._token_cache[cache_key] = token
        return token

    def _installation_headers(
        self, installation_id: int, *, repositories: tuple[str, ...] = ()
    ) -> dict[str, str]:
        token = self.installation_token(installation_id, repositories=repositories)
        return {
            "Authorization": f"token {token.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # -- Repository endpoints (installation-scoped) --------------------------

    def list_repositories(self, installation_id: int) -> list[Repository]:
        headers = self._installation_headers(installation_id)
        raw = self._paginate(
            f"{self._api_url}/installation/repositories", headers, list_key="repositories"
        )
        return [_repository_from_dict(item) for item in raw]

    def get_repository(self, owner: str, repo: str) -> Repository:
        installation = self.resolve_installation_for_repo(owner, repo)
        headers = self._installation_headers(installation.id, repositories=(repo,))
        resp = self._client.get(f"{self._api_url}/repos/{owner}/{repo}", headers=headers)
        self._raise_for_status(resp)
        return _repository_from_dict(resp.json())

    def default_ref(self, owner: str, repo: str) -> str:
        return self.get_repository(owner, repo).default_branch


def _installation_from_dict(item: dict) -> Installation:
    account = item.get("account") or {}
    return Installation(
        id=item["id"],
        account_login=account.get("login", ""),
        account_type=account.get("type", ""),
        repository_selection=item.get("repository_selection", "selected"),
    )


def _repository_from_dict(item: dict) -> Repository:
    return Repository(
        id=item["id"],
        full_name=item["full_name"],
        default_branch=item.get("default_branch", "main"),
        private=bool(item.get("private", False)),
    )


def _next_link(link_header: str | None) -> str | None:
    """Parse the RFC 5988 ``Link`` header GitHub sends for pagination."""
    if not link_header:
        return None
    for part in link_header.split(","):
        pieces = part.split(";")
        if len(pieces) < 2:
            continue
        url = pieces[0].strip().lstrip("<").rstrip(">")
        rel = pieces[1].strip()
        if rel == 'rel="next"':
            return url
    return None
