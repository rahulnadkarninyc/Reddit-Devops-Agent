from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from reddit_kb.models import CommentSnippet
from reddit_kb.reddit_thread import extract_top_comments_from_thread_json

log = logging.getLogger(__name__)

# Public listing JSON (no OAuth). Same shape as oauth.reddit.com listings.
# Reddit may rate-limit or block generic user-agents — use a descriptive REDDIT_USER_AGENT.
PUBLIC_ORIGIN = "https://www.reddit.com"
# Thread JSON sometimes 403 on www for unauthenticated clients; old. is a fallback only.
OLD_PUBLIC_ORIGIN = "https://old.reddit.com"


class RedditPublicJsonClient:
    """Fetch subreddit listings via www.reddit.com/.../*.json (no API app required)."""

    def __init__(
        self,
        user_agent: str,
        timeout: float = 30.0,
        page_delay_sec: float = 1.5,
    ) -> None:
        if not user_agent or user_agent.strip().lower() in ("python-httpx", "reddit-kb/0.1.0"):
            log.warning(
                "Set REDDIT_USER_AGENT to something descriptive, e.g. "
                "'reddit-kb/0.1 by u/YourRedditUser (contact@you.com)' — "
                "otherwise Reddit often returns 403.",
            )
        self._user_agent = user_agent
        self._timeout = timeout
        self._page_delay_sec = page_delay_sec
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> RedditPublicJsonClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(5):
            any_success_candidate = False
            for origin in (PUBLIC_ORIGIN, OLD_PUBLIC_ORIGIN):
                url = f"{origin}{path}" if path.startswith("/") else f"{origin}/{path}"
                r = self._http.get(
                    url,
                    params=params or {},
                    headers={
                        "User-Agent": self._user_agent,
                        "Accept": "application/json",
                    },
                )
                if r.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    log.warning("Reddit 429 on public JSON, sleeping %ss", wait)
                    time.sleep(wait)
                    any_success_candidate = True
                    break
                if r.status_code == 403:
                    log.warning(
                        "403 from %s for %s; trying fallback / check User-Agent",
                        origin,
                        path,
                    )
                    time.sleep(0.75)
                    continue
                r.raise_for_status()
                out = r.json()
                if not isinstance(out, dict):
                    raise TypeError("Expected JSON object from Reddit")
                return out
            if not any_success_candidate:
                log.error(
                    "Reddit listing 403 on www and old for %s. "
                    "Improve REDDIT_USER_AGENT, increase subreddit_delay_sec, or use OAuth.",
                    path,
                )
            time.sleep(1 + attempt)
        raise RuntimeError("Reddit public GET failed after retries")

    def _get_json_any(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{PUBLIC_ORIGIN}{path}" if path.startswith("/") else f"{PUBLIC_ORIGIN}/{path}"
        for attempt in range(5):
            r = self._http.get(
                url,
                params=params or {},
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/json",
                },
            )
            if r.status_code == 429:
                wait = 2 ** (attempt + 1)
                log.warning("Reddit 429 on public JSON, sleeping %ss", wait)
                time.sleep(wait)
                continue
            if r.status_code == 403:
                log.error(
                    "Reddit returned 403. Use a unique, descriptive User-Agent and slow down; "
                    "see https://github.com/reddit-archive/reddit/wiki/API",
                )
            r.raise_for_status()
            return r.json()
        raise RuntimeError("Reddit public GET failed after retries")

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
        path = f"/r/{sub}/comments/{pid}.json"
        root: Any = None
        last_status: int | None = None
        for origin in (PUBLIC_ORIGIN, OLD_PUBLIC_ORIGIN):
            url = f"{origin}{path}"
            r = self._http.get(
                url,
                params=params,
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/json",
                },
            )
            if r.status_code == 403:
                last_status = 403
                log.warning("Thread JSON 403 from %s; trying fallback host", origin)
                time.sleep(0.5)
                continue
            if r.status_code == 429:
                time.sleep(3)
                r = self._http.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": self._user_agent,
                        "Accept": "application/json",
                    },
                )
            r.raise_for_status()
            root = r.json()
            break
        if root is None:
            raise RuntimeError(
                f"Thread JSON blocked (HTTP {last_status}) for r/{sub}/comments/{pid} on "
                "www.reddit.com and old.reddit.com. Use Reddit OAuth or check REDDIT_USER_AGENT."
            )
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
            data = self._get_json(f"/r/{sub}/top.json", params=params)
            listing = data.get("data") or {}
            children = listing.get("children") or []
            if not children:
                break
            collected.extend(children)
            after = listing.get("after")
            if not after:
                break
            time.sleep(self._page_delay_sec)
        return collected[:limit_total]
