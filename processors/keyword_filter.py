"""关键词初筛（PRD §2.4 Step 1）。

脚本层完成，不消耗 LLM token：
  - 命中 topics（en/zh 任一关键词）→ 保留
  - 命中 authors（任一作者/机构）→ 保留（即使未命中 topic）
  - 命中 exclude → 丢弃
"""
from __future__ import annotations

from models import Item


def filter_items(items: list[Item], config: dict) -> list[Item]:
    raise NotImplementedError


def matches_topic(item: Item, topics_en: list[str], topics_zh: list[str]) -> bool:
    raise NotImplementedError


def matches_author(item: Item, authors: list[str]) -> bool:
    raise NotImplementedError


def hits_exclude(item: Item, exclude: list[str]) -> bool:
    raise NotImplementedError
