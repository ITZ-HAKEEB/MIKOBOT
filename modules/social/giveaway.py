"""
Giveaway System for Miko Bot
============================
Prizes:
  1st Prize: FAKE TAG ID : @Usa_fake_tag_id (https://t.me/Usa_fake_tag_id)
  2nd Prize: @Giveaway_gc this group (https://t.me/Giveaway_gc)

Duration:
  7 Days with automatic end & results announcement.

Winner Selection:
  Winners are chosen based on the Top Rich Players on the leaderboard
  (highest net worth: balance + wallet_balance) among all enrolled participants!

Tasks required to join:
  1. Add @i_mikobot to a group with 1000+ members (and make bot Admin)
  2. Add @noahsongbot to a group with 1000+ members (and make bot Admin)
  3. Join @i_mikoo (Updates Channel)
  4. Join @titanic_network

Commands (Admin / Owner):
  /giveaway create [prizes]        — Start 7-day giveaway in group
  /giveaway setprize <p1> | <p2>   — Update prize descriptions
  /giveaway end                    — End giveaway now & announce leaderboard winners
  /giveaway cancel                 — Cancel giveaway
  /giveaway info                   — View status, remaining time & entries
  /giveaway entries                — List all enrolled participants

User Commands:
  /join_giveaway (or /gjoin)       — Open DM task verification flow
  /gcheck                          — Re-check task status
  /gwgroup <@group or ID>          — Verify 1000+ member group with both bots as admins
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from modules.utils.db import (
    _json_serial,
    _sanitize_doc,
    get_mongo_db,
    get_redis_client,
    is_sudo_user,
)
from modules.utils.storage import get_user

logger = logging.getLogger(__name__)

# ─── Channels & Bots ─────────────────────────────────────────────────────────
UPDATES_CHANNEL = "@i_mikoo"
NETWORK_CHANNEL = "@titanic_network"
MIKO_BOT_USERNAME = "i_mikobot"
NOAH_BOT_USERNAME = "noahsongbot"

MIN_GROUP_MEMBERS = 1000
GIVEAWAY_DURATION_DAYS = 7

# ─── Default Prizes & Links ──────────────────────────────────────────────────
DEFAULT_PRIZE_1 = "FAKE TAG ID : @Usa_fake_tag_id"
DEFAULT_PRIZE_1_URL = "https://t.me/Usa_fake_tag_id"

DEFAULT_PRIZE_2 = "@Giveaway_gc this group"
DEFAULT_PRIZE_2_URL = "https://t.me/Giveaway_gc"

_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "giveaway_data.json",
)


# ─── Persistence Helpers ─────────────────────────────────────────────────────

def _load() -> Dict[str, Any]:
    if not os.path.exists(_FILE):
        return {}
    try:
        with open(_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    try:
        with open(_FILE, "w") as f:
            json.dump(data, f, indent=2, default=_json_serial)
    except Exception:
        pass


def _get_giveaway(chat_id: int) -> Optional[Dict[str, Any]]:
    cid = str(chat_id)
    r = get_redis_client()
    if r:
        try:
            val = r.get(f"miko:giveaway:{cid}")
            if val:
                return json.loads(val)
        except Exception:
            pass
    db = get_mongo_db()
    if db is not None:
        try:
            doc = db.giveaways.find_one({"_id": cid})
            if doc:
                doc.pop("_id", None)
                return doc
        except Exception:
            pass
    data = _load()
    return data.get(cid)


def _set_giveaway(chat_id: int, gdata: Dict[str, Any]) -> None:
    cid = str(chat_id)
    gdata = _sanitize_doc(gdata)
    serialized = json.dumps(gdata, default=_json_serial)
    r = get_redis_client()
    if r:
        try:
            r.set(f"miko:giveaway:{cid}", serialized)
            if gdata.get("active"):
                r.sadd("miko:active_giveaways", cid)
            else:
                r.srem("miko:active_giveaways", cid)
        except Exception:
            pass
    db = get_mongo_db()
    if db is not None:
        try:
            db.giveaways.update_one({"_id": cid}, {"$set": gdata}, upsert=True)
        except Exception:
            pass
    data = _load()
    data[cid] = gdata
    _save(data)


def _del_giveaway(chat_id: int) -> None:
    cid = str(chat_id)
    r = get_redis_client()
    if r:
        try:
            r.delete(f"miko:giveaway:{cid}")
            r.srem("miko:active_giveaways", cid)
        except Exception:
            pass
    db = get_mongo_db()
    if db is not None:
        try:
            db.giveaways.delete_one({"_id": cid})
        except Exception:
            pass
    data = _load()
    data.pop(cid, None)
    _save(data)


# ─── User Task State ─────────────────────────────────────────────────────────

def _get_user_task(user_id: int, chat_id: int) -> Dict[str, Any]:
    key = f"miko:gtask:{user_id}:{chat_id}"
    r = get_redis_client()
    if r:
        try:
            val = r.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass
    db = get_mongo_db()
    if db is not None:
        try:
            doc = db.giveaway_tasks.find_one({"_id": key})
            if doc:
                doc.pop("_id", None)
                return doc
        except Exception:
            pass
    return {}


def _set_user_task(user_id: int, chat_id: int, tdata: Dict[str, Any]) -> None:
    key = f"miko:gtask:{user_id}:{chat_id}"
    tdata = _sanitize_doc(tdata)
    serialized = json.dumps(tdata, default=_json_serial)
    r = get_redis_client()
    if r:
        try:
            r.set(key, serialized)
        except Exception:
            pass
    db = get_mongo_db()
    if db is not None:
        try:
            db.giveaway_tasks.update_one({"_id": key}, {"$set": tdata}, upsert=True)
        except Exception:
            pass


def _get_user_active_chat(user_id: int) -> Optional[int]:
    """Retrieve the giveaway chat_id the user is currently interacting with."""
    r = get_redis_client()
    if r:
        try:
            val = r.get(f"miko:user_active_gw:{user_id}")
            if val:
                return int(val)
        except Exception:
            pass
    return None


def _set_user_active_chat(user_id: int, chat_id: int) -> None:
    r = get_redis_client()
    if r:
        try:
            r.set(f"miko:user_active_gw:{user_id}", str(chat_id), ex=86400 * 14)
        except Exception:
            pass


# ─── Bot Username Helper ─────────────────────────────────────────────────────

async def _get_bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.bot:
        if getattr(context.bot, "username", None):
            return context.bot.username
        try:
            me = await context.bot.get_me()
            if me and me.username:
                return me.username
        except Exception:
            pass
    return MIKO_BOT_USERNAME


# ─── Admin Check ─────────────────────────────────────────────────────────────

async def _is_owner_or_sudoer(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_sudo_user(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


# ─── Task Verification Helpers ───────────────────────────────────────────────

async def _check_channel_member(bot, user_id: int, channel: str) -> bool:
    try:
        m = await bot.get_chat_member(channel, user_id)
        return m.status not in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT, "kicked")
    except Exception:
        return False


async def _verify_group_for_user(
    bot,
    user_id: int,
    group_input: str,
    giveaway_chat_id: int,
) -> Tuple[bool, str]:
    """
    Verifies that:
      1. Group exists and has >= 1000 members.
      2. @i_mikobot is an Administrator in the group.
      3. @noahsongbot is an Administrator in the group.
      4. The user is a member/admin in the group.
    """
    raw = group_input.strip()
    # Normalize link or username
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()

    if raw.startswith("+") or "joinchat" in raw:
        return False, "⚠️ Please provide a public <b>@username</b> or <b>Chat ID</b> (private invite links cannot be inspected)."

    if not raw.startswith("-") and not raw.startswith("@") and not raw.isdigit():
        group_identifier = f"@{raw}"
    elif raw.startswith("-") or raw.isdigit():
        try:
            group_identifier = int(raw)
        except Exception:
            group_identifier = raw
    else:
        group_identifier = raw

    try:
        chat = await bot.get_chat(group_identifier)
    except Exception:
        return False, f"❌ Could not find group <code>{html.escape(str(group_identifier))}</code>.\nPlease make sure both bots are added there first!"

    if chat.type not in ("group", "supergroup"):
        return False, f"❌ <b>{html.escape(chat.title or 'This chat')}</b> is not a group/supergroup!"

    # 1. Member count check (>= 1000)
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0

    if count < MIN_GROUP_MEMBERS:
        return (
            False,
            f"❌ Group <b>{html.escape(chat.title)}</b> has only <b>{count:,} members</b>.\n"
            f"Required: At least <b>{MIN_GROUP_MEMBERS:,} members</b>!",
        )

    # 2. Administrator checks
    try:
        admins = await bot.get_chat_administrators(chat.id)
    except Exception:
        return (
            False,
            f"❌ Cannot read admin list for <b>{html.escape(chat.title)}</b>.\n"
            f"Make sure <b>@{MIKO_BOT_USERNAME}</b> is promoted to <b>Admin</b>!",
        )

    miko_admin = any(a.user.id == bot.id for a in admins)
    if not miko_admin:
        return (
            False,
            f"❌ <b>@{MIKO_BOT_USERNAME}</b> is not an <b>Administrator</b> in <b>{html.escape(chat.title)}</b>!\n"
            f"Please give <b>@{MIKO_BOT_USERNAME}</b> admin rights.",
        )

    noah_admin = any(
        (a.user.username and a.user.username.lower() == NOAH_BOT_USERNAME.lower())
        for a in admins
    )
    if not noah_admin:
        return (
            False,
            f"❌ <b>@{NOAH_BOT_USERNAME}</b> is not an <b>Administrator</b> in <b>{html.escape(chat.title)}</b>!\n"
            f"Please add <b>@{NOAH_BOT_USERNAME}</b> and promote it to admin.",
        )

    # 3. Verify user membership in this group
    try:
        user_member = await bot.get_chat_member(chat.id, user_id)
        if user_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, "kicked"):
            return False, f"❌ You are not a member of <b>{html.escape(chat.title)}</b>!"
    except Exception:
        pass

    # Success! Save task progress
    tdata = _get_user_task(user_id, giveaway_chat_id)
    tdata["miko_added"] = True
    tdata["noah_added"] = True
    tdata["verified_group_id"] = chat.id
    tdata["verified_group_title"] = chat.title
    tdata["verified_member_count"] = count
    _set_user_task(user_id, giveaway_chat_id, tdata)

    return (
        True,
        f"✅ <b>Group Verified!</b>\n\n"
        f"🏷 <b>Group:</b> {html.escape(chat.title)} ({count:,} members)\n"
        f"🛡 <b>@{MIKO_BOT_USERNAME}:</b> Admin ✅\n"
        f"🎵 <b>@{NOAH_BOT_USERNAME}:</b> Admin ✅\n\n"
        f"✨ Tasks 1 & 2 marked complete!",
    )


async def _verify_all_tasks(bot, user_id: int, chat_id: int) -> Dict[str, bool]:
    tdata = _get_user_task(user_id, chat_id)
    t1 = bool(tdata.get("miko_added"))
    t2 = bool(tdata.get("noah_added"))
    t3 = await _check_channel_member(bot, user_id, UPDATES_CHANNEL)
    t4 = await _check_channel_member(bot, user_id, NETWORK_CHANNEL)
    return {"miko_added": t1, "noah_added": t2, "updates": t3, "network": t4}


def _task_keyboard(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Verify 1000+ Member Group", callback_data=f"gw_submit_group:{user_id}:{chat_id}")],
        [InlineKeyboardButton("📢 Join @i_mikoo Updates", url="https://t.me/i_mikoo")],
        [InlineKeyboardButton("🌐 Join @titanic_network", url="https://t.me/titanic_network")],
        [InlineKeyboardButton("🔍 Verify My Tasks", callback_data=f"gw_verify:{user_id}:{chat_id}")],
    ])


def _tasks_text(tasks: Dict[str, bool], tdata: Optional[Dict[str, Any]] = None) -> str:
    def tick(v):
        return "✅" if v else "❌"

    tdata = tdata or {}
    group_info = ""
    if tdata.get("verified_group_title"):
        group_info = f"\n   <i>(Verified: {html.escape(tdata['verified_group_title'])})</i>"

    return (
        "📋 <b>Giveaway Tasks</b>\n\n"
        f"{tick(tasks['miko_added'])} 1️⃣ Add <b>@i_mikobot</b> to a group with 1000+ members (Admin){group_info}\n"
        f"{tick(tasks['noah_added'])} 2️⃣ Add <b>@noahsongbot</b> to a group with 1000+ members (Admin)\n"
        f"{tick(tasks['updates'])} 3️⃣ Join <b>@i_mikoo</b> (Updates Channel)\n"
        f"{tick(tasks['network'])} 4️⃣ Join <b>@titanic_network</b>\n\n"
        "💡 <i>Tap <b>🔗 Verify 1000+ Member Group</b> or send:</i>\n"
        "<code>/gwgroup @yourgroup</code>\n\n"
        "When finished, tap <b>🔍 Verify My Tasks</b> to enroll!"
    )


# ─── End Giveaway & Announce Leaderboard Winners ──────────────────────────────

async def end_giveaway_and_announce(bot, chat_id: int) -> Tuple[bool, str]:
    """Ends a giveaway and announces the top rich players as winners."""
    gdata = _get_giveaway(chat_id)
    if not gdata or not gdata.get("active"):
        return False, "⚠️ No active giveaway found to end."

    prize_1 = gdata.get("prize_1", DEFAULT_PRIZE_1)
    prize_1_url = gdata.get("prize_1_url", DEFAULT_PRIZE_1_URL)
    prize_2 = gdata.get("prize_2", DEFAULT_PRIZE_2)
    prize_2_url = gdata.get("prize_2_url", DEFAULT_PRIZE_2_URL)

    entries = gdata.get("entries", [])
    if not entries:
        text = (
            "🎊 <b>GIVEAWAY ENDED!</b> 🎊\n\n"
            "🎁 Unfortunately, <b>no verified participants joined</b>.\n"
            "No winners were picked."
        )
        gdata["active"] = False
        gdata["ended_at"] = datetime.utcnow().isoformat()
        _set_giveaway(chat_id, gdata)
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception:
            pass
        return True, text

    # Calculate net worth (wealth = balance + wallet_balance) for each entrant
    ranked_entries = []
    for e in entries:
        uid = e["user_id"]
        try:
            ud = get_user(uid)
            wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        except Exception:
            wealth = 0
        ranked_entries.append({
            **e,
            "wealth": wealth,
        })

    # Sort descending by wealth
    ranked_entries.sort(key=lambda x: x["wealth"], reverse=True)

    w1 = ranked_entries[0]
    w2 = ranked_entries[1] if len(ranked_entries) > 1 else None

    w1_mention = f'<a href="tg://user?id={w1["user_id"]}">{html.escape(w1["name"])}</a>'
    w1_user = f"@{w1.get('username')}" if w1.get("username") and w1.get("username") != "N/A" else f"ID: {w1['user_id']}"

    text_parts = [
        "🎊 <b>GIVEAWAY CONCLUDED!</b> 🎊\n",
        "🏆 <b>OFFICIAL WINNERS (Top Leaderboard Players):</b>\n",
        f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>",
        f"👑 <b>Champion:</b> {w1_mention} ({w1_user})",
        f"💰 <b>Net Worth:</b> <code>{w1['wealth']:,} Coins</code>\n",
    ]

    if w2:
        w2_mention = f'<a href="tg://user?id={w2["user_id"]}">{html.escape(w2["name"])}</a>'
        w2_user = f"@{w2.get('username')}" if w2.get("username") and w2.get("username") != "N/A" else f"ID: {w2['user_id']}"
        text_parts.extend([
            f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>",
            f"👑 <b>Runner-Up:</b> {w2_mention} ({w2_user})",
            f"💰 <b>Net Worth:</b> <code>{w2['wealth']:,} Coins</code>\n",
        ])

    text_parts.extend([
        f"👥 Total verified entries: <b>{len(entries)}</b>",
        "🎉 Congratulations to our richest players on the leaderboard!",
    ])

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 1st Prize: @Usa_fake_tag_id", url=prize_1_url)],
        [InlineKeyboardButton("🥈 2nd Prize: @Giveaway_gc", url=prize_2_url)],
    ])

    result_text = "\n".join(text_parts)
    gdata["active"] = False
    gdata["winner_1"] = w1
    gdata["winner_2"] = w2
    gdata["ended_at"] = datetime.utcnow().isoformat()
    _set_giveaway(chat_id, gdata)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=result_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as err:
        logger.error(f"Failed to send giveaway results to group {chat_id}: {err}")

    return True, result_text


# ─── Periodic Monitor for 7-Day Expirations ──────────────────────────────────

async def check_all_expired_giveaways(bot) -> None:
    """Checks for active giveaways that exceeded their 7-day duration."""
    chat_ids_to_check = set()
    r = get_redis_client()
    if r:
        try:
            active_ids = r.smembers("miko:active_giveaways")
            for cid in active_ids:
                if isinstance(cid, bytes):
                    cid = cid.decode("utf-8")
                chat_ids_to_check.add(int(cid))
        except Exception:
            pass

    db = get_mongo_db()
    if db is not None:
        try:
            for doc in db.giveaways.find({"active": True}, {"_id": 1}):
                chat_ids_to_check.add(int(doc["_id"]))
        except Exception:
            pass

    now = datetime.utcnow()
    for cid in chat_ids_to_check:
        gdata = _get_giveaway(cid)
        if not gdata or not gdata.get("active"):
            continue
        ends_at_str = gdata.get("ends_at")
        if not ends_at_str:
            continue
        try:
            ends_at = datetime.fromisoformat(ends_at_str)
            if now >= ends_at:
                logger.info(f"Giveaway in chat {cid} expired after 7 days. Auto-ending...")
                await end_giveaway_and_announce(bot, cid)
        except Exception as err:
            logger.error(f"Error checking giveaway expiry for {cid}: {err}")


async def start_giveaway_monitor(bot) -> None:
    """Background task looping to auto-end expired giveaways."""
    logger.info("🎁 7-Day Giveaway Expiry Monitor started...")
    while True:
        try:
            await check_all_expired_giveaways(bot)
        except Exception as e:
            logger.error(f"Error in giveaway monitor: {e}")
        await asyncio.sleep(300)  # Check every 5 minutes


# ─── /giveaway (Admin Command) ───────────────────────────────────────────────

async def cmd_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    if chat.type == "private":
        await msg.reply_text("⚠️ Giveaway commands must be used in a <b>group chat</b>.", parse_mode="HTML")
        return

    if not await _is_owner_or_sudoer(user.id, chat.id, context):
        await msg.reply_text("🚫 Only the bot owner or group admins can manage giveaways!")
        return

    args = context.args or []
    sub = args[0].lower() if args else "info"

    # ── CREATE ──────────────────────────────────────────────────────────────
    if sub == "create":
        existing = _get_giveaway(chat.id)
        if existing and existing.get("active"):
            await msg.reply_text(
                "⚠️ A giveaway is already running in this group!\n"
                "Use <code>/giveaway end</code> or <code>/giveaway cancel</code> first.",
                parse_mode="HTML",
            )
            return

        prize_1 = DEFAULT_PRIZE_1
        prize_1_url = DEFAULT_PRIZE_1_URL
        prize_2 = DEFAULT_PRIZE_2
        prize_2_url = DEFAULT_PRIZE_2_URL

        # Optional custom prize override
        if len(args) > 1:
            raw_p = " ".join(args[1:])
            if "|" in raw_p:
                parts = raw_p.split("|", 1)
                prize_1 = parts[0].strip() or DEFAULT_PRIZE_1
                prize_2 = parts[1].strip() or DEFAULT_PRIZE_2
            else:
                prize_1 = raw_p.strip()

        created_at = datetime.utcnow()
        ends_at = created_at + timedelta(days=GIVEAWAY_DURATION_DAYS)

        gdata = {
            "chat_id": chat.id,
            "chat_title": chat.title or "Group",
            "prize_1": prize_1,
            "prize_1_url": prize_1_url,
            "prize_2": prize_2,
            "prize_2_url": prize_2_url,
            "active": True,
            "created_by": user.id,
            "created_at": created_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "entries": [],
        }
        _set_giveaway(chat.id, gdata)

        bot_username = await _get_bot_username(context)
        ends_at_str = ends_at.strftime("%Y-%m-%d %H:%M UTC")

        text = (
            "🎉 <b>GIVEAWAY STARTED!</b> 🎉\n\n"
            f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>\n"
            f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>\n\n"
            f"⏳ <b>Duration:</b> 7 Days (Ends: <code>{ends_at_str}</code>)\n"
            "🏆 <b>Winner Criteria:</b> Top Rich Players on Leaderboard!\n\n"
            "📋 <b>Tasks to Qualify:</b>\n"
            "1️⃣ Add <b>@i_mikobot</b> to a group with <b>1000+ members</b> (Admin)\n"
            "2️⃣ Add <b>@noahsongbot</b> to a group with <b>1000+ members</b> (Admin)\n"
            "3️⃣ Join <b>@i_mikoo</b> (Updates Channel)\n"
            "4️⃣ Join <b>@titanic_network</b>\n\n"
            "✨ Tap <b>🎟 Join Giveaway</b> below to complete tasks and enroll!"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🥇 1st Prize: @Usa_fake_tag_id", url=prize_1_url)],
            [InlineKeyboardButton("🥈 2nd Prize: @Giveaway_gc", url=prize_2_url)],
            [InlineKeyboardButton("🎟 Join Giveaway", url=f"https://t.me/{bot_username}?start=giveaway_{chat.id}")],
        ])
        await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # ── SET PRIZE ───────────────────────────────────────────────────────────
    if sub in ("setprize", "prize"):
        gdata = _get_giveaway(chat.id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway. Use <code>/giveaway create</code>", parse_mode="HTML")
            return
        if len(args) < 2:
            await msg.reply_text("Usage: <code>/giveaway setprize 1st Prize | 2nd Prize</code>", parse_mode="HTML")
            return
        raw_p = " ".join(args[1:])
        if "|" in raw_p:
            parts = raw_p.split("|", 1)
            gdata["prize_1"] = parts[0].strip()
            gdata["prize_2"] = parts[1].strip()
        else:
            gdata["prize_1"] = raw_p.strip()
        _set_giveaway(chat.id, gdata)
        await msg.reply_text(
            f"✅ Prizes updated:\n"
            f"🥇 1st: <b>{html.escape(gdata.get('prize_1', 'N/A'))}</b>\n"
            f"🥈 2nd: <b>{html.escape(gdata.get('prize_2', 'N/A'))}</b>",
            parse_mode="HTML",
        )
        return

    # ── END / PICK WINNERS ──────────────────────────────────────────────────
    if sub == "end":
        success, text = await end_giveaway_and_announce(context.bot, chat.id)
        if not success:
            await msg.reply_text(text)
        return

    # ── CANCEL ──────────────────────────────────────────────────────────────
    if sub == "cancel":
        gdata = _get_giveaway(chat.id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway to cancel.")
            return
        _del_giveaway(chat.id)
        await msg.reply_text("❌ Giveaway cancelled. No winners were picked.")
        return

    # ── ENTRIES ─────────────────────────────────────────────────────────────
    if sub == "entries":
        gdata = _get_giveaway(chat.id)
        if not gdata:
            await msg.reply_text("⚠️ No giveaway data found.")
            return
        entries = gdata.get("entries", [])
        if not entries:
            await msg.reply_text("📭 No verified entries yet.")
            return
        lines = [f"🎟 <b>Giveaway Participants ({len(entries)}):</b>\n"]
        for i, e in enumerate(entries, 1):
            try:
                ud = get_user(e["user_id"])
                wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
            except Exception:
                wealth = 0
            lines.append(
                f"{i}. <a href=\"tg://user?id={e['user_id']}\">{html.escape(e['name'])}</a> "
                f"(@{e.get('username', 'N/A')}) — <code>{wealth:,} Coins</code>"
            )
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return

    # ── INFO (Default) ───────────────────────────────────────────────────────
    gdata = _get_giveaway(chat.id)
    if not gdata:
        await msg.reply_text(
            "ℹ️ No active giveaway in this group.\n\nUse <code>/giveaway create</code> to start one!",
            parse_mode="HTML",
        )
        return

    status = "🟢 Active" if gdata.get("active") else "🔴 Ended"
    entries = gdata.get("entries", [])
    prize_1 = gdata.get("prize_1", DEFAULT_PRIZE_1)
    prize_1_url = gdata.get("prize_1_url", DEFAULT_PRIZE_1_URL)
    prize_2 = gdata.get("prize_2", DEFAULT_PRIZE_2)
    prize_2_url = gdata.get("prize_2_url", DEFAULT_PRIZE_2_URL)

    time_remaining = ""
    if gdata.get("active") and gdata.get("ends_at"):
        try:
            ends_at = datetime.fromisoformat(gdata["ends_at"])
            delta = ends_at - datetime.utcnow()
            if delta.total_seconds() > 0:
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                time_remaining = f"\n⏳ <b>Time Remaining:</b> {days}d {hours}h {minutes}m"
            else:
                time_remaining = "\n⏳ <b>Time Remaining:</b> Ending soon..."
        except Exception:
            pass

    text = (
        f"🎉 <b>Giveaway Information</b>\n\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>\n"
        f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>\n"
        f"🏆 <b>Rule:</b> Top Rich Players on Leaderboard Win!{time_remaining}\n"
        f"👥 <b>Verified Entries:</b> {len(entries)}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 1st Prize: @Usa_fake_tag_id", url=prize_1_url)],
        [InlineKeyboardButton("🥈 2nd Prize: @Giveaway_gc", url=prize_2_url)],
    ])
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ─── /join_giveaway (User Entry Command) ─────────────────────────────────────

async def cmd_join_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    # In group chat -> redirect to DM with deeplink
    if chat.type != "private":
        group_chat_id = chat.id
        gdata = _get_giveaway(group_chat_id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway running in this group.")
            return

        entries = gdata.get("entries", [])
        if any(e["user_id"] == user.id for e in entries):
            await msg.reply_text("✅ You are already verified and enrolled in this giveaway!", parse_mode="HTML")
            return

        bot_username = await _get_bot_username(context)
        bot_link = f"https://t.me/{bot_username}?start=giveaway_{group_chat_id}"
        await msg.reply_text(
            "🎟 <b>Join Giveaway</b>\n\n"
            "Click below to verify your tasks in private DM and get enrolled!\n\n"
            "<i>Complete all 4 tasks to qualify for 1st and 2nd prizes.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Verify Tasks in DM", url=bot_link)]
            ]),
            parse_mode="HTML",
        )
        return

    # In Private Chat -> show verification tasks
    group_chat_id = None
    if context.args:
        param = context.args[0]
        if param.startswith("giveaway_"):
            try:
                group_chat_id = int(param.split("_", 1)[1])
            except Exception:
                pass

    if not group_chat_id:
        group_chat_id = _get_user_active_chat(user.id)

    if not group_chat_id:
        await msg.reply_text(
            "⚠️ Please click the <b>Join Giveaway</b> button from the group where the giveaway is running,\n"
            "or use <code>/join_giveaway</code> inside the group.",
            parse_mode="HTML",
        )
        return

    _set_user_active_chat(user.id, group_chat_id)

    gdata = _get_giveaway(group_chat_id)
    if not gdata or not gdata.get("active"):
        await msg.reply_text("⚠️ No active giveaway found for that group.")
        return

    entries = gdata.get("entries", [])
    if any(e["user_id"] == user.id for e in entries):
        await msg.reply_text("✅ You are already verified and enrolled in the giveaway! 🎉")
        return

    tdata = _get_user_task(user.id, group_chat_id)
    tasks = await _verify_all_tasks(context.bot, user.id, group_chat_id)
    text = _tasks_text(tasks, tdata)
    kb = _task_keyboard(group_chat_id, user.id)
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ─── /gwgroup (Verify 1000+ Member Group) ────────────────────────────────────

async def cmd_gwgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Direct command for user to verify the group they added the bots to.
    Usage: /gwgroup <@group or ID>
    """
    msg = update.message
    if not msg:
        return
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if chat.type != "private":
        await msg.reply_text("💌 Please send <code>/gwgroup @yourgroup</code> in my <b>private chat</b>!", parse_mode="HTML")
        return

    args = context.args or []
    if not args:
        await msg.reply_text(
            "📋 <b>Group Verification Usage:</b>\n\n"
            "<code>/gwgroup @yourgroup</code>\n\n"
            "• Replace <code>@yourgroup</code> with your group's @username or Chat ID\n"
            "• Make sure the group has at least <b>1,000 members</b>\n"
            "• Make sure both <b>@i_mikobot</b> and <b>@noahsongbot</b> are <b>Admins</b>",
            parse_mode="HTML",
        )
        return

    group_input = args[0]
    giveaway_chat_id = _get_user_active_chat(user.id)
    if not giveaway_chat_id and len(args) > 1:
        try:
            giveaway_chat_id = int(args[1])
        except Exception:
            pass

    if not giveaway_chat_id:
        await msg.reply_text("⚠️ Please first click the <b>Join Giveaway</b> button from your giveaway group!", parse_mode="HTML")
        return

    status_msg = await msg.reply_text("🔍 <i>Checking group, member count, and bot admin permissions...</i>", parse_mode="HTML")

    success, response_text = await _verify_group_for_user(
        context.bot,
        user.id,
        group_input,
        giveaway_chat_id,
    )

    await status_msg.edit_text(response_text, parse_mode="HTML")

    if success:
        # Show updated tasks menu
        tdata = _get_user_task(user.id, giveaway_chat_id)
        tasks = await _verify_all_tasks(context.bot, user.id, giveaway_chat_id)
        text = _tasks_text(tasks, tdata)
        kb = _task_keyboard(giveaway_chat_id, user.id)
        await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ─── /gcheck (Re-Check Tasks) ────────────────────────────────────────────────

async def cmd_gcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if chat.type != "private":
        await msg.reply_text("💌 Use <code>/gcheck</code> in my DM to check your task status.", parse_mode="HTML")
        return

    group_chat_id = None
    if context.args:
        try:
            group_chat_id = int(context.args[0])
        except Exception:
            pass

    if not group_chat_id:
        group_chat_id = _get_user_active_chat(user.id)

    if not group_chat_id:
        await msg.reply_text(
            "⚠️ Please specify the group ID: <code>/gcheck &lt;group_id&gt;</code>\n"
            "Or use the Join Giveaway button from your group.",
            parse_mode="HTML",
        )
        return

    gdata = _get_giveaway(group_chat_id)
    if not gdata or not gdata.get("active"):
        await msg.reply_text("⚠️ No active giveaway found for that group.")
        return

    tdata = _get_user_task(user.id, group_chat_id)
    tasks = await _verify_all_tasks(context.bot, user.id, group_chat_id)
    text = _tasks_text(tasks, tdata)
    kb = _task_keyboard(group_chat_id, user.id)
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ─── Callback Handler ────────────────────────────────────────────────────────

async def giveaway_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    caller = query.from_user
    if not caller:
        return

    parts = data.split(":")
    if len(parts) < 3:
        return

    action = parts[0]
    try:
        target_uid = int(parts[1])
        chat_id = int(parts[2])
    except Exception:
        return

    if caller.id != target_uid:
        await query.answer("⚠️ This is not your giveaway session!", show_alert=True)
        return

    _set_user_active_chat(target_uid, chat_id)
    tdata = _get_user_task(target_uid, chat_id)

    # ── SUBMIT GROUP BUTTON ──────────────────────────────────────────────────
    if action == "gw_submit_group":
        await query.message.reply_text(
            "💬 <b>Group Verification Instructions:</b>\n\n"
            "Send this command in this chat:\n"
            "<code>/gwgroup @yourgroup</code>\n\n"
            "<i>(Replace <code>@yourgroup</code> with your group's @username or Chat ID where you added both @i_mikobot and @noahsongbot with admin permissions and 1000+ members)</i>",
            parse_mode="HTML",
        )
        return

    # ── VERIFY MY TASKS BUTTON ───────────────────────────────────────────────
    if action == "gw_verify":
        tasks = await _verify_all_tasks(context.bot, target_uid, chat_id)
        all_done = all(tasks.values())

        if not all_done:
            text = _tasks_text(tasks, tdata)
            kb = _task_keyboard(chat_id, target_uid)
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass

            missing = []
            if not tasks["miko_added"] or not tasks["noah_added"]:
                missing.append("• 1000+ Member Group with @i_mikobot & @noahsongbot as admins (use /gwgroup @group)")
            if not tasks["updates"]:
                missing.append("• Join @i_mikoo Updates Channel")
            if not tasks["network"]:
                missing.append("• Join @titanic_network Channel")

            alert_msg = "❌ Please complete the following tasks:\n" + "\n".join(missing)
            await query.answer(alert_msg[:200], show_alert=True)
            return

        # All 4 tasks completed -> Enroll in Giveaway
        gdata = _get_giveaway(chat_id)
        if not gdata or not gdata.get("active"):
            await query.answer("⚠️ The giveaway has already ended.", show_alert=True)
            return

        entries = gdata.get("entries", [])
        if any(e["user_id"] == target_uid for e in entries):
            await query.answer("✅ You are already enrolled in this giveaway!", show_alert=True)
            return

        username = caller.username or "N/A"
        name = caller.first_name or caller.username or f"User {caller.id}"
        entry = {
            "user_id": target_uid,
            "username": username,
            "name": name,
            "joined_at": datetime.utcnow().isoformat(),
        }
        entries.append(entry)
        gdata["entries"] = entries
        _set_giveaway(chat_id, gdata)

        # Lookup user's current economy wealth for confirmation
        try:
            ud = get_user(target_uid)
            wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        except Exception:
            wealth = 0

        prize_1 = gdata.get("prize_1", DEFAULT_PRIZE_1)
        prize_2 = gdata.get("prize_2", DEFAULT_PRIZE_2)

        success_text = (
            "🎊 <b>You're In!</b> 🎊\n\n"
            "✅ All 4 tasks verified successfully!\n"
            "🎟 You have been enrolled into the 7-day giveaway!\n\n"
            f"🥇 <b>1st Prize:</b> {html.escape(prize_1)}\n"
            f"🥈 <b>2nd Prize:</b> {html.escape(prize_2)}\n\n"
            f"💰 <b>Your Current Wealth:</b> <code>{wealth:,} Coins</code>\n"
            f"👥 <b>Total Verified Entries:</b> {len(entries)}\n\n"
            "🏆 <i>Reminder: The top richest players on the leaderboard win! Keep grinding coins!</i>"
        )
        try:
            await query.edit_message_text(success_text, parse_mode="HTML")
        except Exception:
            pass
        await query.answer("🎉 Enrolled successfully!", show_alert=True)

        # Notify Group Chat
        try:
            mention = f'<a href="tg://user?id={target_uid}">{html.escape(name)}</a>'
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎟 {mention} has verified all tasks and entered the giveaway!\n"
                    f"👥 Total verified entries: <b>{len(entries)}</b>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
