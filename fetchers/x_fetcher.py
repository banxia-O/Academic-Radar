"""X 平台 fetcher（PRD §2.2 Tier 2，社交信号层）。

价值定位：发现学术评论/争议/会议实时讨论，而非发现文献本身。
需要 X API v2 Bearer Token（config.api_keys.x_bearer_token）。
未配置 token 时静默跳过，不报错。

抓到的推文若引用了 Tier 1 已收录的论文，在 dedup 阶段合并为同一条目
（追加 x_links / fetch_sources），不重复出条。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from models import Item

logger = logging.getLogger(__name__)

SOURCE = "x"
SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
MAX_QUERIES = 3


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    bearer_token = config.get("api_keys", {}).get("x_bearer_token", "")
    if not bearer_token:
        logger.info("X bearer token not configured, skipping X source")
        return []

    topics = config.get("topics", {})
    queries = topics.get("en", [])[:MAX_QUERIES]
    items: list[Item] = []
    seen_ids: set[str] = set()

    for q in queries:
        try:
            batch = _search_tweets(q, since, until, bearer_token)
            for item in batch:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        except Exception as exc:
            logger.warning("⚠️X 抓取失败 for query '%s': %s", q[:40], exc)

    return items


def _search_tweets(query: str, since: datetime, until: datetime, bearer_token: str) -> list[Item]:
    params = {
        "query": f"{query} (doi OR arxiv OR pubmed) lang:en -is:retweet",
        "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_results": 100,
        "tweet.fields": "created_at,author_id,entities",
        "expansions": "author_id",
        "user.fields": "username",
    }
    headers = {"Authorization": f"Bearer {bearer_token}"}
    r = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()

    data = r.json()
    users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
    now = datetime.now(timezone.utc).isoformat()

    return [
        item
        for tweet in data.get("data", [])
        if (item := _parse_tweet(tweet, users, now)) is not None
    ]


def _parse_tweet(tweet: dict, users: dict, now: str) -> Item | None:
    text = tweet.get("text", "")
    tweet_id = tweet.get("id", "")
    handle = users.get(tweet.get("author_id", ""), "unknown")
    tweet_url = f"https://x.com/{handle}/status/{tweet_id}"

    doi: str | None = None
    for url_obj in (tweet.get("entities") or {}).get("urls", []):
        expanded = url_obj.get("expanded_url", "")
        if "doi.org/" in expanded:
            doi = expanded.split("doi.org/")[-1].strip("/")
            break

    return Item(
        id=f"x:{tweet_id}",
        title=text[:200],
        authors=[f"@{handle}"],
        abstract=text,
        abstract_source="x_tweet",
        doi=doi,
        status="unverified",
        doi_verified=False,
        url=tweet_url,
        x_links=[tweet_url],
        fetch_sources=[SOURCE],
        fetched_at=now,
        raw={"tweet_id": tweet_id},
    )
