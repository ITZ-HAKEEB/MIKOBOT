from __future__ import annotations

import time
import sys
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

BOT_START_TIME = datetime.utcnow()


def get_readable_uptime() -> str:
    delta = datetime.utcnow() - BOT_START_TIME
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    msg = await update.message.reply_text("🏓 <b>Pɪɴɢɪɴɢ...</b>", parse_mode="HTML")
    end = time.time()

    latency = round((end - start) * 1000, 2)
    uptime = get_readable_uptime()

    text = (
        "🏓 <b>Pᴏɴɢ!</b>\n\n"
        f"⚡ <b>Lᴀᴛᴇɴᴄʏ:</b> <code>{latency} ms</code>\n"
        f"⏳ <b>Uᴘᴛɪᴍᴇ:</b> <code>{uptime}</code>\n"
        f"🍃 <b>Dᴀᴛᴀʙᴀꜱᴇ:</b> <code>MongoDB + Redis Online</code>\n"
        f"🤖 <b>Pʏᴛʜᴏɴ:</b> <code>v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}</code>\n\n"
        "✨ <i>ᴍɪᴋᴏ ɪꜱ ꜱᴍᴏᴏᴛʜ ᴀɴᴅ ʀᴇᴀᴅʏ!</i>"
    )

    try:
        await msg.edit_text(text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(text, parse_mode="HTML")
