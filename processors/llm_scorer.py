"""LLM 相关性评分（PRD §2.4 Step 2）。

职责边界（PRD §附录 B 反幻觉）：
  - 输入：标题 + 摘要 + 用户研究方向描述（config.research_focus）
  - 输出：1-5 分 + 基于 abstract 的核心发现摘要
  - 严禁生成或改写任何书目元数据（title/author/DOI/期刊）
  - 严禁在 summary 中添加 abstract 未提及的数据或结论

格式异常处理：
  - 评分非 1-5 整数 → 该条进入 errors 日志，不进入推送
  - 调用超时 → 同上
"""
from __future__ import annotations

from models import Item

SCORE_KEEP_THRESHOLD = 3  # 评分 ≥ 3 才保留（PRD §2.4 Step 2）


def score_items(items: list[Item], config: dict) -> tuple[list[Item], list[dict]]:
    """返回 (保留的条目, 异常条目日志)。"""
    raise NotImplementedError


def build_prompt(item: Item, research_focus: str) -> str:
    raise NotImplementedError


def call_llm(prompt: str, llm_config: dict) -> dict:
    """调用 OpenAI 兼容接口，返回 {"score": int, "summary": str}。"""
    raise NotImplementedError
