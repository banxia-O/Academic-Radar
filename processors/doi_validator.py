"""DOI 验证与发表状态识别（PRD §2.4 Step 3）。

规则：
  - Tier 1 源（pubmed/semantic_scholar/openalex）的 DOI 天然可信，不调用外部 API
  - Tier 2/3 源的 DOI 先走 Crossref（结构化元数据）
  - Crossref 查不到时回退 doi.org HTTP HEAD（200 = 存在）
  - 超时不阻塞，标注 "⚠️DOI 待验证"

发表状态判定：
  published   有 DOI 且来自正式期刊
  preprint    来自 bioRxiv/medRxiv/arXiv
  conference  会议摘要（ASCO/ASTRO/ESMO 等关键词）
  unverified  仅社交平台讨论，无法追溯原始文献
"""
from __future__ import annotations

import logging

import requests

from models import Item

logger = logging.getLogger(__name__)

CROSSREF_URL = "https://api.crossref.org/works/{doi}"
DOI_RESOLVER = "https://doi.org/{doi}"
TRUSTED_SOURCES = {"pubmed", "semantic_scholar", "openalex"}
PREPRINT_SOURCES = {"biorxiv", "medrxiv"}
CONFERENCE_KEYWORDS = {"asco", "astro", "esmo", "sabcs", "abstract #", "abstract number", "conference abstract"}


def validate_items(items: list[Item], config: dict) -> list[Item]:
    mailto = config.get("api_keys", {}).get("crossref_mailto", "")
    for item in items:
        _set_status(item)
        if item.doi and not item.doi_verified:
            if _from_trusted_source(item):
                item.doi_verified = True
                src = next((s for s in item.fetch_sources if s in TRUSTED_SOURCES), "api")
                item.doi_verify_method = f"{src}_native"
            else:
                _verify_doi(item, mailto)
    return items


def _from_trusted_source(item: Item) -> bool:
    return bool(set(item.fetch_sources) & TRUSTED_SOURCES)


def _set_status(item: Item) -> None:
    if item.status != "unverified":
        return
    if set(item.fetch_sources) & PREPRINT_SOURCES or item.arxiv_id:
        item.status = "preprint"
    elif _is_conference(item):
        item.status = "conference"
    elif item.doi and _from_trusted_source(item):
        item.status = "published"
    elif item.doi:
        item.status = "published"


def _is_conference(item: Item) -> bool:
    text = f"{item.title} {item.abstract} {item.source_journal or ''}".lower()
    return any(k in text for k in CONFERENCE_KEYWORDS)


def _verify_doi(item: Item, mailto: str) -> None:
    doi = item.doi
    try:
        params = {"mailto": mailto} if mailto else {}
        r = requests.get(CROSSREF_URL.format(doi=doi), params=params, timeout=10)
        if r.status_code == 200:
            item.doi_verified = True
            item.doi_verify_method = "crossref_api"
            return
    except Exception as exc:
        logger.debug("Crossref lookup failed for %s: %s", doi, exc)

    try:
        r = requests.head(DOI_RESOLVER.format(doi=doi), timeout=10, allow_redirects=True)
        if r.status_code == 200:
            item.doi_verified = True
            item.doi_verify_method = "doi_resolver_head"
            return
    except Exception as exc:
        logger.debug("doi.org HEAD failed for %s: %s", doi, exc)

    logger.warning("DOI %s could not be verified (⚠️DOI 待验证)", doi)


def verify_doi_crossref(doi: str, mailto: str | None = None) -> dict | None:
    try:
        params = {"mailto": mailto} if mailto else {}
        r = requests.get(CROSSREF_URL.format(doi=doi), params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("message")
    except Exception:
        pass
    return None


def verify_doi_resolver(doi: str) -> bool:
    try:
        r = requests.head(DOI_RESOLVER.format(doi=doi), timeout=10, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False
