"""推送适配器（PRD §1 推送渠道可配置）。

按 config.push.channel 分发到对应渠道：
  webhook / telegram / slack / email

新增渠道时在此扩展 dispatch 表，无需改主流程。
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

logger = logging.getLogger(__name__)


def push(message: str, config: dict) -> bool:
    """返回 True 表示推送成功；失败不抛异常，记录日志。"""
    push_cfg = config.get("push", {})
    channel = push_cfg.get("channel", "webhook")

    dispatch = {
        "webhook": lambda: push_webhook(message, push_cfg.get("webhook_url", "")),
        "telegram": lambda: push_telegram(
            message,
            push_cfg.get("telegram_bot_token", ""),
            push_cfg.get("telegram_chat_id", ""),
        ),
        "slack": lambda: push_slack(message, push_cfg.get("slack_webhook_url", "")),
        "email": lambda: push_email(message, push_cfg.get("smtp", {})),
    }

    fn = dispatch.get(channel)
    if not fn:
        logger.error("Unknown push channel: %s", channel)
        return False

    try:
        return fn()
    except Exception as exc:
        logger.error("Push failed [%s]: %s", channel, exc)
        return False


def push_webhook(message: str, webhook_url: str) -> bool:
    if not webhook_url:
        logger.warning("webhook_url not configured")
        return False
    r = requests.post(
        webhook_url,
        json={"msgtype": "text", "text": {"content": message}},
        timeout=15,
    )
    r.raise_for_status()
    return True


def push_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token or chat_id not configured")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
    r.raise_for_status()
    return True


def push_slack(message: str, webhook_url: str) -> bool:
    if not webhook_url:
        logger.warning("slack webhook_url not configured")
        return False
    r = requests.post(webhook_url, json={"text": message}, timeout=15)
    r.raise_for_status()
    return True


def push_email(message: str, smtp_config: dict) -> bool:
    host = smtp_config.get("host", "")
    port = int(smtp_config.get("port", 587))
    user = smtp_config.get("user", "")
    password = smtp_config.get("password", "")
    to_addr = smtp_config.get("to", "")

    if not all([host, user, password, to_addr]):
        logger.warning("SMTP config incomplete")
        return False

    msg = MIMEText(message, "plain", "utf-8")
    msg["Subject"] = "📡 学术雷达推送"
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
    return True
