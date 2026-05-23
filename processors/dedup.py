"""去重与多源合并（PRD §2.4 Step 4）。

单次运行内去重优先级：DOI > PMID > 标题相似度（≥80%）
合并优先级：PubMed > Semantic Scholar > OpenAlex > bioRxiv > medRxiv > RSS > X
  - 保留元数据最规范的版本作为主条目
  - 其他源的补充字段（引用数、TLDR、X 讨论链接）合并进主条目
  - fetch_sources 合并为去重后的去重列表

跨周期去重：读取近 N 天存档（即历史已推送条目）的指纹集合，
在 LLM 评分前剔除重复，避免窗口边界文章被反复推送、并省下重复评分的 token。
"""
from __future__ import annotations

import difflib
import json
import logging
from datetime import datetime
from pathlib import Path

from models import Item

logger = logging.getLogger(__name__)

SOURCE_PRIORITY = ["pubmed", "semantic_scholar", "openalex", "biorxiv", "medrxiv", "rss", "x"]
TITLE_SIMILARITY_THRESHOLD = 0.8


def merge(items: list[Item]) -> list[Item]:
    def source_rank(item: Item) -> int:
        for s in item.fetch_sources:
            if s in SOURCE_PRIORITY:
                return SOURCE_PRIORITY.index(s)
        return len(SOURCE_PRIORITY)

    items = sorted(items, key=source_rank)
    used: set[int] = set()
    merged: list[Item] = []

    for i, item in enumerate(items):
        if i in used:
            continue
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            if _should_merge(item, items[j]):
                merge_pair(item, items[j])
                used.add(j)
        merged.append(item)

    return merged


def _should_merge(a: Item, b: Item) -> bool:
    if a.doi and b.doi and a.doi.lower() == b.doi.lower():
        return True
    if a.pmid and b.pmid and a.pmid == b.pmid:
        return True
    return title_similarity(a.title, b.title) >= TITLE_SIMILARITY_THRESHOLD


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def merge_pair(primary: Item, secondary: Item) -> Item:
    if not primary.doi and secondary.doi:
        primary.doi = secondary.doi
    if not primary.pmid and secondary.pmid:
        primary.pmid = secondary.pmid
    if not primary.abstract and secondary.abstract:
        primary.abstract = secondary.abstract
        primary.abstract_source = secondary.abstract_source
    if not primary.source_journal and secondary.source_journal:
        primary.source_journal = secondary.source_journal
    if not primary.publication_date and secondary.publication_date:
        primary.publication_date = secondary.publication_date
    if secondary.citation_count is not None and (
        primary.citation_count is None or secondary.citation_count > primary.citation_count
    ):
        primary.citation_count = secondary.citation_count
        primary.citation_source = secondary.citation_source
    if not primary.tldr and secondary.tldr:
        primary.tldr = secondary.tldr
    if not primary.url and secondary.url:
        primary.url = secondary.url
    primary.x_links = list({*primary.x_links, *secondary.x_links})
    for s in secondary.fetch_sources:
        if s not in primary.fetch_sources:
            primary.fetch_sources.append(s)
    return primary


def fingerprint(
    doi: str | None = None,
    pmid: str | None = None,
    arxiv_id: str | None = None,
    title: str = "",
) -> str | None:
    """跨周期去重用的稳定标识：DOI > PMID > arXiv > 规范化标题。无任何可用标识时返回 None。"""
    if doi:
        return f"doi:{doi.lower().strip()}"
    if pmid:
        return f"pmid:{str(pmid).strip()}"
    if arxiv_id:
        return f"arxiv:{arxiv_id.lower().strip()}"
    norm = "".join(c for c in title.lower() if c.isalnum())
    return f"title:{norm}" if norm else None


def item_fingerprint(item: Item) -> str | None:
    return fingerprint(item.doi, item.pmid, item.arxiv_id, item.title)


def load_seen_fingerprints(archive_dir: Path, lookback_days: int, now: datetime) -> set[str]:
    """扫描近 lookback_days 天的存档 JSON，收集历史已推送条目的指纹集合。"""
    seen: set[str] = set()
    if lookback_days <= 0 or not archive_dir.exists():
        return seen
    cutoff = now.timestamp() - lookback_days * 86400
    for f in archive_dir.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Skip archive %s while loading seen set: %s", f.name, exc)
            continue
        for it in data.get("items", []):
            fp = fingerprint(it.get("doi"), it.get("pmid"), it.get("arxiv_id"), it.get("title", ""))
            if fp:
                seen.add(fp)
    return seen


def filter_seen(items: list[Item], seen: set[str]) -> list[Item]:
    """剔除指纹已出现在历史存档中的条目（跨周期去重）。seen 为空时原样返回。"""
    if not seen:
        return items
    return [it for it in items if item_fingerprint(it) not in seen]
