"""Semantic Scholar Graph API fetcher（PRD §2.2 Tier 1，引文网络分析）。

端点：https://api.semanticscholar.org/graph/v1/paper/search
价值：TLDR、引用数、influential citation、跨数据库 ID 映射
限制：100 req / 5min（无 key），需做请求节流；限流时指数退避（PRD §3）
"""
from __future__ import annotations

from datetime import datetime

from models import Item

SOURCE = "semantic_scholar"
SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = (
    "title,authors,abstract,tldr,year,venue,"
    "externalIds,citationCount,influentialCitationCount,publicationDate"
)


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    raise NotImplementedError
