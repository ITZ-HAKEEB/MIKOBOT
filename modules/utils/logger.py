from __future__ import annotations

import os
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

LOG_GROUP_ID = os.getenv("LOG_GROUP_ID", "-1005397585622")


def get_log_group_id() -> Optional[int]:
    try:
        return int(LOG_GROUP_ID)
    except (ValueError, TypeError):
        return None


async def send_log_message(bot: Bot, text: str, parse_mode: str = "HTML"):
    log_id = get_log_group_id()
    if not log_id:
        return
    try:
        await bot.send_message(chat_id=log_id, text=text, parse_mode=parse_mode)
    except TelegramError as e:
        print(f"⚠️ Log channel send failed: {e}")
    except Exception as e:
        print(f"⚠️ Log channel unexpected error: {e}")
