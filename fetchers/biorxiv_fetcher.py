"""bioRxiv / medRxiv fetcher（PRD §2.2 Tier 1，预印本）。

端点：https://api.biorxiv.org/details/[server]/[interval]
server = biorxiv 或 medrxiv
按日期范围批量拉取后本地关键词过滤（API 不支持复杂检索）。
返回的 published 字段可判断是否已有正式发表版（PRD §2.4 Step 3）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from models import Item

logger = logging.getLogger(__name__)

SOURCE_BIORXIV = "biorxiv"
SOURCE_MEDRXIV = "medrxiv"
DETAILS_URL = "https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}/json"
PAGE_SIZE = 100


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    """同时处理 biorxiv 与 medrxiv，按 config.sources 开关决定是否各自启用。"""
    sources_cfg = config.get("sources", {})
    items: list[Item] = []

    if sources_cfg.get("biorxiv", True):
        try:
            items.extend(_fetch_server("biorxiv", since, until))
        except Exception as exc:
            logger.warning("⚠️bioRxiv 抓取失败: %s, retrying", exc)
            try:
                items.extend(_fetch_server("biorxiv", since, until))
            except Exception as exc2:
                logger.error("bioRxiv failed after retry: %s", exc2)

    if sources_cfg.get("medrxiv", True):
        try:
            items.extend(_fetch_server("medrxiv", since, until))
        except Exception as exc:
            logger.warning("⚠️medRxiv 抓取失败: %s, retrying", exc)
            try:
                items.extend(_fetch_server("medrxiv", since, until))
            except Exception as exc2:
                logger.error("medRxiv failed after retry: %s", exc2)

    return items


def _fetch_server(server: str, since: datetime, until: datetime) -> list[Item]:
    start = since.strftime("%Y-%m-%d")
    end = until.strftime("%Y-%m-%d")
    source_tag = SOURCE_BIORXIV if server == "biorxiv" else SOURCE_MEDRXIV
    now = datetime.now(timezone.utc).isoformat()
    cursor = 0
    items: list[Item] = []

    while True:
        url = DETAILS_URL.format(server=server, start=start, end=end, cursor=cursor)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        collection = data.get("collection", [])
        if not collection:
            break

        for paper in collection:
            items.append(_parse_paper(paper, source_tag, now))

        messages = data.get("messages", [{}])
        total = int(messages[0].get("total", 0)) if messages else 0
        cursor += len(collection)
        if cursor >= total:
            break

    return items


def _parse_paper(p: dict, source_tag: str, now: str) -> Item:
    doi = p.get("doi", "")
    published = p.get("published", "")

    if published and published != "NA":
        item_id = f"doi:{published}"
        final_doi = published
        status = "published"
        doi_verified = True
        verify_method = "biorxiv_published_field"
    else:
        item_id = f"doi:{doi}" if doi else f"{source_tag}:{p.get('rel_doi', '')}"
        final_doi = doi or None
        status = "preprint"
        doi_verified = False
        verify_method = None

    authors = [a.strip() for a in (p.get("authors", "") or "").split(";") if a.strip()]

    return Item(
        id=item_id,
        title=p.get("title", ""),
        authors=authors,
        abstract=p.get("abstract", ""),
        abstract_source=f"{source_tag}_api",
        doi=final_doi,
        url=f"https://www.{source_tag}.org/content/{doi}" if doi else None,
        source_journal=source_tag.capitalize(),
        publication_date=p.get("date", ""),
        status=status,
        doi_verified=doi_verified,
        doi_verify_method=verify_method,
        fetch_sources=[source_tag],
        fetched_at=now,
        raw={"biorxiv_doi": doi, "published": p.get("published", "")},
    )


def check_published_version(doi: str) -> str | None:
    """查询预印本是否已有正式发表版本，返回正式 DOI 或 None。"""
    try:
        url = f"https://api.biorxiv.org/details/biorxiv/{doi}/na/json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            for item in r.json().get("collection", []):
                published = item.get("published", "")
                if published and published != "NA":
                    return published
    except Exception:
        pass
    return None
