"""Semantic Scholar Graph API fetcher（PRD §2.2 Tier 1，引文网络分析）。

端点：https://api.semanticscholar.org/graph/v1/paper/search
价值：TLDR、引用数、influential citation、跨数据库 ID 映射
限制：100 req / 5min（无 key），需做请求节流；限流时指数退避（PRD §3）
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from models import Item

logger = logging.getLogger(__name__)

SOURCE = "semantic_scholar"
SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = (
    "title,authors,abstract,tldr,year,venue,"
    "externalIds,citationCount,influentialCitationCount,publicationDate"
)
MAX_QUERIES = 5


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    topics = config.get("topics", {})
    queries = topics.get("en", [])[:MAX_QUERIES]
    api_key = config.get("api_keys", {}).get("semantic_scholar_key", "")

    items: list[Item] = []
    seen_ids: set[str] = set()

    for query in queries:
        try:
            batch = _search(query, since, until, api_key)
            for item in batch:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    items.append(item)
        except Exception as exc:
            logger.warning("S2 search failed for query '%s': %s", query[:40], exc)
        time.sleep(1.5 if not api_key else 0.1)

    return items


def _search(query: str, since: datetime, until: datetime, api_key: str) -> list[Item]:
    headers = {"x-api-key": api_key} if api_key else {}
    params = {
        "query": query,
        "fields": FIELDS,
        "limit": 100,
        "fieldsOfStudy": "Medicine,Biology",
        "publicationDateOrYear": f"{since.strftime('%Y-%m-%d')}:{until.strftime('%Y-%m-%d')}",
    }

    r = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
    if r.status_code == 429:
        logger.warning("S2 rate limited, backing off 60s")
        time.sleep(60)
        r = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()

    return [_parse_paper(p) for p in r.json().get("data", []) if p.get("title")]


def _parse_paper(p: dict) -> Item:
    now = datetime.now(timezone.utc).isoformat()
    external = p.get("externalIds") or {}
    doi = external.get("DOI")
    pmid = str(external["PubMed"]) if external.get("PubMed") else None
    arxiv_id = external.get("ArXiv")

    item_id = f"doi:{doi}" if doi else (f"pmid:{pmid}" if pmid else f"s2:{p.get('paperId', '')}")
    authors = [a.get("name", "") for a in (p.get("authors") or [])[:20]]
    tldr = (p.get("tldr") or {}).get("text")
    pub_date = p.get("publicationDate") or str(p.get("year", ""))

    status: str
    if arxiv_id:
        status = "preprint"
    elif doi:
        status = "published"
    else:
        status = "unverified"

    return Item(
        id=item_id,
        title=p.get("title", ""),
        authors=authors,
        abstract=p.get("abstract") or "",
        abstract_source="semantic_scholar_api",
        doi=doi,
        pmid=pmid,
        arxiv_id=arxiv_id,
        source_journal=p.get("venue"),
        publication_date=pub_date,
        status=status,
        doi_verified=bool(doi),
        doi_verify_method="semantic_scholar_native" if doi else None,
        citation_count=p.get("citationCount"),
        influential_citation_count=p.get("influentialCitationCount"),
        citation_source=SOURCE,
        tldr=tldr,
        fetch_sources=[SOURCE],
        fetched_at=now,
        raw={"s2_paper_id": p.get("paperId")},
    )
