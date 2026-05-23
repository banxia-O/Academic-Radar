"""OpenAlex fetcher（PRD §2.2 Tier 1，广覆盖元数据补充）。

端点：https://api.openalex.org/works
价值：4.7 亿+ 作品，含非英文文献/数据集/预印本；补 PubMed 未收录内容
限制：10 万请求 / 天。加 mailto 参数进入 polite pool。
用途：concept/topic 过滤 + 作者/机构追踪。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from models import Item

logger = logging.getLogger(__name__)

SOURCE = "openalex"
WORKS_URL = "https://api.openalex.org/works"
MAX_QUERIES = 5
MAX_AUTHORS = 10


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    topics = config.get("topics", {})
    queries = topics.get("en", [])[:MAX_QUERIES]
    authors_track = config.get("authors", [])[:MAX_AUTHORS]
    mailto = config.get("api_keys", {}).get("openalex_mailto", "")

    items: list[Item] = []
    seen_ids: set[str] = set()

    for query in queries:
        try:
            for item in _fetch_works(query, since, until, mailto):
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        except Exception as exc:
            logger.warning("OpenAlex query failed for '%s': %s", query[:40], exc)

    for author_name in authors_track:
        try:
            for item in _fetch_by_author(author_name, since, until, mailto):
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        except Exception as exc:
            logger.warning("OpenAlex author search failed for '%s': %s", author_name, exc)

    return items


def _fetch_works(query: str, since: datetime, until: datetime, mailto: str) -> list[Item]:
    params: dict = {
        "search": query,
        "filter": (
            f"from_publication_date:{since.strftime('%Y-%m-%d')},"
            f"to_publication_date:{until.strftime('%Y-%m-%d')}"
        ),
        "per_page": 50,
        "select": (
            "id,title,authorships,abstract_inverted_index,"
            "doi,publication_date,primary_location,cited_by_count,open_access"
        ),
    }
    if mailto:
        params["mailto"] = mailto
    r = requests.get(WORKS_URL, params=params, timeout=30)
    r.raise_for_status()
    return [_parse_work(w) for w in r.json().get("results", []) if w.get("title")]


def _fetch_by_author(author_name: str, since: datetime, until: datetime, mailto: str) -> list[Item]:
    params: dict = {
        "filter": (
            f"raw_author_name.search:{author_name},"
            f"from_publication_date:{since.strftime('%Y-%m-%d')},"
            f"to_publication_date:{until.strftime('%Y-%m-%d')}"
        ),
        "per_page": 25,
        "select": (
            "id,title,authorships,abstract_inverted_index,"
            "doi,publication_date,primary_location,cited_by_count"
        ),
    }
    if mailto:
        params["mailto"] = mailto
    r = requests.get(WORKS_URL, params=params, timeout=30)
    r.raise_for_status()
    return [_parse_work(w) for w in r.json().get("results", []) if w.get("title")]


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex 以倒排索引存储摘要：{word: [positions]} → 重建原文。"""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))


def _parse_work(w: dict) -> Item:
    now = datetime.now(timezone.utc).isoformat()
    doi_raw = w.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "").strip() or None

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in (w.get("authorships") or [])[:20]
    ]

    primary_loc = w.get("primary_location") or {}
    source_info = primary_loc.get("source") or {}
    journal = source_info.get("display_name")

    oa_url = (w.get("open_access") or {}).get("oa_url")
    item_id = f"doi:{doi}" if doi else f"openalex:{w.get('id', '')}"

    return Item(
        id=item_id,
        title=w.get("title", ""),
        authors=authors,
        abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
        abstract_source="openalex_api",
        doi=doi,
        source_journal=journal,
        publication_date=w.get("publication_date", ""),
        status="published" if doi else "unverified",
        doi_verified=bool(doi),
        doi_verify_method="openalex_native" if doi else None,
        citation_count=w.get("cited_by_count"),
        citation_source=SOURCE,
        url=oa_url,
        fetch_sources=[SOURCE],
        fetched_at=now,
        raw={"openalex_id": w.get("id")},
    )
