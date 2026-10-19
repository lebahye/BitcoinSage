"""OPTIONAL alert delivery for My Plan call changes.  OFF by default.

Nothing is sent unless ALL of these hold:
  1. the user ticked "Send me alerts" in My Plan → 🔔 Alert settings (saved in data/notify_settings.json), and
  2. the channel's environment variables (Replit Secrets) are set, and
  3. we're not under test (PYTEST_CURRENT_TEST or BITCOINSAGE_NO_NOTIFY set → never send).

Telegram:  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Email:     SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO, [SMTP_FROM]
Secret values are never logged or shown; errors are reported without them.
"""
from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from typing import Dict, List

SETTINGS_FILE = os.path.join("data", "notify_settings.json")
DEFAULTS = {"enabled": False, "telegram": True, "email": True}
TELEGRAM_VARS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
EMAIL_VARS = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO")


def load_settings(path: str = SETTINGS_FILE) -> dict:
    try:
        with open(path) as f:
            d = json.load(f)
        return {**DEFAULTS, **{k: bool(v) for k, v in d.items() if k in DEFAULTS}}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save_settings(settings: dict, path: str = SETTINGS_FILE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump({k: bool(settings.get(k, v)) for k, v in DEFAULTS.items()}, f, indent=1)


def configured(env=None) -> Dict[str, bool]:
    env = os.environ if env is None else env
    return {"telegram": all(env.get(v) for v in TELEGRAM_VARS),
            "email": all(env.get(v) for v in EMAIL_VARS)}


def sending_blocked(env=None) -> bool:
    env = os.environ if env is None else env
    return bool(env.get("PYTEST_CURRENT_TEST") or env.get("BITCOINSAGE_NO_NOTIFY"))


def channels_to_use(settings: dict, env=None) -> List[str]:
    if not settings.get("enabled") or sending_blocked(env):
        return []
    cfg = configured(env)
    return [c for c in ("telegram", "email") if settings.get(c) and cfg[c]]


def _send_telegram(text: str) -> None:
    import requests
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Telegram returned HTTP {r.status_code}")


def _send_email(subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ["SMTP_USER"]
    msg["To"] = os.environ["ALERT_EMAIL_TO"]
    msg.set_content(text)
    port = int(os.environ.get("SMTP_PORT") or 587)
    if port == 465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=15) as s:
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)
    else:
        with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=15) as s:
            s.starttls(); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)


def notify(subject: str, text: str, settings: dict = None) -> Dict[str, str]:
    """Send via every enabled+configured channel. Returns {channel: 'sent' | 'failed: <type>'}.
    Returns {} (sends nothing) when alerts are off, unconfigured, or under test."""
    settings = load_settings() if settings is None else settings
    out = {}
    for ch in channels_to_use(settings):
        try:
            _send_telegram(f"{subject}\n\n{text}") if ch == "telegram" else _send_email(subject, text)
            out[ch] = "sent"
        except Exception as e:  # never echo exception text: it can contain the URL with the bot token
            out[ch] = f"failed: {type(e).__name__}"
    return out
