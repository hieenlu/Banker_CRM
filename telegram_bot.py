from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from telegram import Bot


@dataclass(frozen=True)
class TelegramConfig:
    token: str
    chat_id: str


def load_telegram_config_from_env() -> TelegramConfig | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None
    return TelegramConfig(token=token, chat_id=chat_id)


def _run_coroutine_safely(coro):
    """
    Streamlit can run inside an environment with an active event loop; this
    wrapper avoids "event loop is running" issues by using a fresh loop.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def send_telegram_message(config: TelegramConfig, text: str) -> None:
    async def _send():
        bot = Bot(token=config.token)
        await bot.send_message(chat_id=config.chat_id, text=text, disable_web_page_preview=True)

    _run_coroutine_safely(_send())

