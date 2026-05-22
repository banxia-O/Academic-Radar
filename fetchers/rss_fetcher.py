"""RSS fetcher（PRD §2.2 Tier 3，辅助源）。

通过 RSSHub 或期刊原生 RSS 订阅目标信息源。
公众号/博客等二手信息源拉取的条目必须追溯到原始学术来源（DOI 或论文链接），
否则在 doi_validator 阶段标为 unverified。
"""
from __future__ import annotations

from datetime import datetime

from models import Item

SOURCE = "rss"


def fetch(config: dict, since: datetime, until: datetime) -> list[Item]:
    """遍历 config.rss_feeds，单个 feed 失败不影响其他 feed。"""
    raise NotImplementedError
