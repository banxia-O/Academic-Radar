"""输出格式化（PRD §2.5）。

默认纯文本（适配微信等不支持 markdown 的平台）。
头部：抓取时间范围、各源命中数、命中总数。
条目：发表状态 emoji + 相关性分、标题、作者、期刊/来源、DOI/链接、引用数、核心发现、数据来源。
0 条时输出"今日无新增"；超过 max_items 时截断并标注"另有 N 条未展示"。
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
    max_items = config.get("output", {}).get("max_items", 15)
    display = items[:max_items]
    truncated = len(items) - len(display)

    sections: list[str] = [format_header(stats, since, until, len(display))]

    if not display:
        sections.append("今日无新增")
    else:
        for i, item in enumerate(display, 1):
            sections.append(format_item(item, i))

    footer_lines: list[str] = ["———"]
    if truncated > 0:
        footer_lines.append(f"另有 {truncated} 条未展示，回复「更多」查看")

    kw_version = config.get("_config_mtime", "")
    if kw_version:
        footer_lines.append(f"关键词版本: {kw_version}")

    next_run = _next_run_hint(config)
    if next_run:
        footer_lines.append(f"下次抓取: {next_run}")

    sections.append("\n".join(footer_lines))
    return "\n\n".join(sections)


def format_header(stats: FetchStats, since: datetime, until: datetime, hits: int) -> str:
    now_str = datetime.now().strftime("%m-%d %H:%M")
    biorxiv_total = stats.biorxiv_searched + stats.medrxiv_searched
    lines = [
        f"📡 学术雷达 {now_str}",
        f"抓取范围：{since.strftime('%m-%d %H:%M')} ~ {until.strftime('%m-%d %H:%M')}",
        (
            f"PubMed: {stats.pubmed_searched} | "
            f"S2: {stats.semantic_scholar_searched} | "
            f"OpenAlex: {stats.openalex_searched} | "
            f"bioRxiv: {biorxiv_total} | "
            f"arXiv: {stats.arxiv_searched} | "
            f"X: {stats.x_searched} | "
            f"RSS: {stats.rss_processed}"
        ),
        f"命中: {hits} 条",
        "\n———",
    ]
    return "\n".join(lines)


def format_item(item: Item, idx: int) -> str:
    status_label = STATUS_EMOJI.get(item.status, "❓Unverified")
    score = item.relevance_score if item.relevance_score is not None else "?"
    lines = [f"{idx}. {status_label} | 相关性:{score}"]

    lines.append(f"标题: {item.title}")

    if item.authors:
        authors_str = ", ".join(item.authors[:3])
        if len(item.authors) > 3:
            authors_str += ", et al."
        lines.append(f"作者: {authors_str}")

    if item.source_journal:
        year = (item.publication_date or "")[:4]
        lines.append(f"期刊: {item.source_journal}" + (f", {year}" if year else ""))

    if item.doi:
        lines.append(f"DOI: {item.doi}")
    elif item.url:
        lines.append(f"链接: {item.url}")

    if item.citation_count is not None:
        src_abbr = (item.citation_source or "").upper()[:2] or "?"
        lines.append(f"引用: {item.citation_count} ({src_abbr})")

    if item.summary:
        lines.append(f"核心发现: {item.summary}")
    elif item.tldr:
        lines.append(f"核心发现: {item.tldr}")

    sources_str = " + ".join(item.fetch_sources)
    if item.x_links:
        handles = [
            lnk.split("x.com/")[1].split("/")[0]
            for lnk in item.x_links
            if "x.com/" in lnk
        ]
        if handles:
            sources_str += f" + X(@{handles[0]} 讨论)"
    lines.append(f"来源: {sources_str}")

    if item.status == "preprint":
        is_published = item.doi_verify_method == "biorxiv_published_field"
        lines.append(f"正式发表: {'已检出' if is_published else '未检出'}")

    return "\n".join(lines)


def _next_run_hint(config: dict) -> str:
    sched = config.get("schedule", {})
    freq = sched.get("frequency", "daily")
    times = sched.get("times") or ["08:00"]
    primary = times[0]

    if freq == "every_4_hours":
        return "4 小时后"
    if freq == "monthly":
        return f"下月 1 号 {primary}"

    if freq == "twice_daily":
        now_hm = datetime.now().strftime("%H:%M")
        upcoming = sorted(t for t in times if t > now_hm)
        if upcoming:
            return upcoming[0]
        return f"明日 {sorted(times)[0]}"

    interval_days = {
        "daily": 1,
        "every_3_days": 3,
        "weekly": 7,
        "biweekly": 14,
        "custom": sched.get("custom_days", 7),
    }.get(freq, 1)

    if interval_days == 1:
        now_hm = datetime.now().strftime("%H:%M")
        return primary if primary > now_hm else f"明日 {primary}"
    return f"{interval_days} 天后 {primary}"
