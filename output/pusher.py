"""推送适配器（PRD §1 推送渠道可配置）。

按 config.push.channel 分发到对应渠道：
  webhook / telegram / slack / email

新增渠道时在此扩展 dispatch 表，无需改主流程。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def push(message: str, config: dict) -> bool:
    """返回 True 表示推送成功；失败不抛异常，记录日志。"""
    raise NotImplementedError


def push_webhook(message: str, webhook_url: str) -> bool:
    raise NotImplementedError


def push_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    raise NotImplementedError


def push_slack(message: str, webhook_url: str) -> bool:
    raise NotImplementedError


def push_email(message: str, smtp_config: dict) -> bool:
    raise NotImplementedError
