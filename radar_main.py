"""Academic Radar 主入口。

调度顺序对应 PRD §2.4：
  1) 加载配置 + 计算时间窗口
  2) 各 Tier 1/2/3 源抓取（各源独立容错）
  3) 关键词初筛（脚本层，不消耗 token）
  4) LLM 相关性评分
  5) DOI 验证 + 发表状态识别
  6) 去重与多源合并
  7) 排序
  8) 格式化 + 推送
  9) 存档 JSON + 更新 state/last_success_ts
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from fetchers import (
    biorxiv_fetcher,
    openalex_fetcher,
    pubmed_fetcher,
    rss_fetcher,
    semantic_scholar_fetcher,
    x_fetcher,
)
from models import FetchStats, Item
from output import formatter, pusher
from processors import dedup, doi_validator, keyword_filter, llm_scorer, sorter

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("academic_radar_config.yaml")
STATE_DIR = Path("state")
DATA_DIR = Path("data/radar")
ERRORS_DIR = DATA_DIR / "errors"
LAST_SUCCESS_FILE = STATE_DIR / "last_success_ts"
LAST_VALID_CONFIG = STATE_DIR / "last_valid_config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    """加载 YAML 配置。失败时回退到 state/last_valid_config.yaml 并告警（PRD §3）。"""
    try:
        with open(path) as f:
            cfg = yaml.safe_load(f)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LAST_VALID_CONFIG, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True)
        cfg["_config_mtime"] = datetime.fromtimestamp(path.stat().st_mtime).strftime("%m-%d")
        return cfg
    except Exception as exc:
        logger.error("Config load failed: %s", exc)
        if LAST_VALID_CONFIG.exists():
            logger.warning("Using last valid config: %s", LAST_VALID_CONFIG)
            with open(LAST_VALID_CONFIG) as f:
                return yaml.safe_load(f)
        raise


def compute_time_window(now: datetime, last_success: datetime | None) -> tuple[datetime, datetime]:
    """PRD §2.1：起点 = max(上次成功时间, now - 48h)，终点 = now。"""
    floor = now - timedelta(hours=48)
    since = max(last_success, floor) if last_success else floor
    return since, now


def read_last_success() -> datetime | None:
    if not LAST_SUCCESS_FILE.exists():
        return None
    try:
        return datetime.fromisoformat(LAST_SUCCESS_FILE.read_text().strip())
    except Exception:
        return None


def write_last_success(ts: datetime) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_SUCCESS_FILE.write_text(ts.isoformat())


def fetch_all(config: dict, since: datetime, until: datetime, stats: FetchStats) -> list[Item]:
    """按 config.sources 开关分发，单源失败不阻塞整体（PRD §3）。"""
    sources = config.get("sources", {})
    all_items: list[Item] = []

    def _safe(name: str, fn, stat_attr: str) -> None:
        if not sources.get(name, True):
            return
        try:
            items = fn(config, since, until)
            setattr(stats, stat_attr, len(items))
            all_items.extend(items)
            logger.info("%s: %d items", name, len(items))
        except Exception as exc:
            logger.error("⚠️%s 抓取失败: %s", name, exc)

    _safe("pubmed", pubmed_fetcher.fetch, "pubmed_searched")
    _safe("semantic_scholar", semantic_scholar_fetcher.fetch, "semantic_scholar_searched")
    _safe("openalex", openalex_fetcher.fetch, "openalex_searched")
    _safe("x_search", x_fetcher.fetch, "x_searched")
    _safe("rss", rss_fetcher.fetch, "rss_processed")

    # bioRxiv + medRxiv share one fetcher that checks sources internally
    if sources.get("biorxiv", True) or sources.get("medrxiv", True):
        try:
            bx = biorxiv_fetcher.fetch(config, since, until)
            for item in bx:
                if "biorxiv" in item.fetch_sources:
                    stats.biorxiv_searched += 1
                else:
                    stats.medrxiv_searched += 1
            all_items.extend(bx)
            logger.info("biorxiv/medrxiv: %d items", len(bx))
        except Exception as exc:
            logger.error("⚠️bioRxiv/medRxiv 抓取失败: %s", exc)

    return all_items


def archive(
    items: list[Item],
    stats: FetchStats,
    errors: list[dict],
    since: datetime,
    until: datetime,
    config: dict,
) -> Path:
    """写入 data/radar/YYYY-MM-DD_HHmm.json（PRD §2.6）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filename = DATA_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"

    def _item_dict(item: Item) -> dict:
        d = {k: v for k, v in item.__dict__.items() if k != "raw"}
        return d

    payload = {
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "time_window": {"from": since.isoformat(), "to": until.isoformat()},
        "config_version": config.get("_config_mtime", ""),
        "stats": stats.__dict__,
        "items": [_item_dict(i) for i in items],
        "errors": errors,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Archived to %s", filename)
    return filename


def cleanup_old_archives(retention_days: int) -> None:
    cutoff = datetime.now() - timedelta(days=retention_days)
    for f in DATA_DIR.glob("*.json"):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
        except Exception:
            pass


def run_once() -> None:
    """执行一次完整流水线。被 cron 或 Agent 调度器调用。"""
    config = load_config()

    tz_name = config.get("timezone", "Asia/Shanghai")
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    now = datetime.now(tz)
    since, until = compute_time_window(now, read_last_success())
    logger.info("Window: %s → %s", since.isoformat(), until.isoformat())

    stats = FetchStats()

    # Steps 1-2: fetch
    items = fetch_all(config, since, until, stats)
    logger.info("Total fetched: %d", len(items))

    # Step 3: keyword filter (no LLM token)
    items = keyword_filter.filter_items(items, config)
    stats.after_keyword_filter = len(items)
    logger.info("After keyword filter: %d", len(items))

    # Step 4: LLM scoring
    items, errors = llm_scorer.score_items(items, config)
    stats.after_llm_scoring = len(items)
    logger.info("After LLM scoring: %d (errors: %d)", len(items), len(errors))

    if errors:
        ERRORS_DIR.mkdir(parents=True, exist_ok=True)
        err_file = ERRORS_DIR / f"{now.strftime('%Y-%m-%d_%H%M')}_errors.json"
        with open(err_file, "w") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    # Step 5: DOI validation
    items = doi_validator.validate_items(items, config)

    # Step 6: dedup
    items = dedup.merge(items)
    stats.after_dedup = len(items)
    logger.info("After dedup: %d", len(items))

    # Step 7: sort
    items = sorter.sort_items(items)

    # Steps 8-9: format, push, archive, state
    max_items = config.get("output", {}).get("max_items", 15)
    stats.final_output = min(len(items), max_items)

    message = formatter.format_message(items, stats, since, until, config)
    push_ok = pusher.push(message, config)
    if not push_ok:
        logger.error("Push failed — message saved to archive only")

    archive(items[:max_items], stats, errors, since, until, config)
    write_last_success(now)
    cleanup_old_archives(config.get("archive_retention_days", 30))

    logger.info(
        "Done. output=%d push=%s",
        stats.final_output,
        "OK" if push_ok else "FAILED",
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_once()
