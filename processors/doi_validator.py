"""DOI 验证与发表状态识别（PRD §2.4 Step 3）。

规则：
  - Tier 1 源（pubmed/semantic_scholar/openalex）的 DOI 天然可信，不验证
  - Tier 2/3 源的 DOI 先走 Crossref（结构化元数据）
  - Crossref 查不到时回退 doi.org HTTP HEAD（200 = 存在）
  - 超时不阻塞，标注 "⚠️DOI 待验证"

发表状态判定：
  published   有 DOI 且来自正式期刊
  preprint    来自 bioRxiv/medRxiv/arXiv（可附带是否有正式发表版的查询结果）
  conference  会议摘要（ASCO/ASTRO/ESMO 等）
  unverified  仅社交平台讨论，无法追溯原始文献
"""
from __future__ import annotations

from models import Item

CROSSREF_URL = "https://api.crossref.org/works/{doi}"
DOI_RESOLVER = "https://doi.org/{doi}"
TRUSTED_SOURCES = {"pubmed", "semantic_scholar", "openalex"}


def validate_items(items: list[Item], config: dict) -> list[Item]:
    """就地更新每个 item 的 status / doi_verified / doi_verify_method。"""
    raise NotImplementedError


def verify_doi_crossref(doi: str, mailto: str | None = None) -> dict | None:
    raise NotImplementedError


def verify_doi_resolver(doi: str) -> bool:
    raise NotImplementedError
