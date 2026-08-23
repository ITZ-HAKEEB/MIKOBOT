from __future__ import annotations

import json
import uuid
from typing import Optional, Dict, Any

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes

from modules.utils.db import get_redis_client, get_mongo_db

# Local fallback cache in case DB is unreachable
_WHISPERS_MEMORY: Dict[str, Dict[str, Any]] = {}


def save_whisper(whisper_id: str, data: Dict[str, Any]) -> None:
    _WHISPERS_MEMORY[whisper_id] = data
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.set(f"miko:whisper:{whisper_id}", json.dumps(data), ex=86400 * 7)
        except Exception:
            pass
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            mongo_db.whispers.update_one(
                {"_id": whisper_id},
                {"$set": data},
                upsert=True,
            )
        except Exception:
            pass


def get_whisper(whisper_id: str) -> Optional[Dict[str, Any]]:
    if whisper_id in _WHISPERS_MEMORY:
        return _WHISPERS_MEMORY[whisper_id]

    redis_client = get_redis_client()
    if redis_client:
        try:
            raw = redis_client.get(f"miko:whisper:{whisper_id}")
            if raw:
                data = json.loads(raw)
                _WHISPERS_MEMORY[whisper_id] = data
                return data
        except Exception:
            pass

    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            doc = mongo_db.whispers.find_one({"_id": whisper_id})
            if doc:
                doc.pop("_id", None)
                _WHISPERS_MEMORY[whisper_id] = doc
                return doc
        except Exception:
            pass

    return None


async def inline_whisper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    sender = update.inline_query.from_user

    # If query is empty or doesn't have target + message
    parts = query.split(maxsplit=1)
    if not query or len(parts) < 2:
        help_text = (
            "<b>🤫 ᴍɪᴋᴏ ᴡʜɪꜱᴘᴇʀ ꜱʏꜱᴛᴇᴍ</b>\n\n"
            "Just type:\n"
            "<code>@i_mikobot &lt;username/userid&gt; &lt;your whisper text&gt;</code>\n\n"
            "<i>Only you and the target user can open and view the secret whisper message!</i>"
        )
        results = [
            InlineQueryResultArticle(
                id="whisper_help",
                title="—Mɪᴋᴏ 亗 | 🤫 Send Whisper Message",
                description="Just type: @i_mikobot <username/userid> <your whisper text>",
                thumb_url="https://telegra.ph/file/0c9a75908b8b0e7747e92.jpg",
                input_message_content=InputTextMessageContent(help_text, parse_mode="HTML"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✨ Try Whisper", switch_inline_query_current_chat="")]
                ]),
            )
        ]
        await update.inline_query.answer(results, cache_time=1, is_personal=True)
        return

    raw_target, whisper_text = parts[0], parts[1]
    target = raw_target.lstrip("@").strip()

    target_id: Optional[int] = None
    target_username: Optional[str] = None

    if target.isdigit():
        target_id = int(target)
        target_disp = f"ID: {target_id}"
    else:
        target_username = target.lower()
        target_disp = f"@{target}"

    whisper_id = str(uuid.uuid4())[:8]

    whisper_data = {
        "sender_id": sender.id,
        "sender_name": sender.first_name,
        "sender_username": sender.username.lower() if sender.username else None,
        "target_id": target_id,
        "target_username": target_username,
        "target_disp": target_disp,
        "text": whisper_text,
    }

    save_whisper(whisper_id, whisper_data)

    msg_text = (
        f"🔒 <b>A secret whisper message for {target_disp}!</b>\n"
        f"<i>Only {target_disp} and {sender.first_name} can open this.</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Show Whisper", callback_data=f"wspr_{whisper_id}")]
    ])

    results = [
        InlineQueryResultArticle(
            id=whisper_id,
            title=f"🤫 Send Whisper to {target_disp}",
            description=f"Message: {whisper_text[:40]}{'...' if len(whisper_text) > 40 else ''}",
            thumb_url="https://telegra.ph/file/0c9a75908b8b0e7747e92.jpg",
            input_message_content=InputTextMessageContent(msg_text, parse_mode="HTML"),
            reply_markup=kb,
        )
    ]

    await update.inline_query.answer(results, cache_time=1, is_personal=True)


async def whisper_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("wspr_"):
        return False

    whisper_id = data.split("wspr_", 1)[1]
    w_data = get_whisper(whisper_id)

    if not w_data:
        await query.answer("⚠️ This whisper has expired or does not exist!", show_alert=True)
        return True

    user = query.from_user
    user_id = user.id
    user_uname = user.username.lower() if user.username else None

    # Check permission: Is user the sender or target?
    is_sender = user_id == w_data.get("sender_id")
    is_target_id = w_data.get("target_id") and user_id == w_data["target_id"]
    is_target_uname = w_data.get("target_username") and user_uname == w_data["target_username"]

    if is_sender or is_target_id or is_target_uname:
        await query.answer(f"🤫 Secret Whisper:\n\n{w_data['text']}", show_alert=True)
    else:
        await query.answer("❌ This whisper is not for you!", show_alert=True)

    return True
