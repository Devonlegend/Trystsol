"""GitHub REST API client and repository-control proof helpers.

Docs read 2026-11-24:
- Rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
  Unauthenticated 60/h; authenticated 5,000/h; secondary limits on 403/429.
- Contents API is used only with the fixed api.github.com host and a strictly
  parsed owner/repo, which avoids fetching arbitrary user URLs (SSRF).
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import time
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

REPO_PATH_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
GITHUB_HOSTS = {"github.com", "www.github.com"}
REPO_CACHE_KEY = "trystsol:github:repo:"
ACTIVITY_CACHE_KEY = "trystsol:github:activity:"
PROOF_PATH = ".trystsol/proof.json"


class GitHubError(Exception):
    pass


class GitHubNotFound(GitHubError):
    pass


def parse_repo_url(value: str) -> tuple[str, str, str]:
    parsed = urlparse((value or "").strip())
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() not in GITHUB_HOSTS:
        raise GitHubError("Repository URL must be https://github.com/<owner>/<repo>.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise GitHubError("Repository URL must contain an owner and a repository.")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not REPO_PATH_RE.match(owner) or not REPO_PATH_RE.match(repo):
        raise GitHubError("Invalid GitHub owner or repository name.")
    canonical = f"https://github.com/{owner}/{repo}"
    return owner, repo, canonical


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


def _get(path: str, params: dict | None = None) -> object:
    url = f"{settings.GITHUB_API_URL.rstrip('/')}{path}"
    for attempt in range(2):
        try:
            response = httpx.get(url, params=params or {}, headers=_headers(), timeout=10.0)
        except httpx.HTTPError as exc:
            logger.warning("github_transport_error", extra={"path": path})
            raise GitHubError("GitHub request failed.") from exc
        if response.status_code in (403, 429) and attempt == 0:
            time.sleep(1.0)
            continue
        if response.status_code == 404:
            raise GitHubNotFound("GitHub resource not found.")
        if response.status_code != 200:
            logger.warning(
                "github_http_error",
                extra={"status": response.status_code, "path": path},
            )
            raise GitHubError(f"GitHub returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubError("GitHub returned invalid JSON.") from exc
    raise GitHubError("GitHub rate limit persisted.")


def fetch_repo(owner: str, repo: str) -> dict:
    key = f"{REPO_CACHE_KEY}{owner}/{repo}"
    cached = cache.get(key)
    if cached:
        return cached
    payload = _get(f"/repos/{owner}/{repo}")
    if not isinstance(payload, dict):
        raise GitHubError("Unexpected GitHub repository response.")
    selected = {
        "full_name": payload.get("full_name"),
        "owner": (payload.get("owner") or {}).get("login"),
        "html_url": payload.get("html_url"),
        "description": payload.get("description"),
        "default_branch": payload.get("default_branch"),
        "stargazers_count": payload.get("stargazers_count"),
        "forks_count": payload.get("forks_count"),
        "open_issues_count": payload.get("open_issues_count"),
        "pushed_at": payload.get("pushed_at"),
        "created_at": payload.get("created_at"),
        "archived": payload.get("archived"),
        "visibility": payload.get("visibility"),
    }
    cache.set(key, selected, settings.GITHUB_CACHE_TTL)
    return selected


def fetch_commits_since(owner: str, repo: str, since_iso: str) -> int:
    payload = _get(
        f"/repos/{owner}/{repo}/commits",
        {"since": since_iso, "per_page": 100},
    )
    if not isinstance(payload, list):
        raise GitHubError("Unexpected GitHub commits response.")
    return len(payload)


def fetch_activity(owner: str, repo: str, since_iso: str) -> dict:
    key = f"{ACTIVITY_CACHE_KEY}{owner}/{repo}:{since_iso[:10]}"
    cached = cache.get(key)
    if cached:
        return cached
    repo_data = fetch_repo(owner, repo)
    commits = fetch_commits_since(owner, repo, since_iso)
    activity = {
        **repo_data,
        "commits_since": commits,
        "commits_since_capped": commits >= 100,
        "commits_since_from": since_iso,
    }
    cache.set(key, activity, settings.GITHUB_CACHE_TTL)
    return activity


def fetch_file(owner: str, repo: str, path: str) -> str:
    payload = _get(f"/repos/{owner}/{repo}/contents/{path}")
    if not isinstance(payload, dict) or payload.get("type") != "file":
        raise GitHubError("Proof path is not a file.")
    encoded = payload.get("content")
    if not encoded:
        raise GitHubError("GitHub did not return file content.")
    try:
        raw = base64.b64decode(encoded, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise GitHubError("GitHub file content is not valid base64.") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitHubError("Proof file is not UTF-8 text.") from exc
