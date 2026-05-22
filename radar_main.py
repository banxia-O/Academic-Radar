"""Academic Radar 主入口。

调度顺序对应 PRD §2.4：
  1) 加载配置 + 计算时间窗口
  2) 各 Tier 1/2/3 源并发抓取
  3) 关键词初筛（脚本层，不消耗 token）
  4) LLM 相关性评分
  5) DOI 验证 + 发表状态识别
  6) 去重与多源合并
  7) 排序
  8) 格式化 + 推送
  9) 存档 JSON + 更新 state/last_success_ts
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from models import FetchStats, Item

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("academic_radar_config.yaml")
STATE_DIR = Path("state")
DATA_DIR = Path("data/radar")
ERRORS_DIR = DATA_DIR / "errors"

LAST_SUCCESS_FILE = STATE_DIR / "last_success_ts"
LAST_VALID_CONFIG = STATE_DIR / "last_valid_config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    """加载 YAML 配置。失败时回退到 state/last_valid_config.yaml 并告警（PRD §3）。"""
    raise NotImplementedError


def compute_time_window(now: datetime, last_success: datetime | None) -> tuple[datetime, datetime]:
    """PRD §2.1：起点 = max(上次成功时间, now - 48h)，终点 = now。"""
    raise NotImplementedError


def read_last_success() -> datetime | None:
    raise NotImplementedError


def write_last_success(ts: datetime) -> None:
    raise NotImplementedError


def fetch_all(config: dict, since: datetime, until: datetime, stats: FetchStats) -> list[Item]:
    """按 config.sources 开关分发到各 fetcher，单源失败不阻塞整体（PRD §3）。"""
    raise NotImplementedError


def archive(items: list[Item], stats: FetchStats, since: datetime, until: datetime, config: dict) -> Path:
    """写入 data/radar/YYYY-MM-DD_HHmm.json，并清理超过 retention 的旧档。"""
    raise NotImplementedError


def cleanup_old_archives(retention_days: int) -> None:
    raise NotImplementedError


def run_once() -> None:
    """执行一次完整流水线。被 cron 或 Agent 调度器调用。"""
    raise NotImplementedError


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_once()
