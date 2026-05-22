"""bioRxiv / medRxiv fetcher（PRD §2.2 Tier 1，预印本）。

端点：https://api.biorxiv.org/details/[server]/[interval]
server = biorxiv 或 medrxiv
按日期范围批量拉取后本地关键词过滤（API 不支持复杂检索）。
返回的 published 字段可判断是否已有正式发表版（PRD §2.4 Step 3）。
"""
from __future__ import annotations

from datetime import datetime

from models import Item

SOURCE_BIORXIV = "biorxiv"
SOURCE_MEDRXIV = "medrxiv"
DETAILS_URL = "https://api.biorxiv.org/details/{server}/{interval}/{cursor}"


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    """同时处理 biorxiv 与 medrxiv，按 config.sources 开关决定是否各自启用。"""
    raise NotImplementedError


def check_published_version(doi: str) -> str | None:
    """查询预印本是否已有正式发表版本，返回正式 DOI 或 None。"""
    raise NotImplementedError
