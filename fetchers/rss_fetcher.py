"""RSS fetcher（PRD §2.2 Tier 3，辅助源）。

通过 RSSHub 或期刊原生 RSS 订阅目标信息源。
公众号/博客等二手信息源拉取的条目必须追溯到原始学术来源（DOI 或论文链接），
否则在 doi_validator 阶段标为 unverified。
单个 feed 失败不影响其他 feed。
"""
from __future__ import annotations

import logging
import re
import time as time_module
from datetime import datetime, timezone

import feedparser

from models import Item

logger = logging.getLogger(__name__)

SOURCE = "rss"
DOI_PATTERN = re.compile(r"\b10\.\d{4,}/\S+")


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    """遍历 config.rss_feeds，单个 feed 失败不影响其他 feed。"""
    feeds = config.get("rss_feeds", []) or []
    if not feeds:
        return []

    items: list[Item] = []
    now = datetime.now(timezone.utc).isoformat()

    for feed_cfg in feeds:
        name = feed_cfg.get("name", "RSS")
        url = feed_cfg.get("url", "")
        if not url:
            continue
        try:
            items.extend(_fetch_feed(url, name, since, until, now))
        except Exception as exc:
            logger.warning("RSS feed '%s' failed: %s", name, exc)

    return items


def _fetch_feed(url: str, name: str, since: datetime, until: datetime, now: str) -> list[Item]:
    feed = feedparser.parse(url)
    items: list[Item] = []

    for entry in feed.entries:
        pub_dt = _parse_entry_date(entry)
        if pub_dt and (pub_dt < since or pub_dt > until):
            continue
        item = _parse_entry(entry, name, now)
        if item:
            items.append(item)

    return items


def _parse_entry_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            return datetime.fromtimestamp(time_module.mktime(val), tz=timezone.utc)
    return None


def _parse_entry(entry, feed_name: str, now: str) -> Item | None:
    title = getattr(entry, "title", "") or ""
    summary = getattr(entry, "summary", "") or ""
    link = getattr(entry, "link", "") or ""

    if not title:
        return None

    doi: str | None = None
    for text in [link, summary, title]:
        m = DOI_PATTERN.search(text)
        if m:
            doi = m.group().rstrip(".,)")
            break

    pub_date = ""
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            pub_date = val
            break

    item_id = f"doi:{doi}" if doi else f"rss:{abs(hash(title + link))}"

    return Item(
        id=item_id,
        title=title,
        authors=[],
        abstract=summary,
        abstract_source="rss_feed",
        doi=doi,
        url=link,
        source_journal=feed_name,
        publication_date=pub_date,
        status="unverified",
        doi_verified=False,
        fetch_sources=[SOURCE],
        fetched_at=now,
        raw={"feed_name": feed_name, "link": link},
    )
