from __future__ import annotations

import os
import io
import re
import random
import base64
import html as html_lib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from gtts import gTTS
from deep_translator import GoogleTranslator
import sympy
import html2image
from telegram import Update, User, ChatMemberAdministrator, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

_hti = None
try:
    _hti = html2image.Html2Image(
        custom_flags=[
            '--no-sandbox',
            '--disable-gpu',
            '--default-background-color=00000000',
            '--hide-scrollbars',
            '--force-device-scale-factor=3.0',
        ]
    )
    _hti.output_path = '/tmp'
except Exception:
    _hti = None

from modules.social.ping import ping_cmd
from modules.ai.translator import ai_translate
from modules.utils.storage import (
    get_user,
    update_user,
    add_xp,
    get_group,
    update_group,
    get_all_users,
)


def _cs(cmd, desc=""):
    return f"⏳ <b>/{cmd}</b> — ᴄᴏᴍɪɴɢ ꜱᴏᴏɴ!\n<i>{desc}</i>"


def _reply_user(update: Update) -> Optional[User]:
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        return update.message.reply_to_message.from_user
    return None


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return False
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        return any(m.user.id == user_id for m in admins)
    except Exception:
        return False


SOCIAL_ACTIONS = {
    "crush": ("💘", "{a} ʜᴀꜱ ᴀ ᴄʀᴜꜱʜ ᴏɴ {t}! 💕"),
    "love": ("❤️", "{a} ꜱᴇɴᴛ ʟᴏᴠᴇ ᴛᴏ {t}! ❤️‍🔥"),
    "look": ("👀", "{a} ɪꜱ ʟᴏᴏᴋɪɴɢ ᴀᴛ {t}..."),
    "brain": ("🧠", "{a} ɢᴀᴠᴇ {t} ᴀ ʙʀᴀɪɴʏ ᴠɪʙᴇ ᴄʜᴇᴄᴋ (+5 XP!)"),
    "murder": ("🔪", "{a} ᴍᴜʀᴅᴇʀᴇᴅ {t} ɪɴ ᴄᴏʟᴅ ʙʟᴏᴏᴅ! 💀"),
    "slap": ("🖐️", "{a} ꜱʟᴀᴘᴘᴇᴅ {t} ʜᴀʀᴅ! 🫢"),
    "punch": ("👊", "{a} ᴘᴜɴᴄʜᴇᴅ {t}! 💢"),
    "bite": ("🦷", "{a} ʙɪᴛ {t}! 😬"),
    "kiss": ("💋", "{a} ᴋɪꜱꜱᴇᴅ {t}! 💞"),
    "hug": ("🤗", "{a} ɢᴀᴠᴇ {t} ᴀ ʙɪɢ ʜᴜɢ! 🌸"),
}


def _make_social_handler(action_key: str):
    emoji, template = SOCIAL_ACTIONS[action_key]

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        author = update.effective_user
        target = _reply_user(update)
        if not target or target.id == author.id:
            await update.message.reply_text(f"{emoji} ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ ᴛᴏ ᴜꜱᴇ /{action_key}!")
            return
        a_name = author.first_name or author.username or "Someone"
        t_name = target.first_name or target.username or "Someone"
        await update.message.reply_text(f"{emoji} {template.format(a=a_name, t=t_name)}")
        if action_key in ("crush", "love", "kiss", "hug"):
            get_user(author.id, author.username or a_name, author.first_name)
            add_xp(author.id, 3)

    return handler


async def cmd_hug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    add_xp(author.id, 3)

    msg = f"{a_mention} Sᴇɴᴛ A Hᴜɢ Tᴏ {t_mention} 🤗"
    photo_url = "https://cdn.imageurlgenerator.com/uploads/856e0adb-1891-441e-ae03-1987d6befbf6.jpg"
    try:
        await update.message.reply_photo(
            photo=photo_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_punch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    add_xp(author.id, 3)

    msg = f"{a_mention} punched {t_mention} really hard 👊"
    gif_url = "https://cdn.imageurlgenerator.com/uploads/ea21c85b-ef61-4bb7-9e5e-7a4fd56a31a4.gif"
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_bite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    add_xp(author.id, 3)

    msg = f"{a_mention} Gᴀᴠᴇ A  Nᴏᴛᴛʏ Bɪᴛᴇ ᴛᴏ {t_mention} 😁"
    gif_url = "https://cdn.imageurlgenerator.com/uploads/a9bdb1fc-478d-4cb8-b6c9-8f1035f8a30c.gif"
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_slap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    add_xp(author.id, 3)

    msg = f"{a_mention} slapped {t_mention} 👋"
    gif_url = "https://cdn.imageurlgenerator.com/uploads/f465dd78-b150-4a69-ac18-5c3dfd8f9553.gif"
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_murder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("🔪 Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Tᴏ Mᴜʀᴅᴇʀ Tʜᴇᴍ!")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    add_xp(author.id, 3)

    msg = f"{a_mention} Bʀᴜᴛᴀʟʟʏ Mᴜʀᴅᴇʀᴇᴅ {t_mention} 🔪🩸"
    gif_url = "https://cdn.imageurlgenerator.com/uploads/95137995-12aa-45fa-9493-5c41f4cff986.gif"
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_crush(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    pct = random.randint(30, 100)
    add_xp(author.id, 3)

    msg = (
        f"💘 {t_mention}'ꜱ Sᴇᴄʀᴇᴛ Cʀᴜꜱʜ Iꜱ {a_mention}\n"
        f"Crush level: {pct}% ❤️"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_brain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    pct = random.randint(5, 100)
    emoji = "😎" if pct >= 60 else ("🧠" if pct >= 30 else "🤪")

    msg = f"IQ Lᴇᴠᴇʟ Oꜰ {t_mention} Iꜱ {pct}% {emoji}"
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_kiss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    add_xp(author.id, 3)

    msg = f"{a_mention} Gᴀᴠᴇ A Sᴡᴇᴇᴛ Kɪꜱꜱ Tᴏ {t_mention} 😘💋"
    gif_url = "https://www.image2url.com/r2/default/gifs/1787438796218-88146e12-1516-4f03-a50f-d06fa5160b09.gif"
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_love(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return
    
    author = update.effective_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))
    
    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or author.username or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"
    
    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'
    
    pct = random.randint(10, 100)
    
    msg = (
        "❤️ Lᴏᴠᴇ Mᴇᴛᴇʀ Rᴇᴘᴏʀᴛ ❤️\n"
        f"{a_mention} ❤️ {t_mention}\n"
        f"Lᴏᴠᴇ Cᴏᴍᴘᴀᴛɪʙɪʟɪᴛʏ: {pct}% ❤️"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_look(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    ud = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))
    t_name = ud.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"
    
    pct = random.randint(35, 100)
    emoji = "😍" if pct >= 60 else ("✨" if pct >= 50 else "😉")
    
    mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'
    msg = f"{mention}'S Lᴏᴏᴋ Rᴀᴛɪɴɢ Iꜱ: {pct}% {emoji}"
    await update.message.reply_text(msg, parse_mode="HTML")


async def stupid_meter(update, context):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ.")
        return

    ud = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))
    t_name = ud.get("display_name") or getattr(target, "full_name", None) or target.first_name or target.username or "User"
    mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'
    pct = random.randint(10, 100)

    msg = (
        "Sᴛᴜᴘɪᴅ Mᴇᴛᴇʀ Sᴄᴀɴɴɪɴɢ… 🔍\n"
        f"Rᴇꜱᴜʟᴛ Fᴏʀ {mention}: {pct}% 😵💫 Sᴛᴜᴘɪᴅ Dᴇᴛᴇᴄᴛᴇᴅ"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


COUPLE_COOLDOWNS: Dict[int, datetime] = {}
GROUP_ACTIVE_MEMBERS: Dict[int, Dict[int, str]] = {}


async def couples(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("💞 This command works best in groups!")
        return

    now = datetime.now()
    last_time = COUPLE_COOLDOWNS.get(chat.id)
    if last_time and (now - last_time) < timedelta(minutes=5):
        await update.message.reply_text(
            "⏳ A CᴏᴜᴘʟE Hᴀꜱ Bᴇᴇɴ Dᴇᴄʟᴀʀᴇᴅ Rᴇᴄᴇɴᴛʟʏ.\n"
            "⏰ Tʀʏ Aꜰᴛᴇʀ 5 Mɪɴꜱ"
        )
        return

    author = update.effective_user
    replied = _reply_user(update)

    from modules.utils.storage import get_all_users
    all_users = get_all_users()

    if chat.id not in GROUP_ACTIVE_MEMBERS:
        GROUP_ACTIVE_MEMBERS[chat.id] = {}

    # Register author in group active list
    ud_a = all_users.get(str(author.id), {})
    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or "User"
    GROUP_ACTIVE_MEMBERS[chat.id][author.id] = a_name

    if replied and replied.id != author.id:
        u1_id = author.id
        u2_id = replied.id
        ud_r = all_users.get(str(u2_id), {})
        u1_name = a_name
        u2_name = ud_r.get("display_name") or getattr(replied, "full_name", None) or replied.first_name or "User"
        GROUP_ACTIVE_MEMBERS[chat.id][u2_id] = u2_name
    else:
        group_members = GROUP_ACTIVE_MEMBERS[chat.id]
        if len(group_members) >= 2:
            chosen_ids = random.sample(list(group_members.keys()), 2)
            u1_id = chosen_ids[0]
            u2_id = chosen_ids[1]
            u1_name = group_members[u1_id]
            u2_name = group_members[u2_id]
        else:
            # Need more group members
            await update.message.reply_text(
                "💞 Need at least 2 active group members to pick a couple!\n"
                "Tip: reply to someone with /couples or chat in the group first."
            )
            return

    COUPLE_COOLDOWNS[chat.id] = now

    m1 = f'<a href="tg://user?id={u1_id}">{html_lib.escape(u1_name)}</a>'
    m2 = f'<a href="tg://user?id={u2_id}">{html_lib.escape(u2_name)}</a>'

    msg = (
        "❤️ <b>Tᴏᴅᴀʏꜱ Cᴜᴛᴇ Cᴏᴜᴘʟᴇ</b> ❤️\n\n"
        f"{m1} 💞 {m2}\n\n"
        "Lᴏᴠᴇ Iꜱ Iɴ Tʜᴇ Aɪʀ ❤️\n\n"
        "~ Fʀᴏᴍ ᴍɪᴋᴏ Wɪᴛʜ Lᴏᴠᴇ 💋"
    )
    photo_url = "https://i.ibb.co/KcTmzLDJ/When-Two-Hearts-Talk-The-World-Goes-Quiet.jpg"
    try:
        await update.message.reply_photo(
            photo=photo_url,
            caption=msg,
            parse_mode="HTML",
        )
    except Exception:
        await update.message.reply_text(msg, parse_mode="HTML")


def _friends_for(user_id: int) -> Dict[str, List[int]]:
    ud = get_user(user_id)
    friends = ud.get("friends") or {}
    if not isinstance(friends, dict):
        friends = {}
    return {str(k): (v if isinstance(v, list) else []) for k, v in friends.items()}


def _save_friends(user_id: int, friends: Dict[str, List[int]]):
    update_user(user_id, friends={k: list(v) for k, v in friends.items()})


def _friend_name(friend_id: int) -> str:
    from modules.utils.storage import get_all_users
    data = get_all_users()
    info = data.get(str(friend_id)) or {}
    return (
        info.get("display_name")
        or info.get("username")
        or f"User {friend_id}"
    )


async def friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🧸 <b>Fʀɪᴇɴᴅꜱʜɪᴘ Cᴏᴍᴍᴀɴᴅꜱ</b>\n\n"
        "• <code>/addf &lt;tag_name&gt;</code> - Add friend (in reply)\n"
        "• <code>/tag &lt;tag/all&gt;</code> - Tag your friend\n"
        "• <code>/t &lt;tag/all&gt;</code> - Tag your friend\n"
        "• <code>/ctag &lt;old&gt; &lt;new&gt;</code> - Change tag of your friend\n"
        "• <code>/delf &lt;tag&gt;</code> - Delete a friend\n"
        "• <code>/allf</code> - All friend's list\n"
        "• <code>/friend</code> - Show friends count\n"
        "• <code>/friends</code> - Show all friendship commands\n\n"
        "<b>💡 Benefits:</b>\n"
        "Now you can easily tag your friends in any group by typing <code>/tag jinu</code> - this will tag your friend in that particular group!"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def addf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    target = _reply_user(update)
    args = context.args or []
    tag = (args[0].strip() if args else "").lstrip("#").lower()
    if not target or target.id == user.id:
        await update.message.reply_text("📌 Rᴇᴘʟʏ Tᴏ A Uꜱᴇʀ Tᴏ Aᴅᴅ A Fʀɪᴇɴᴅ: /addf <tag>")
        return
    if not tag:
        await update.message.reply_text("📌 Pʀᴏᴠɪᴅᴇ A Tᴀɢ: /addf <tag> (e.g. /addf bestie)")
        return
    get_user(user.id, user.username or user.first_name or "User", user.first_name)
    get_user(
        target.id,
        getattr(target, "username", None) or (target.first_name or "User"),
        target.first_name,
    )
    friends = _friends_for(user.id)
    friends.setdefault(tag, [])
    if target.id in friends[tag]:
        await update.message.reply_text(
            f"📌 {target.first_name or target.username or 'User'} is already in #{tag}."
        )
        return
    friends[tag].append(target.id)
    _save_friends(user.id, friends)
    await update.message.reply_text(
        f"✅ Added <b>{target.first_name or target.username or 'User'}</b> to your #{tag} friends!",
        parse_mode="HTML",
    )


async def tag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    if not args:
        await update.message.reply_text("❗️ Usᴀɢᴇ: /tag <tag_name|all> [message]")
        return
    tag_arg = (args[0].strip() if args else "").lstrip("#").lower()
    if not tag_arg:
        await update.message.reply_text("❗️ Usᴀɢᴇ: /tag <tag_name|all> [message]")
        return
    friends = _friends_for(user.id)
    ids: List[int] = []
    if tag_arg == "all":
        for ids_list in friends.values():
            for fid in ids_list:
                if fid not in ids:
                    ids.append(fid)
        if not ids:
            await update.message.reply_text("❗️ Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ғʀɪᴇɴᴅs ʏᴇᴛ.")
            return
    elif tag_arg in friends:
        ids = list(friends[tag_arg])
    else:
        await update.message.reply_text(f"📌 You have no friends tagged #{tag_arg}.")
        return
    if not ids:
        await update.message.reply_text("❗️ Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ғʀɪᴇɴᴅs ʏᴇᴛ.")
        return
    mention_limit = 20
    chunks = [ids[i:i+mention_limit] for i in range(0, len(ids), mention_limit)]
    for chunk in chunks:
        parts = []
        for fid in chunk:
            name = _friend_name(fid)
            parts.append(f"[{name}](tg://user?id={fid})")
        header = f"📢 Tagging {'#all' if tag_arg == 'all' else '#'+tag_arg} ({len(chunk)}):"
        await update.message.reply_text(
            header + "\n" + " • ".join(parts),
            parse_mode="Markdown",
        )


async def ctag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("📌 USAGE: /ctag <old_tag> <new_tag>")
        return
    old_tag = args[0].strip().lstrip("#").lower()
    new_tag = args[1].strip().lstrip("#").lower()
    if not old_tag or not new_tag:
        await update.message.reply_text("📌 USAGE: /ctag <old_tag> <new_tag>")
        return
    friends = _friends_for(user.id)
    if old_tag not in friends:
        await update.message.reply_text(f"📌 Tag #{old_tag} doesn't exist.")
        return
    if old_tag == new_tag:
        await update.message.reply_text("📌 Old and new tag are the same.")
        return
    old_ids = list(friends[old_tag])
    if new_tag in friends:
        for fid in old_ids:
            if fid not in friends[new_tag]:
                friends[new_tag].append(fid)
    else:
        friends[new_tag] = list(old_ids)
    del friends[old_tag]
    _save_friends(user.id, friends)
    await update.message.reply_text(
        f"✅ Renamed #{old_tag} → #{new_tag} ({len(old_ids)} friends moved)."
    )


async def delf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    arg = (args[0].strip() if args else "").lstrip("#").lower()
    if not arg:
        await update.message.reply_text("📌 USAGE: /delf <tag> (reply to remove that user) OR /delf all")
        return
    friends = _friends_for(user.id)
    target = _reply_user(update)
    if arg == "all":
        total = sum(len(v) for v in friends.values())
        _save_friends(user.id, {})
        await update.message.reply_text(f"✅ Deleted all {total} friend entries.")
        return
    if arg not in friends:
        await update.message.reply_text(f"📌 Tag #{arg} doesn't exist.")
        return
    if target:
        if target.id not in friends[arg]:
            await update.message.reply_text(
                f"📌 {target.first_name or target.username or 'User'} is not in #{arg}."
            )
            return
        friends[arg] = [fid for fid in friends[arg] if fid != target.id]
        if not friends[arg]:
            del friends[arg]
        _save_friends(user.id, friends)
        await update.message.reply_text(
            f"✅ Removed <b>{target.first_name or target.username or 'User'}</b> from #{arg}.",
            parse_mode="HTML",
        )
        return
    removed_count = len(friends[arg])
    del friends[arg]
    _save_friends(user.id, friends)
    await update.message.reply_text(f"✅ Deleted tag #{arg} ({removed_count} friends removed).")


async def allf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    friends = _friends_for(user.id)
    if not friends:
        await update.message.reply_text(
            "👥 You have no friends yet. Reply to someone: <code>/addf bestie</code>",
            parse_mode="HTML",
        )
        return
    total = sum(len(v) for v in friends.values())
    lines = [f"👥 <b>Your Friends</b>  (total {total})\n"]
    for tag, ids in friends.items():
        names = ", ".join(_friend_name(fid) for fid in ids) or "(empty)"
        lines.append(f"  #{tag} ({len(ids)}): {names}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    friends = _friends_for(user.id)
    total = sum(len(v) for v in friends.values())
    uniq = {fid for ids in friends.values() for fid in ids}
    await update.message.reply_text(
        f"👥 You have <b>{len(uniq)}</b> unique friend(s) across <b>{len(friends)}</b> tag(s) (total entries: {total}).",
        parse_mode="HTML",
    )


GIFT_CATALOG: Dict[str, Dict[str, Any]] = {
    "rose": {"name": "🌹 Rᴏꜱᴇ", "price": 500},
    "chocolate": {"name": "🍫 Cʜᴏᴄᴏʟᴀᴛᴇ", "price": 800},
    "ring": {"name": "💍 Ring", "price": 2000},
    "teddy": {"name": "🧸 Tᴇᴅᴅʏ Bᴇᴀʀ", "price": 1500},
    "teddy bear": {"name": "🧸 Tᴇᴅᴅʏ Bᴇᴀʀ", "price": 1500},
    "pizza": {"name": "🍕 Pizza", "price": 600},
    "surprise box": {"name": "🎁 Sᴜʀᴘʀɪꜱᴇ Bᴏx", "price": 2500},
    "box": {"name": "🎁 Sᴜʀᴘʀɪꜱᴇ Bᴏx", "price": 2500},
    "puppy": {"name": "🐶 Puppy", "price": 3000},
    "cake": {"name": "🎂 Cake", "price": 1000},
    "love letter": {"name": "💌 Lᴏᴠᴇ Lᴇᴛᴛᴇʀ", "price": 400},
    "letter": {"name": "💌 Lᴏᴠᴇ Lᴇᴛᴛᴇʀ", "price": 400},
    "cat": {"name": "🐱 Cᴀᴛ", "price": 2500},
    "tulip": {"name": "🌷 Tᴜʟɪᴘ", "price": 1500},
    "girl friend": {"name": "👠 Gɪʀʟ Fʀɪᴇɴᴅ", "price": 1000},
    "girlfriend": {"name": "👠 Gɪʀʟ Fʀɪᴇɴᴅ", "price": 1000},
    "boy friend": {"name": "👦 Bᴏʏ Fʀɪᴇɴᴅ", "price": 1000},
    "boyfriend": {"name": "👦 Bᴏʏ Fʀɪᴇɴᴅ", "price": 1000},
    "bmw": {"name": "🏎 Bᴍᴡ", "price": 5000},
    "car": {"name": "🏎 Bᴍᴡ", "price": 5000},
}


async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = _reply_user(update)
    if not target:
        await update.message.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ Tʜᴇ Uꜱᴇʀ Yᴏᴜ Wᴀɴᴛ Tᴏ Gɪꜰᴛ.")
        return

    author = update.effective_user
    args = context.args or []
    if not args:
        await update.message.reply_text("🎁 Uꜱᴀɢᴇ: /gift <ɪᴛᴇᴍ_ɴᴀᴍᴇ>")
        return

    raw_item = " ".join(args).strip().lower()
    gift_info = GIFT_CATALOG.get(raw_item)
    if gift_info:
        item_name = gift_info["name"]
        price = gift_info["price"]
    else:
        item_name = f"🎁 {' '.join(args).strip()}"
        price = 500

    from modules.utils.storage import get_user, update_user
    ud_a = get_user(author.id, getattr(author, "username", "User"), getattr(author, "first_name", "User"))
    ud_t = get_user(target.id, getattr(target, "username", "User"), getattr(target, "first_name", "User"))

    if ud_a.get("balance", 0) < price:
        await update.message.reply_text(f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nRequired: ${price} | You have: ${ud_a.get('balance', 0)}")
        return

    update_user(author.id, balance=ud_a.get("balance", 0) - price)
    t_items = dict(ud_t.get("items") or {})
    t_items[item_name] = t_items.get(item_name, 0) + 1
    update_user(target.id, items=t_items)

    a_name = ud_a.get("display_name") or getattr(author, "full_name", None) or author.first_name or "User"
    t_name = ud_t.get("display_name") or getattr(target, "full_name", None) or target.first_name or "User"

    a_mention = f'<a href="tg://user?id={author.id}">{html_lib.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(t_name)}</a>'

    text = (
        f"{a_mention} Gɪꜰᴛᴇᴅ {item_name} Tᴏ {t_mention} 🥰\n"
        f"Dᴇᴅᴜᴄᴛᴇᴅ : -${price}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


SMALL_CAPS_MAP: Dict[str, str] = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ',
    'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
    'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
    's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ',
    'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ',
    'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ',
    'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x',
    'Y': 'ʏ', 'Z': 'ᴢ',
}

def to_small_caps(text: str) -> str:
    return "".join(SMALL_CAPS_MAP.get(c, c) for c in text)

COLOR_PRESETS: Dict[str, tuple[str, str, str]] = {
    "red": ("#FF0000", "#000000", "#FFFFFF"),
    "blue": ("#0984E3", "#FFFFFF", "#DFF9FB"),
    "green": ("#00B894", "#FFFFFF", "#E8F8F5"),
    "yellow": ("#F1C40F", "#000000", "#5B4100"),
    "pink": ("#FD79A8", "#FFFFFF", "#FFF0F5"),
    "purple": ("#6C5CE7", "#FFFFFF", "#F1F2F6"),
    "orange": ("#FA8231", "#FFFFFF", "#FFF3CD"),
    "black": ("#000000", "#FFFFFF", "#FF79C6"),
    "white": ("#FFFFFF", "#000000", "#E84393"),
    "cyan": ("#00CEC9", "#000000", "#004E4D"),
    "dark": ("#181226", "#FFFFFF", "#FF79C6"),
    "lime": ("#2ECC71", "#000000", "#0B5345"),
    "teal": ("#009688", "#FFFFFF", "#E0F2F1"),
    "gold": ("#F39C12", "#000000", "#4E342E"),
    "rose": ("#E84393", "#FFFFFF", "#FCE4EC"),
    "grey": ("#636E72", "#FFFFFF", "#DFE6E9"),
    "gray": ("#636E72", "#FFFFFF", "#DFE6E9"),
}


def generate_quote_sticker(
    text: str,
    author_name: str,
    avatar_bytes: Optional[bytes] = None,
    bg_color: str = "#181226",
    text_color: str = "#FFFFFF",
    author_color: str = "#FF79C6",
    font_style: str = "normal",
) -> io.BytesIO:
    def hex_to_rgb(hex_str: str, default=(24, 18, 38, 255)):
        try:
            h = str(hex_str).lstrip("#")
            if len(h) == 3:
                h = "".join([c * 2 for c in h])
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (r, g, b, 255)
        except Exception:
            return default

    # Load high-definition bold fonts
    font_bold_path = "assets/fonts/Roboto-Bold.ttf"
    font_dev_path = "assets/fonts/NotoSansDevanagari-Bold.ttf"

    is_hindi = any("\u0900" <= ch <= "\u097f" for ch in (text + author_name))
    font_file = font_dev_path if (is_hindi and os.path.exists(font_dev_path)) else font_bold_path

    if not os.path.exists(font_file):
        font_file = font_bold_path if os.path.exists(font_bold_path) else None

    if font_file:
        font_name = ImageFont.truetype(font_file, 36)
        font_text = ImageFont.truetype(font_file, 42)
    else:
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()

    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    # Process newlines and word wrapping
    raw_lines = text.split("\n")
    lines = []
    max_line_width = 540

    for r_line in raw_lines:
        words = r_line.split()
        if not words:
            lines.append("")
            continue
        curr = ""
        for w in words:
            test = curr + (" " if curr else "") + w
            bbox = dummy_draw.textbbox((0, 0), test, font=font_text)
            if (bbox[2] - bbox[0]) > max_line_width and curr:
                lines.append(curr)
                curr = w
            else:
                curr = test
        if curr:
            lines.append(curr)

    if not lines:
        lines = [text if text else "(empty)"]

    name_bbox = dummy_draw.textbbox((0, 0), author_name, font=font_name)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = name_bbox[3] - name_bbox[1]

    line_h = 52
    text_total_h = len(lines) * line_h

    content_w = name_w
    for l in lines:
        b = dummy_draw.textbbox((0, 0), l, font=font_text)
        content_w = max(content_w, b[2] - b[0])

    pad_left = 32
    pad_right = 84
    pad_top = 24
    pad_bottom = 32

    bubble_w = max(int(content_w + pad_left + pad_right), 310)
    bubble_h = int(name_h + 18 + text_total_h + pad_top + pad_bottom)

    avatar_size = 96
    total_w = avatar_size + 18 + bubble_w + 20
    total_h = max(avatar_size + 20, bubble_h + 20)

    img = Image.new("RGBA", (int(total_w), int(total_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_rgb = hex_to_rgb(bg_color, (24, 18, 38, 255))
    text_rgb = hex_to_rgb(text_color, (255, 255, 255, 255))
    author_rgb = hex_to_rgb(author_color, (255, 121, 198, 255))

    av_x = 10
    av_y = total_h - avatar_size - 10

    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            av = av.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
            img.paste(av, (av_x, av_y), mask)
        except Exception:
            draw.ellipse([(av_x, av_y), (av_x + avatar_size, av_y + avatar_size)], fill=(255, 105, 180, 255))
    else:
        draw.ellipse([(av_x, av_y), (av_x + avatar_size, av_y + avatar_size)], fill=(255, 105, 180, 255))
        init_letter = (author_name[:1] if author_name else "U").upper()
        init_bbox = dummy_draw.textbbox((0, 0), init_letter, font=font_name)
        iw = init_bbox[2] - init_bbox[0]
        ih = init_bbox[3] - init_bbox[1]
        draw.text(
            (av_x + (avatar_size - iw) // 2, av_y + (avatar_size - ih) // 2 - 4),
            init_letter,
            fill=(255, 255, 255, 255),
            font=font_name,
        )

    bx = av_x + avatar_size + 14
    by = total_h - bubble_h - 10
    draw.rounded_rectangle([(bx, by), (bx + bubble_w, by + bubble_h)], radius=24, fill=bg_rgb)

    # Sleek dialogue tail pointing towards the avatar
    tail = [
        (bx + 4, by + bubble_h - 26),
        (bx - 12, by + bubble_h - 6),
        (bx + 20, by + bubble_h),
    ]
    draw.polygon(tail, fill=bg_rgb)

    draw.text((bx + pad_left, by + pad_top), author_name, fill=author_rgb, font=font_name)

    cur_y = by + pad_top + name_h + 16
    for l in lines:
        draw.text((bx + pad_left, cur_y), l, fill=text_rgb, font=font_text)
        cur_y += line_h

    max_dim = max(img.size)
    if max_dim != 512:
        ratio = 512.0 / max_dim
        new_size = (max(1, int(img.size[0] * ratio)), max(1, int(img.size[1] * ratio)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    img = ImageEnhance.Sharpness(img).enhance(1.3)

    buf = io.BytesIO()
    buf.name = "quote.webp"
    img.save(buf, format="WEBP", quality=100, method=6)
    buf.seek(0)
    return buf


async def q_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    replied = update.message.reply_to_message
    if not replied:
        await update.message.reply_text("💬 Reply to a message to quote it into a sticker: /q")
        return
    
    target_user = replied.from_user or update.effective_user
    author_name = getattr(target_user, "full_name", None) or target_user.first_name or target_user.username or "User"
    text = replied.text or replied.caption or (
        "[Sticker]" if replied.sticker else (
            "[Photo]" if replied.photo else (
                "[Animation]" if replied.animation else (
                    "[Voice]" if replied.voice else "[Media]"
                )
            )
        )
    )

    avatar_bytes = None
    try:
        photos = await context.bot.get_user_profile_photos(target_user.id, limit=1)
        if photos.total_count > 0:
            photo_file = photos.photos[0][-1]
            file_obj = await context.bot.get_file(photo_file.file_id)
            av_buf = io.BytesIO()
            await file_obj.download_to_memory(av_buf)
            avatar_bytes = av_buf.getvalue()
    except Exception:
        pass

    bg_color = "#181226"
    text_color = "#FFFFFF"
    author_color = "#FF79C6"
    font_style = "normal"

    args = [a.lower().strip() for a in (context.args or [])]
    for a in args:
        if a in COLOR_PRESETS:
            bg_color, text_color, author_color = COLOR_PRESETS[a]
        elif a.startswith("#") and len(a) in (4, 7):
            bg_color = a
            try:
                h = a.lstrip("#")
                if len(h) == 3:
                    h = "".join([c * 2 for c in h])
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                text_color = "#000000" if lum > 140 else "#FFFFFF"
                author_color = "#FFFFFF" if lum <= 140 else "#550055"
            except Exception:
                pass
        elif a in ("smallcaps", "sc"):
            text = to_small_caps(text)
        elif a in ("mono", "code", "italic", "cursive", "serif"):
            font_style = a

    sticker_buf = generate_quote_sticker(
        text,
        author_name,
        avatar_bytes,
        bg_color=bg_color,
        text_color=text_color,
        author_color=author_color,
        font_style=font_style,
    )
    await update.message.reply_sticker(sticker=sticker_buf)


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    text = " ".join(args).strip() if args else None
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text or update.message.reply_to_message.caption
    if not text:
        await update.message.reply_text(
            "🎙️ <b>Vᴏɪᴄᴇ Cᴏᴍᴍᴀɴᴅ</b>\n\n"
            "👉 <b>Usage:</b> <code>/voice &lt;your text&gt;</code>\n"
            "👉 Or reply to any message with <code>/voice</code>",
            parse_mode="HTML",
        )
        return

    # Clean text for smoother voice synthesis
    clean_text = re.sub(r"http\S+|www\S+|@\w+|#\w+", "", text).strip()
    if not clean_text:
        clean_text = text[:300]

    try:
        is_hindi = any("\u0900" <= ch <= "\u097f" for ch in clean_text)
        lang = "hi" if is_hindi else "en"
        tld = "co.in" if is_hindi else "com"

        buf = io.BytesIO()
        tts = gTTS(text=clean_text[:500], lang=lang, tld=tld)
        tts.write_to_fp(buf)
        buf.seek(0)

        preview = (clean_text[:50] + "...") if len(clean_text) > 50 else clean_text
        caption = f"🎙️ <b>Vᴏɪᴄᴇ Gᴇɴᴇʀᴀᴛᴇᴅ Bʏ Mɪᴋᴏ</b>\n<i>\"{html_lib.escape(preview)}\"</i>"
        await update.message.reply_voice(voice=buf, caption=caption, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating voice: {e}")


async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    raw = " ".join(args).strip() if args else None
    if not raw and update.message.reply_to_message and update.message.reply_to_message.text:
        raw = update.message.reply_to_message.text.strip()
        
    if not raw:
        await update.message.reply_text(
            "🧮 <b>ᴍᴀᴛʜ ᴄᴀʟᴄᴜʟᴀᴛᴏʀ</b>\n\n"
            "Examples:\n"
            "• <code>/calc 20+10</code>\n"
            "• <code>/calc 10*10</code>\n"
            "• <code>/calc 200/10</code>\n"
            "• <code>/calc 200-10</code>\n"
            "• <code>/calc 1000 ka 30% kitna hota</code>\n"
            "• <code>/c 2^8</code>",
            parse_mode="HTML",
        )
        return

    cleaned = raw.lower().strip()
    
    # 1) Natural language percentages
    m = re.search(r'([0-9\.]+)\s*(?:ka|of)\s*([0-9\.]+)\s*%', cleaned)
    if m:
        val, pct = float(m.group(1)), float(m.group(2))
        res_str = f"{(val * pct) / 100.0:g}"
        await update.message.reply_text(f"🧮 <b>Calculation:</b> <code>{raw}</code>\n<b>Result:</b> <code>{res_str}</code>", parse_mode="HTML")
        return

    m2 = re.search(r'([0-9\.]+)\s*%\s*(?:of|ka)\s*([0-9\.]+)', cleaned)
    if m2:
        pct, val = float(m2.group(1)), float(m2.group(2))
        res_str = f"{(val * pct) / 100.0:g}"
        await update.message.reply_text(f"🧮 <b>Calculation:</b> <code>{raw}</code>\n<b>Result:</b> <code>{res_str}</code>", parse_mode="HTML")
        return

    expr = re.sub(r'(kitna\s*hota\s*(?:hai)?|\?|=|equals|what\s*is)', '', cleaned).strip()
    expr = expr.replace('^', '**').replace('x', '*').replace('÷', '/')

    allowed_chars = set('0123456789+-*/().% ')
    if all(c in allowed_chars for c in expr):
        try:
            eval_expr = re.sub(r'([0-9\.]+)%', r'(\1/100)', expr)
            res = eval(eval_expr, {'__builtins__': None}, {})
            await update.message.reply_text(f"🧮 <b>Calculation:</b> <code>{raw}</code>\n<b>Result:</b> <code>{res:g}</code>", parse_mode="HTML")
            return
        except Exception:
            pass

    try:
        sym_res = sympy.sympify(expr)
        await update.message.reply_text(f"🧮 <b>Calculation:</b> <code>{raw}</code>\n<b>Result:</b> <code>{sym_res}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ Could not evaluate math query. Example: <code>/calc 1000 ka 30%</code>", parse_mode="HTML")


async def is_deleted_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    target_id = None
    if args:
        try:
            target_id = int(str(args[0]).replace("@", "").strip())
        except Exception:
            pass
    elif update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id

    if not target_id:
        await update.message.reply_text("⚠️ format: /is_deleted <user_id>")
        return

    from modules.utils.storage import get_user
    ud = get_user(target_id)

    name = None
    try:
        chat = await context.bot.get_chat(target_id)
        if chat.first_name and "deleted" in chat.first_name.lower():
            await update.message.reply_text("❌ Account is Deleted or Not Found!")
            return
        name = ud.get("display_name") or chat.first_name or chat.username or f"User {target_id}"
    except Exception:
        if ud and (ud.get("display_name") or ud.get("username") and ud.get("username") != "User"):
            name = ud.get("display_name") or ud.get("username")
        else:
            await update.message.reply_text("❌ Account is Deleted or Not Found!")
            return

    mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(name)}</a>'
    text = (
        "✅ Account is Active!\n"
        f"👤 Name: {mention}\n"
        f"🆔 ID: {target_id}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        await update.message.reply_text("🛡️ Run this in a group!")
        return

    replied = update.message.reply_to_message
    if not replied:
        await update.message.reply_text("🛡️ Reply to the message you want to report: /report [reason]")
        return

    reason = " ".join(context.args).strip() if context.args else "Suspicious / spam message"
    reporter_name = user.first_name or user.username or "Someone"
    reported_user = replied.from_user
    reported_name = reported_user.first_name if reported_user else "User"

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        admin_mentions = []
        for a in admins:
            if not a.user.is_bot:
                admin_mentions.append(f"[{a.user.first_name}](tg://user?id={a.user.id})")
        
        msg = (
            f"🚨 <b>USER REPORTED TO ADMINS</b>\n\n"
            f"👤 <b>Reported User:</b> {reported_name} (<code>{reported_user.id if reported_user else 'N/A'}</code>)\n"
            f"📢 <b>Reported By:</b> {reporter_name}\n"
            f"📝 <b>Reason:</b> {reason}\n\n"
            f"Admins: {', '.join(admin_mentions[:5])}"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(f"🚨 Reported message to admins! (Reason: {reason})")


async def setemoji(update, context):
    user = update.effective_user
    args = context.args or []
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if not ud.get("premium"):
        await update.message.reply_text(
            "💓 Oɴʟʏ Pʀᴇᴍɪᴜᴍ Uꜱᴇʀꜱ Cᴀɴ Sᴇᴛ Tʜᴇɪʀ Cᴜꜱᴛᴏᴍ Eᴍᴏᴊɪ.\n"
            " Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ → /pay"
        )
        return
    if not args:
        await update.message.reply_text("😀 Usage: /setemoji <emoji> (or reply to a friend with /setemoji <emoji>)")
        return
    emoji = args[0].strip()

    target = _reply_user(update)
    if target and target.id != user.id:
        update_user(target.id, emoji=emoji)
        mention = f'<a href="tg://user?id={target.id}">{html_lib.escape(target.first_name or "User")}</a>'
        await update.message.reply_text(f"✅ Custom emoji for {mention} is now: {emoji}", parse_mode="HTML")
    else:
        update_user(user.id, emoji=emoji)
        await update.message.reply_text(f"✅ Your custom emoji is now: {emoji}")


async def check_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user
    from modules.utils.storage import get_user, get_all_users
    ud_caller = get_user(caller.id, getattr(caller, "username", "User"), getattr(caller, "first_name", "User"))

    if not ud_caller.get("premium"):
        await update.message.reply_text("💓 Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Iꜱ Oɴʟʏ Fᴏʀ Pʀᴇᴍɪᴜᴍ Uꜱᴇʀꜱ. Bᴜʏ Pʀᴇᴍɪᴜᴍ Uꜱɪɴɢ→ /pay")
        return

    replied = _reply_user(update)
    args = context.args or []
    target_id = None
    target_obj = None

    if replied:
        target_id = replied.id
        target_obj = replied
    elif args:
        arg = args[0].strip()
        if arg.startswith("@"):
            uname = arg[1:].lower()
            all_users = get_all_users()
            for uid_str, uinfo in all_users.items():
                if (uinfo.get("username") or "").lower() == uname:
                    target_id = int(uid_str)
                    break
        elif arg.isdigit():
            target_id = int(arg)
        else:
            uname = arg.lower()
            all_users = get_all_users()
            for uid_str, uinfo in all_users.items():
                if (uinfo.get("username") or "").lower() == uname:
                    target_id = int(uid_str)
                    break

    if not target_id:
        await update.message.reply_text("⚠️  Uꜱᴀɢᴇ: /check Rᴇᴘʟʏ Oʀ Uꜱᴇʀ Iᴅ.")
        return

    ud_t = get_user(target_id)
    raw_name = ud_t.get("display_name") or (target_obj.first_name if target_obj else None) or ud_t.get("username") or f"User {target_id}"
    mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(raw_name)}</a>'
    emoji = ud_t.get("emoji") or "❌ None"

    await update.message.reply_text(
        f"✨ <b>Uꜱᴇʀ Cʜᴇᴄᴋ</b> — {mention}\n"
        f"✨ Eᴍᴏᴊɪ: {emoji}\n"
        f"👑 Pʀᴇᴍɪᴜᴍ: {'Yᴇꜱ' if ud_t.get('premium') else 'Nᴏ'}",
        parse_mode="HTML",
    )


async def detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    replied = _reply_user(update)
    args = context.args or []
    from modules.utils.storage import get_all_users
    all_users = get_all_users()

    target_id = None
    target_obj = None

    if replied:
        target_id = replied.id
        target_obj = replied
    elif args:
        arg = args[0].strip()
        if arg.startswith("@"):
            uname = arg[1:].lower()
            for uid_str, uinfo in all_users.items():
                if (uinfo.get("username") or "").lower() == uname:
                    target_id = int(uid_str)
                    break
        elif arg.isdigit():
            if arg in all_users:
                target_id = int(arg)
            else:
                try:
                    target_id = int(arg)
                except Exception:
                    pass
        else:
            uname = arg.lower()
            for uid_str, uinfo in all_users.items():
                if (uinfo.get("username") or "").lower() == uname:
                    target_id = int(uid_str)
                    break

    if not target_id:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: /detail <ᴜꜱᴇʀɴᴀᴍᴇ/ʀᴇᴘʟʏ/ɪᴅ>")
        return

    if target_obj:
        ud = get_user(
            target_id,
            getattr(target_obj, "username", None) or "User",
            getattr(target_obj, "full_name", None) or target_obj.first_name,
        )
    else:
        ud = get_user(target_id)

    raw_name = ud.get("display_name") or (target_obj.first_name if target_obj else None) or ud.get("username") or f"User {target_id}"

    # Past names
    past_names = list(ud.get("past_names") or [])
    if raw_name and raw_name not in past_names:
        past_names.append(raw_name)
    if not past_names:
        past_names = [raw_name]
    names_block = "\n".join([f"• {html_lib.escape(n)}" for n in past_names if n])

    # Past usernames
    curr_uname = None
    if target_obj and getattr(target_obj, "username", None):
        curr_uname = target_obj.username
    elif ud.get("username") and ud.get("username") != "User":
        curr_uname = ud.get("username")

    past_unames = list(ud.get("past_usernames") or [])
    if curr_uname and curr_uname not in past_unames:
        past_unames.append(curr_uname)

    valid_unames = [u for u in past_unames if u and u != "User"]
    if valid_unames:
        unames_block = "\n".join([f"• @{html_lib.escape(u.lstrip('@'))}" for u in valid_unames])
    else:
        unames_block = "• None"

    mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(raw_name)}</a>'
    text = (
        f"{mention}'s Hɪꜱᴛᴏʀʏ\n"
        "________________________\n"
        "Fᴜʟʟ Nᴀᴍᴇꜱ:\n"
        f"{names_block}\n\n"
        "-----------\n"
        "Uꜱᴇʀɴᴀᴍᴇꜱ:\n"
        f"{unames_block}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def owner_cmd(update, context):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("👑 Run this in a group!")
        return
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        owner = next((m for m in admins if m.status == "creator"), None)
        if owner:
            await update.message.reply_text(f"👑 Group Owner: [{owner.user.first_name}](tg://user?id={owner.user.id})", parse_mode="Markdown")
        else:
            await update.message.reply_text("👑 No owner found.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def admins_cmd(update, context):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🛡️ Run this in a group!")
        return
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        from modules.utils.storage import get_all_users
        all_users = get_all_users()

        owner_mention = "None"
        admin_lines = []

        for m in admins:
            if m.user.is_bot:
                continue
            u_id = m.user.id
            ud = all_users.get(str(u_id), {})
            name = ud.get("display_name") or getattr(m.user, "full_name", None) or m.user.first_name or "User"
            mention = f'<a href="tg://user?id={u_id}">{html_lib.escape(name)}</a>'

            if m.status == "creator":
                owner_mention = mention
            else:
                admin_lines.append(f"• {mention}")

        total_admins = (1 if owner_mention != "None" else 0) + len(admin_lines)
        admins_block = "\n".join(admin_lines) if admin_lines else "• None"

        text = (
            f"👑 <b>Gʀᴏᴜᴘ Oᴡɴᴇʀ:</b> {owner_mention}\n\n"
            f"🛡️ <b>Aᴅᴍɪɴꜱ:</b>\n"
            f"{admins_block}\n\n"
            f"👥 <b>Tᴏᴛᴀʟ Aᴅᴍɪɴꜱ:</b> {total_admins}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


INTRO_FORMAT_HELP = (
    "⚠️ Intro format:\n"
    "⚡ /intro reply\n"
    "⚡ /intro me (with/without reply)\n"
    "⚡ /setintro intro text"
)


async def intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    sub = (args[0].lower() if args else "").strip()
    author = update.effective_user
    replied = _reply_user(update)

    if sub == "reply":
        if not replied:
            await update.message.reply_text(INTRO_FORMAT_HELP)
            return
        target = replied
    elif sub == "me":
        target = author
    else:
        await update.message.reply_text(INTRO_FORMAT_HELP)
        return

    ud = get_user(
        target.id,
        getattr(target, "username", None) or (target.first_name or "User"),
        target.first_name,
    )
    intro_text = ud.get("intro_text")
    name = ud.get("display_name") or target.first_name or "User"

    if not intro_text:
        if target.id == author.id:
            await update.message.reply_text(
                "❌ You haven't set an intro yet.\nUse <code>/setintro &lt;text&gt;</code> to set your intro.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                f"❌ <b>{name}</b> hasn't set an intro yet.",
                parse_mode="HTML",
            )
        return

    await update.message.reply_text(
        f"⚡ <b>Intro of {name}:</b>\n\n{intro_text}",
        parse_mode="HTML",
    )


async def setintro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = None
    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text.strip()
    args = context.args or []
    if args:
        joined = " ".join(args).strip()
        if joined:
            text = joined
    if not text:
        await update.message.reply_text(INTRO_FORMAT_HELP)
        return
    if len(text) > 500:
        text = text[:500]
    get_user(user.id, user.username or user.first_name or "User", user.first_name)
    update_user(user.id, intro_text=text)
    await update.message.reply_text("✅ Your intro has been saved! Preview: /intro me")


async def own(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Reply To A Sticker To Add In Your Pack.")


async def open_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🛡️ Run this in a group!")
        return
    if not (await _is_admin(update, context, user.id)):
        await update.message.reply_text("🛡️ Only group admins can use /open.")
        return
    update_group(chat.id, economy_enabled=True)
    await update.message.reply_text("✅ All Economy Commands Have Been Enabled In This Group.")


async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🛡️ Run this in a group!")
        return
    if not (await _is_admin(update, context, user.id)):
        await update.message.reply_text("🛡️ Only group admins can use /close.")
        return
    update_group(chat.id, economy_enabled=False)
    await update.message.reply_text("🚫 All Economy Commands Have Been Disabled In This Group.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🍀 Tᴀᴘ Tʜᴇ Bᴜᴛᴛᴏɴ Bᴇʟᴏᴡ Tᴏ Gᴇᴛ Sᴏᴍᴇ Aᴍᴀᴢɪɴɢ Mɪᴋᴏ'S Gʀᴏᴜᴘ Mᴀɴᴀɢᴇᴍᴇɴᴛ Cᴏᴍᴍᴀɴᴅꜱ."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Cʟɪᴄᴋ Hᴇʀᴇ Fᴏʀ Cᴏᴍᴍᴀɴᴅ Lɪꜱᴛ", url="https://t.me/i_mikoo/9")]
    ])
    await update.message.reply_text(text, reply_markup=kb)


async def tr(update, context):
    args = context.args or []
    replied = update.message.reply_to_message if update.message else None

    if not replied and not args:
        await update.message.reply_text("🥀 Uꜱᴀɢᴇ: /tr <Rᴇᴘʟʏ> <Lᴀɴɢᴜᴀɢᴇ Nᴀᴍᴇ>")
        return

    text = None
    target_lang = "english"

    if replied:
        text = replied.text or replied.caption
        if args:
            target_lang = " ".join(args).strip()
    elif args:
        if len(args) >= 2:
            target_lang = args[0].strip()
            text = " ".join(args[1:])
        else:
            await update.message.reply_text("🥀 Uꜱᴀɢᴇ: /tr <Rᴇᴘʟʏ> <Lᴀɴɢᴜᴀɢᴇ Nᴀᴍᴇ>")
            return

    if not text:
        await update.message.reply_text("🥀 Uꜱᴀɢᴇ: /tr <Rᴇᴘʟʏ> <Lᴀɴɢᴜᴀɢᴇ Nᴀᴍᴇ>")
        return

    wait_msg = await update.message.reply_text("🌐 <i>Translating...</i>", parse_mode="HTML")
    try:
        translated, src_lang, tgt_lang = await ai_translate(text, target_lang)
        result_text = f"Translated from {src_lang} to {tgt_lang}.\n\n{translated}"
        await wait_msg.edit_text(result_text)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Translation error: {e}")


async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    from modules.utils.storage import get_all_users, get_featured_groups, save_featured_groups
    data = get_all_users()
    sorted_richest = sorted(data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)
    top_5_ids = [int(uid) for uid, _ in sorted_richest[:5]]

    if user.id not in top_5_ids:
        await update.message.reply_text("🚫 Oɴʟʏ Tᴏᴘ 5 Gʟᴏʙᴀʟ Rɪᴄʜᴇꜱᴛ Uꜱᴇʀꜱ Cᴀɴ Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("💡 Usage: /setgroup <Group Name> | <https://t.me/your_group_link>")
        return

    raw = " ".join(args).strip()
    if "|" in raw:
        parts = raw.split("|", 1)
        g_name = parts[0].strip()
        g_link = parts[1].strip()
    else:
        g_name = user.first_name or "Top Group"
        g_link = raw

    if not g_link.startswith("http"):
        g_link = f"https://t.me/{g_link.lstrip('@')}"

    groups = [g for g in get_featured_groups() if g.get("user_id") != user.id]
    groups.append({"name": g_name, "link": g_link, "user_id": user.id})
    save_featured_groups(groups[:5])

    await update.message.reply_text(
        f"✅ <b>Featured Group Updated!</b>\n\n"
        f"🏷️ Name: <b>{html_lib.escape(g_name)}</b>\n"
        f"🔗 Link: {g_link}",
        parse_mode="HTML",
    )


HANDLERS = {
    "crush": cmd_crush,
    "love": cmd_love,
    "look": cmd_look,
    "brain": cmd_brain,
    "stupid_meter": stupid_meter,
    "murder": cmd_murder,
    "slap": cmd_slap,
    "punch": cmd_punch,
    "bite": cmd_bite,
    "kiss": cmd_kiss,
    "hug": cmd_hug,
    "couples": couples,
    "friends": friends,
    "addf": addf,
    "tag": tag_cmd,
    "t": tag_cmd,
    "ctag": ctag,
    "delf": delf,
    "allf": allf,
    "friend": friend,
    "gift": gift,
    "q": q_cmd,
    "calc": calc_cmd,
    "c": calc_cmd,
    "voice": voice,
    "tr": tr,
    "is_deleted": is_deleted_cmd,
    "report": report_cmd,
    "setemoji": setemoji,
    "check": check_emoji,
    "detail": detail,
    "owner": owner_cmd,
    "admins": admins_cmd,
    "admin": admins_cmd,
    "intro": intro,
    "setintro": setintro,
    "own": own,
    "open": open_cmd,
    "close": close_cmd,
    "help": help_cmd,
    "setgroup": setgroup,
    "ping": ping_cmd,
}
