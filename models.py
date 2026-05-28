"""共享数据模型：流水线各阶段传递的 Item 结构。

字段与 PRD §2.6 存档 JSON 对齐，新增字段时同步存档 schema。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

PublishStatus = Literal["published", "preprint", "conference", "unverified"]


@dataclass
class Item:
    title: str
    authors: list[str]
    abstract: str
    fetch_sources: list[str]
    fetched_at: str

    id: str = ""
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv_id: Optional[str] = None
    source_journal: Optional[str] = None
    publication_date: Optional[str] = None

    status: PublishStatus = "unverified"
    doi_verified: bool = False
    doi_verify_method: Optional[str] = None

    relevance_score: Optional[int] = None
    summary: Optional[str] = None
    abstract_source: Optional[str] = None

    citation_count: Optional[int] = None
    citation_source: Optional[str] = None
    influential_citation_count: Optional[int] = None
    tldr: Optional[str] = None

    x_links: list[str] = field(default_factory=list)
    url: Optional[str] = None

    raw: dict = field(default_factory=dict)


@dataclass
class FetchStats:
    """PRD §2.6 stats 段：每个源的检索与过滤计数。"""
    pubmed_searched: int = 0
    semantic_scholar_searched: int = 0
    openalex_searched: int = 0
    biorxiv_searched: int = 0
    medrxiv_searched: int = 0
    arxiv_searched: int = 0
    x_searched: int = 0
    rss_processed: int = 0
    manual_processed: int = 0
    after_keyword_filter: int = 0
    after_llm_scoring: int = 0
    after_dedup: int = 0
    final_output: int = 0
