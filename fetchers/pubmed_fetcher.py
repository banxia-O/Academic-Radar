"""PubMed E-utilities fetcher（PRD §2.2 Tier 1 主力源）。

接口：
  esearch.fcgi  按 MeSH + 自由词 + 时间窗口检索 → PMID 列表
  efetch.fcgi   根据 PMID 拉详细元数据（标题/作者/期刊/摘要/MeSH）

无 API key 时低频可用；填写 api_keys.pubmed_api_key 后可提至 10 req/s。
PubMed 来源 DOI/PMID 天然可信，不需 Crossref 二次验证（PRD §2.4 Step 3）。
"""
from __future__ import annotations

from datetime import datetime

from models import Item

SOURCE = "pubmed"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def build_query(topics_en: list[str], topics_zh: list[str], authors: list[str]) -> str:
    """组合 MeSH + 自由词 + 作者检索式。"""
    raise NotImplementedError


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    raise NotImplementedError
