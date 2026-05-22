"""输出格式化（PRD §2.5）。

默认纯文本（适配微信等不支持 markdown 的平台）。
头部包含：抓取范围、各源命中数统计、命中总数。
每条包含：发表状态 emoji + 相关性、标题、作者、期刊/来源、DOI、引用数、核心发现、来源标注。
0 条时输出 "今日无新增"；超过 max_items 时截断并标注 "另有 N 条未展示"。
"""
from __future__ import annotations

from datetime import datetime

from models import FetchStats, Item

STATUS_EMOJI = {
    "published": "✅Published",
    "preprint": "📄Preprint",
    "conference": "🎤Conference",
    "unverified": "❓Unverified",
}


def format_message(
    items: list[Item],
    stats: FetchStats,
    since: datetime,
    until: datetime,
    config: dict,
) -> str:
    raise NotImplementedError


def format_item(item: Item, idx: int) -> str:
    raise NotImplementedError


def format_header(stats: FetchStats, since: datetime, until: datetime, hits: int) -> str:
    raise NotImplementedError
