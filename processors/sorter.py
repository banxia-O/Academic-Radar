"""排序（PRD §2.4 Step 5）。

排序键（依次降序）：
  1) 发表状态优先级：published > preprint > conference > unverified
  2) 相关性评分（5 → 1）
  3) 发布时间（新 → 旧）
"""
from __future__ import annotations

from models import Item

STATUS_PRIORITY = {"published": 3, "preprint": 2, "conference": 1, "unverified": 0}


def sort_items(items: list[Item]) -> list[Item]:
    raise NotImplementedError
