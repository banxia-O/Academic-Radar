"""OpenAlex fetcher（PRD §2.2 Tier 1，广覆盖元数据补充）。

端点：https://api.openalex.org/works
价值：4.7 亿+ 作品，含非英文文献/数据集/预印本；补 PubMed 未收录内容
限制：10 万请求 / 天。加 mailto 参数进入 polite pool。
用途：concept/topic 过滤 + 作者/机构追踪。
"""
from __future__ import annotations

from datetime import datetime

from models import Item

SOURCE = "openalex"
WORKS_URL = "https://api.openalex.org/works"


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    raise NotImplementedError
