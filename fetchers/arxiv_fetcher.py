"""arXiv fetcher（PRD §2.2，预印本补充源）。

端点：http://export.arxiv.org/api/query（返回 Atom XML，用 feedparser 解析）
按 topics.en 关键词检索，按 submittedDate 倒序取最新，客户端按时间窗口过滤
（arXiv API 的 search_query 日期语法易错，沿用 rss_fetcher 的"先抓后过滤"策略）。
arXiv 礼仪：请求间隔 ≥ 3s。含 <arxiv:doi> 字段者视为已有正式发表版（同 bioRxiv published 逻辑）。
"""
from __future__ import annotations

import logging
import re
import time as time_module
from datetime import datetime, timezone

import feedparser
import requests

from models import Item

logger = logging.getLogger(__name__)

SOURCE = "arxiv"
API_URL = "http://export.arxiv.org/api/query"
MAX_QUERIES = 5
MAX_RESULTS = 50
REQUEST_INTERVAL = 3.0  # arXiv 建议每 3 秒最多一次请求
ABS_RE = re.compile(r"/abs/(.+)$")
VERSION_RE = re.compile(r"v\d+$")


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    topics = config.get("topics", {})
    queries = topics.get("en", [])[:MAX_QUERIES]

    items: list[Item] = []
    seen_ids: set[str] = set()

    for i, query in enumerate(queries):
        if not query.strip():
            continue
        try:
            for item in _search(query, since, until):
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        except Exception as exc:
            logger.warning("arXiv search failed for query '%s': %s", query[:40], exc)
        if i < len(queries) - 1:
            time_module.sleep(REQUEST_INTERVAL)

    return items


def _search(query: str, since: datetime, until: datetime) -> list[Item]:
    params = {
        "search_query": f'all:"{query}"',
        "start": 0,
        "max_results": MAX_RESULTS,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    now = datetime.now(timezone.utc).isoformat()

    items: list[Item] = []
    for entry in feed.entries:
        pub_dt = _entry_date(entry)
        if pub_dt and (pub_dt < since or pub_dt > until):
            continue
        item = _parse_entry(entry, now)
        if item:
            items.append(item)
    return items


def _entry_date(entry) -> datetime | None:
    val = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if val:
        return datetime.fromtimestamp(time_module.mktime(val), tz=timezone.utc)
    return None


def _parse_entry(entry, now: str) -> Item | None:
    title = (getattr(entry, "title", "") or "").replace("\n", " ").strip()
    if not title:
        return None
    summary = (getattr(entry, "summary", "") or "").replace("\n", " ").strip()

    arxiv_id = ""
    m = ABS_RE.search(getattr(entry, "id", "") or "")
    if m:
        arxiv_id = VERSION_RE.sub("", m.group(1).strip())

    authors = [a.get("name", "") for a in (getattr(entry, "authors", []) or []) if a.get("name")]
    published_doi = getattr(entry, "arxiv_doi", None)

    if published_doi:
        status = "published"
        doi = published_doi
        verified = True
        verify_method = "arxiv_doi_field"
        item_id = f"doi:{doi}"
    else:
        status = "preprint"
        doi = None
        verified = False
        verify_method = None
        item_id = f"arxiv:{arxiv_id}" if arxiv_id else f"arxiv:{abs(hash(title))}"

    return Item(
        id=item_id,
        title=title,
        authors=authors,
        abstract=summary,
        abstract_source="arxiv_api",
        doi=doi,
        arxiv_id=arxiv_id or None,
        url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else getattr(entry, "link", None),
        source_journal="arXiv",
        publication_date=getattr(entry, "published", "") or "",
        status=status,
        doi_verified=verified,
        doi_verify_method=verify_method,
        fetch_sources=[SOURCE],
        fetched_at=now,
        raw={"arxiv_id": arxiv_id, "arxiv_doi": published_doi or ""},
    )
