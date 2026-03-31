from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from reddit_kb.models import CommentSnippet
from reddit_kb.reddit_thread import extract_top_comments_from_thread_json

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE = "https://oauth.reddit.com"


class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        timeout: float = 30.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._timeout = timeout
        self._access_token: str | None = None
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> RedditClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _ensure_token(self) -> str:
        if self._access_token:
            return self._access_token
        r = self._http.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
            headers={"User-Agent": self._user_agent},
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token in Reddit response: {data}")
        self._access_token = str(token)
        return self._access_token

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._ensure_token()
        url = f"{OAUTH_BASE}{path}" if path.startswith("/") else f"{OAUTH_BASE}/{path}"
        for attempt in range(5):
            r = self._http.get(
                url,
                params=params or {},
                headers={
                    "User-Agent": self._user_agent,
                    "Authorization": f"bearer {token}",
                },
            )
            if r.status_code == 429:
                wait = 2**attempt
                log.warning("Reddit 429, sleeping %ss", wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            out = r.json()
            if not isinstance(out, dict):
                raise TypeError("Expected JSON object from Reddit")
            return out
        raise RuntimeError("Reddit GET failed after retries")

    def _get_any(self, path: str, params: dict[str, Any] | None = None) -> Any:
        token = self._ensure_token()
        url = f"{OAUTH_BASE}{path}" if path.startswith("/") else f"{OAUTH_BASE}/{path}"
        for attempt in range(5):
            r = self._http.get(
                url,
                params=params or {},
                headers={
                    "User-Agent": self._user_agent,
                    "Authorization": f"bearer {token}",
                },
            )
            if r.status_code == 429:
                wait = 2**attempt
                log.warning("Reddit 429, sleeping %ss", wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("Reddit GET failed after retries")

    def fetch_post_thread_top_comments(
        self,
        subreddit: str,
        post_id: str,
        *,
        sort: str = "top",
        thread_limit: int = 200,
        top_comments_per_post: int = 20,
        max_comment_chars: int = 500,
        max_comment_depth: int = 6,
    ) -> list[CommentSnippet]:
        sub = subreddit.removeprefix("r/").strip()
        pid = post_id.removeprefix("t3_").strip()
        params: dict[str, Any] = {"sort": sort, "limit": thread_limit, "raw_json": 1}
        root = self._get_any(f"/r/{sub}/comments/{pid}", params=params)
        return extract_top_comments_from_thread_json(
            root,
            top_n=top_comments_per_post,
            max_comment_chars=max_comment_chars,
            max_comment_depth=max_comment_depth,
        )

    def iter_subreddit_top(
        self,
        subreddit: str,
        time_filter: str,
        limit_total: int,
        page_limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return raw listing children (each t3 post wrapper)."""
        sub = subreddit.removeprefix("r/").strip()
        collected: list[dict[str, Any]] = []
        after: str | None = None
        while len(collected) < limit_total:
            batch = min(page_limit, limit_total - len(collected))
            params: dict[str, Any] = {"t": time_filter, "limit": batch, "raw_json": 1}
            if after:
                params["after"] = after
            data = self._get(f"/r/{sub}/top", params=params)
            listing = data.get("data") or {}
            children = listing.get("children") or []
            if not children:
                break
            collected.extend(children)
            after = listing.get("after")
            if not after:
                break
            time.sleep(0.5)
        return collected[:limit_total]
