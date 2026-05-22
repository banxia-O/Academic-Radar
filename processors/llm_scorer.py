"""LLM 相关性评分（PRD §2.4 Step 2）。

职责边界（PRD §附录 B 反幻觉）：
  - 输入：标题 + 摘要 + 用户研究方向描述（config.research_focus）
  - 输出：1-5 分 + 基于 abstract 原文的核心发现摘要
  - 严禁生成或改写任何书目元数据（title/author/DOI/期刊）
  - 严禁在 summary 中添加 abstract 未提及的数据或结论

格式异常处理：
  - 评分非 1-5 整数 → 该条进入 errors 日志，不进入推送
  - 调用超时 → 同上
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from openai import OpenAI

from models import Item

logger = logging.getLogger(__name__)

SCORE_KEEP_THRESHOLD = 3


def score_items(items: list[Item], config: dict) -> tuple[list[Item], list[dict]]:
    """返回 (评分 >= 3 的条目, 评分异常条目日志)。"""
    llm_cfg = config.get("llm", {})
    research_focus = config.get("research_focus", "").strip()

    client = OpenAI(
        base_url=llm_cfg.get("base_url", "https://api.openai.com/v1"),
        api_key=llm_cfg.get("api_key", ""),
    )

    kept: list[Item] = []
    errors: list[dict] = []

    for item in items:
        try:
            result = call_llm(build_prompt(item, research_focus), llm_cfg, client)
            score = result.get("score")
            if not isinstance(score, int) or score not in range(1, 6):
                raise ValueError(f"Invalid score value: {score!r}")
            item.relevance_score = score
            item.summary = result.get("summary", "")
            if score >= SCORE_KEEP_THRESHOLD:
                kept.append(item)
        except Exception as exc:
            errors.append({
                "item_id": item.id,
                "title": item.title[:120],
                "error": str(exc),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            logger.warning("LLM scoring failed for '%s': %s", item.title[:60], exc)

    return kept, errors


def build_prompt(item: Item, research_focus: str) -> str:
    abstract = item.abstract or "（无摘要）"
    focus_section = f"用户的研究方向：\n{research_focus}\n\n" if research_focus else ""
    return (
        f"{focus_section}"
        f"以下是一篇论文的标题和摘要：\n"
        f"标题：{item.title}\n"
        f"摘要：{abstract}\n\n"
        f"请基于上述研究方向，为这篇论文的相关性打分（1-5分）：\n"
        f"5 = 研究方向核心文献\n"
        f"4 = 同领域重要进展\n"
        f"3 = 相邻领域，有参考价值\n"
        f"2 = 仅关键词匹配，实际关联弱\n"
        f"1 = 不相关\n\n"
        f"同时基于摘要原文提供1-2句核心发现总结"
        f"（仅基于以下摘要内容，不添加摘要中未出现的信息）。\n\n"
        f'以JSON格式返回（不添加任何其他内容）：{{"score": <1-5整数>, "summary": "<核心发现摘要>"}}'
    )


def call_llm(prompt: str, llm_cfg: dict, client: OpenAI) -> dict:
    """调用 OpenAI 兼容接口，返回 {"score": int, "summary": str}。"""
    response = client.chat.completions.create(
        model=llm_cfg.get("model", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        timeout=llm_cfg.get("timeout", 30),
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
