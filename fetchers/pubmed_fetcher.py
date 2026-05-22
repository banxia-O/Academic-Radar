"""PubMed E-utilities fetcher（PRD §2.2 Tier 1 主力源）。

接口：
  esearch.fcgi  按 MeSH + 自由词 + 时间窗口检索 → PMID 列表
  efetch.fcgi   根据 PMID 拉详细元数据（标题/作者/期刊/摘要/MeSH）

无 API key 时低频可用；填写 api_keys.pubmed_api_key 后可提至 10 req/s。
PubMed 来源 DOI/PMID 天然可信，不需 Crossref 二次验证（PRD §2.4 Step 3）。
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from models import Item

logger = logging.getLogger(__name__)

SOURCE = "pubmed"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 100


def build_query(topics_en: list[str], topics_zh: list[str], authors: list[str]) -> str:
    topic_terms = [f'"{t}"[Title/Abstract]' for t in topics_en + topics_zh if t.strip()]
    author_terms = [f'"{a}"[Author]' for a in authors if a.strip()]
    parts = []
    if topic_terms:
        parts.append(f"({' OR '.join(topic_terms)})")
    if author_terms:
        parts.append(f"({' OR '.join(author_terms)})")
    return " OR ".join(parts)


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    topics = config.get("topics", {})
    api_key = config.get("api_keys", {}).get("pubmed_api_key", "")

    query = build_query(
        topics.get("en", []),
        topics.get("zh", []),
        config.get("authors", []),
    )
    if not query:
        return []

    try:
        pmids = _esearch(query, since, until, api_key)
    except Exception as exc:
        logger.warning("⚠️PubMed esearch failed: %s, retrying in 5s", exc)
        time.sleep(5)
        try:
            pmids = _esearch(query, since, until, api_key)
        except Exception as exc2:
            logger.error("⚠️PubMed 抓取失败: %s", exc2)
            return []

    if not pmids:
        return []

    items: list[Item] = []
    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i : i + BATCH_SIZE]
        try:
            items.extend(_efetch(batch, api_key))
        except Exception as exc:
            logger.warning("PubMed efetch batch failed: %s", exc)
        time.sleep(0.1 if api_key else 0.4)

    return items


def _esearch(query: str, since: datetime, until: datetime, api_key: str) -> list[str]:
    params: dict = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": since.strftime("%Y/%m/%d"),
        "maxdate": until.strftime("%Y/%m/%d"),
        "retmax": 500,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(ESEARCH_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def _efetch(pmids: list[str], api_key: str) -> list[Item]:
    params: dict = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(EFETCH_URL, params=params, timeout=60)
    r.raise_for_status()
    return _parse_xml(r.text)


def _parse_xml(xml_text: str) -> list[Item]:
    root = ET.fromstring(xml_text)
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for article in root.findall(".//PubmedArticle"):
        try:
            items.append(_parse_article(article, now))
        except Exception as exc:
            logger.debug("Failed to parse PubMed article: %s", exc)
    return items


def _parse_article(article: ET.Element, now: str) -> Item:
    mc = article.find("MedlineCitation")
    art = mc.find("Article")

    pmid = mc.findtext("PMID", "")
    title = art.findtext("ArticleTitle", "") or ""

    abstract_parts: list[str] = []
    for at in art.findall(".//AbstractText"):
        label = at.get("Label")
        text = (at.text or "").strip()
        if label and text:
            abstract_parts.append(f"{label}: {text}")
        elif text:
            abstract_parts.append(text)
    abstract = " ".join(abstract_parts)

    authors: list[str] = []
    for author in art.findall(".//AuthorList/Author"):
        last = author.findtext("LastName", "")
        initials = author.findtext("Initials", "")
        if last:
            authors.append(f"{last} {initials}".strip())

    journal = art.findtext("Journal/Title") or art.findtext("Journal/ISOAbbreviation") or ""
    pub_date = _parse_pub_date(art.find("Journal/JournalIssue/PubDate"))

    doi: str | None = None
    for aid in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text
            break

    item_id = f"doi:{doi}" if doi else f"pmid:{pmid}"

    return Item(
        id=item_id,
        title=title,
        authors=authors,
        abstract=abstract,
        abstract_source="pubmed_api",
        doi=doi,
        pmid=pmid,
        source_journal=journal,
        publication_date=pub_date,
        status="published",
        doi_verified=True,
        doi_verify_method="pubmed_native",
        fetch_sources=[SOURCE],
        fetched_at=now,
        raw={"pmid": pmid},
    )


def _parse_pub_date(el: ET.Element | None) -> str:
    if el is None:
        return ""
    year = el.findtext("Year", "")
    month = el.findtext("Month", "")
    day = el.findtext("Day", "")
    if year:
        parts = [year] + ([month] if month else []) + ([day] if day else [])
        return "-".join(parts)
    return el.findtext("MedlineDate", "")
