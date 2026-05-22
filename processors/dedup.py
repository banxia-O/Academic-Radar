"""去重与多源合并（PRD §2.4 Step 4）。

去重优先级：DOI > PMID > 标题相似度（≥80%）
合并优先级：PubMed > Semantic Scholar > OpenAlex > bioRxiv
  - 保留元数据最规范的版本作为主条目
  - 其他源的补充字段（如 S2 引用数、X 讨论链接）合并进主条目
  - fetch_sources 合并为去重后的列表
"""
from __future__ import annotations

from models import Item

SOURCE_PRIORITY = ["pubmed", "semantic_scholar", "openalex", "biorxiv", "medrxiv", "rss", "x"]
TITLE_SIMILARITY_THRESHOLD = 0.8


def merge(items: list[Item]) -> list[Item]:
    raise NotImplementedError


def title_similarity(a: str, b: str) -> float:
    """Jaccard 或 Levenshtein 归一化相似度，返回 0~1。"""
    raise NotImplementedError


def merge_pair(primary: Item, secondary: Item) -> Item:
    """将 secondary 的补充字段合并进 primary。"""
    raise NotImplementedError
