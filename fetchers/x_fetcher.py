"""X 平台 fetcher（PRD §2.2 Tier 2，社交信号层）。

价值定位：发现学术评论/争议/会议实时讨论，而非发现文献本身。
实现方式二选一：
  - X API v2（需 bearer token）
  - LLM 原生搜索能力（如支持联网检索的模型）

抓到的推文若引用了 Tier 1 已收录的论文，应在 dedup 阶段合并为同一条目
（追加 x_links / fetch_sources），不重复出条。
"""
from __future__ import annotations

from datetime import datetime

from models import Item

SOURCE = "x"


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    raise NotImplementedError
