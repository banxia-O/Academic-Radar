"""关键词初筛（PRD §2.4 Step 1）。

脚本层完成，不消耗 LLM token：
  - 命中 topics（en/zh 任一关键词）→ 保留
  - 命中 authors（任一作者/机构）→ 保留（即使未命中 topic）
  - 命中 exclude → 丢弃
"""
from __future__ import annotations

from models import Item


def filter_items(items: list[Item], config: dict) -> list[Item]:
    topics = config.get("topics", {})
    topics_en = topics.get("en", [])
    topics_zh = topics.get("zh", [])
    authors = config.get("authors", [])
    exclude = config.get("exclude", [])

    result = []
    for item in items:
        if hits_exclude(item, exclude):
            continue
        if matches_author(item, authors) or matches_topic(item, topics_en, topics_zh):
            result.append(item)
    return result


def matches_topic(item: Item, topics_en: list[str], topics_zh: list[str]) -> bool:
    text_lower = f"{item.title} {item.abstract}".lower()
    if any(p.lower() in text_lower for p in topics_en):
        return True
    text_orig = f"{item.title} {item.abstract}"
    return any(p in text_orig for p in topics_zh)


def matches_author(item: Item, authors: list[str]) -> bool:
    haystack = " ".join(item.authors).lower()
    return any(a.lower() in haystack for a in authors)


def hits_exclude(item: Item, exclude: list[str]) -> bool:
    text = f"{item.title} {item.abstract}".lower()
    return any(e.lower() in text for e in exclude)
