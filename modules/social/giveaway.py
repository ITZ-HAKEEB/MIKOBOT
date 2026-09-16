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
  3. Add @Lilyy_music_bot to a group with 10000+ members (and make bot Admin)
  4. Join @i_mikoo (Updates Channel)
  5. Join @titanic_network (Network Channel)

User Commands:
  /join_giveaway (or /gjoin)       — Open giveaway panel with live tasks (works in every group and DM)
  /gcheck                          — Re-check task status / open giveaway panel
  /gwgroup <@group or ID>          — Verify 1000+ / 10000+ member groups with bot admins (works in DM & groups)

Admin Commands:
  /giveaway create [p1 | p2]       — Start 7-day giveaway in group or global
  /giveaway setprize <p1> | <p2>   — Update prize descriptions
  /giveaway end                    — End giveaway now & announce winners
  /giveaway cancel                 — Cancel giveaway
  /giveaway info                   — View status, remaining time & entries
  /giveaway entries                — List all enrolled participants
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

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
from modules.utils.logger import get_log_group_id, send_log_message
from modules.utils.storage import get_user, global_rank

logger = logging.getLogger(__name__)

# ─── Channels & Bots ─────────────────────────────────────────────────────────
UPDATES_CHANNEL = "@i_mikoo"
NETWORK_CHANNEL = "@titanic_network"
MIKO_BOT_USERNAME = "i_mikobot"
NOAH_BOT_USERNAME = "noahsongbot"
LILYY_BOT_USERNAME = "Lilyy_music_bot"

MIN_GROUP_MEMBERS = 1000
MIN_LILYY_GROUP_MEMBERS = 10000
GIVEAWAY_DURATION_DAYS = 7

# ─── Default Prizes & Links ──────────────────────────────────────────────────
DEFAULT_PRIZE_1 = "FAKE TAG ID : @Usa_fake_tag_id"
DEFAULT_PRIZE_1_URL = "https://t.me/Usa_fake_tag_id"

DEFAULT_PRIZE_2 = "@Giveaway_gc this group"
DEFAULT_PRIZE_2_URL = "https://t.me/Giveaway_gc"

GLOBAL_GIVEAWAY_ID = "global"

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


def _get_giveaway(chat_id: Any) -> Optional[Dict[str, Any]]:
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


def _set_giveaway(chat_id: Any, gdata: Dict[str, Any]) -> None:
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


def _del_giveaway(chat_id: Any) -> None:
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


def _get_or_create_global_giveaway() -> Dict[str, Any]:
    """Retrieves or initializes the global giveaway so it is always active."""
    gdata = _get_giveaway(GLOBAL_GIVEAWAY_ID)
    if gdata and gdata.get("active"):
        return gdata

    created_at = datetime.utcnow()
    ends_at = created_at + timedelta(days=GIVEAWAY_DURATION_DAYS)

    entries = []
    if gdata and isinstance(gdata.get("entries"), list) and gdata.get("active") is not False:
        entries = gdata.get("entries", [])

    gdata = {
        "chat_id": GLOBAL_GIVEAWAY_ID,
        "chat_title": "Miko Global Giveaway",
        "prize_1": (gdata.get("prize_1") if gdata else None) or DEFAULT_PRIZE_1,
        "prize_1_url": (gdata.get("prize_1_url") if gdata else None) or DEFAULT_PRIZE_1_URL,
        "prize_2": (gdata.get("prize_2") if gdata else None) or DEFAULT_PRIZE_2,
        "prize_2_url": (gdata.get("prize_2_url") if gdata else None) or DEFAULT_PRIZE_2_URL,
        "active": True,
        "created_at": created_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "entries": entries,
    }
    _set_giveaway(GLOBAL_GIVEAWAY_ID, gdata)
    return gdata


def get_effective_giveaway(chat_id: Optional[Any] = None) -> Tuple[Dict[str, Any], str]:
    """
    Returns (giveaway_dict, giveaway_id).
    If chat_id has an active giveaway, uses that.
    Otherwise defaults to the bot-wide Global Giveaway.
    """
    if chat_id and str(chat_id) != GLOBAL_GIVEAWAY_ID:
        gdata = _get_giveaway(chat_id)
        if gdata and gdata.get("active"):
            return gdata, str(chat_id)
    gdata = _get_or_create_global_giveaway()
    return gdata, GLOBAL_GIVEAWAY_ID


# ─── User Task State ─────────────────────────────────────────────────────────

def _get_user_task(user_id: int, chat_id: Any = GLOBAL_GIVEAWAY_ID) -> Dict[str, Any]:
    cid = str(chat_id) if chat_id else GLOBAL_GIVEAWAY_ID
    key = f"miko:gtask:{user_id}:{cid}"
    doc = None
    r = get_redis_client()
    if r:
        try:
            val = r.get(key)
            if val:
                doc = json.loads(val)
        except Exception:
            pass
    if not doc:
        db = get_mongo_db()
        if db is not None:
            try:
                found = db.giveaway_tasks.find_one({"_id": key})
                if found:
                    found.pop("_id", None)
                    doc = found
            except Exception:
                pass
    doc = doc or {}

    # Mirror group verification from global if local doesn't have it yet
    if cid != GLOBAL_GIVEAWAY_ID:
        g_doc = _get_user_task(user_id, GLOBAL_GIVEAWAY_ID)
        if not doc.get("miko_added") and g_doc.get("miko_added"):
            doc["miko_added"] = True
            doc["verified_group_id"] = g_doc.get("verified_group_id")
            doc["verified_group_title"] = g_doc.get("verified_group_title")
            doc["verified_member_count"] = g_doc.get("verified_member_count")
        if not doc.get("noah_added") and g_doc.get("noah_added"):
            doc["noah_added"] = True
        if not doc.get("lilyy_added") and g_doc.get("lilyy_added"):
            doc["lilyy_added"] = True
            doc["verified_lilyy_group_id"] = g_doc.get("verified_lilyy_group_id")
            doc["verified_lilyy_group_title"] = g_doc.get("verified_lilyy_group_title")
            doc["verified_lilyy_member_count"] = g_doc.get("verified_lilyy_member_count")

    return doc


def _set_user_task(user_id: int, chat_id: Any, tdata: Dict[str, Any]) -> None:
    cid = str(chat_id) if chat_id else GLOBAL_GIVEAWAY_ID
    key = f"miko:gtask:{user_id}:{cid}"
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

    # Save to global as well if any group verification was completed
    if (tdata.get("miko_added") or tdata.get("noah_added") or tdata.get("lilyy_added")) and cid != GLOBAL_GIVEAWAY_ID:
        g_key = f"miko:gtask:{user_id}:{GLOBAL_GIVEAWAY_ID}"
        g_tdata = _get_user_task(user_id, GLOBAL_GIVEAWAY_ID)
        g_tdata.update({k: v for k, v in tdata.items() if v is not None})
        g_serialized = json.dumps(g_tdata, default=_json_serial)
        if r:
            try:
                r.set(g_key, g_serialized)
            except Exception:
                pass
        if db is not None:
            try:
                db.giveaway_tasks.update_one({"_id": g_key}, {"$set": g_tdata}, upsert=True)
            except Exception:
                pass


def _get_user_active_chat(user_id: int) -> Optional[str]:
    """Retrieve the giveaway chat_id the user is currently interacting with."""
    r = get_redis_client()
    if r:
        try:
            val = r.get(f"miko:user_active_gw:{user_id}")
            if val:
                return val.decode("utf-8") if isinstance(val, bytes) else str(val)
        except Exception:
            pass
    return None


def _set_user_active_chat(user_id: int, chat_id: Any) -> None:
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

async def _is_owner_or_sudoer(user_id: int, chat_id: Any, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_sudo_user(user_id):
        return True
    if str(chat_id) == GLOBAL_GIVEAWAY_ID:
        return is_sudo_user(user_id)
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
    except Exception as e:
        logger.debug(f"Channel check failed for user {user_id} in {channel}: {e}")
        return False


async def _verify_group_for_user(
    bot,
    user_id: int,
    group_input: str,
    giveaway_chat_id: Any,
) -> Tuple[bool, str]:
    """
    Verifies that:
      1. Group exists and can be inspected.
      2. For Tasks 1 & 2: Group has >= 1,000 members and @i_mikobot & @noahsongbot are Admins.
      3. For Task 3: Group has >= 10,000 members and @Lilyy_music_bot is Admin.
    """
    raw = str(group_input).strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()

    if raw.startswith("+") or "joinchat" in raw:
        return False, "⚠️ Please provide a public <b>@username</b> or <b>Chat ID</b> (private invite links cannot be inspected)."

    if not raw.startswith("-") and not raw.startswith("@") and not raw.isdigit():
        group_identifier: Union[int, str] = f"@{raw}"
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
        return False, f"❌ Could not find group <code>{html.escape(str(group_identifier))}</code>.\nPlease make sure bot is added there first!"

    if chat.type not in ("group", "supergroup"):
        return False, f"❌ <b>{html.escape(chat.title or 'This chat')}</b> is not a group/supergroup!"

    # 1. Member count check
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0

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
    noah_admin = any(
        (a.user.username and a.user.username.lower() == NOAH_BOT_USERNAME.lower())
        for a in admins
    )
    lilyy_admin = any(
        (a.user.username and a.user.username.lower() == LILYY_BOT_USERNAME.lower())
        for a in admins
    )

    tdata = _get_user_task(user_id, giveaway_chat_id)
    verified_any = False
    details = []

    # Verify 1000+ member group with @i_mikobot & @noahsongbot
    if count >= MIN_GROUP_MEMBERS:
        if miko_admin:
            tdata["miko_added"] = True
            verified_any = True
        if noah_admin:
            tdata["noah_added"] = True
            verified_any = True
        if miko_admin or noah_admin:
            tdata["verified_group_id"] = chat.id
            tdata["verified_group_title"] = chat.title
            tdata["verified_member_count"] = count

    # Verify 10000+ member group with @Lilyy_music_bot
    if count >= MIN_LILYY_GROUP_MEMBERS:
        if lilyy_admin:
            tdata["lilyy_added"] = True
            tdata["verified_lilyy_group_id"] = chat.id
            tdata["verified_lilyy_group_title"] = chat.title
            tdata["verified_lilyy_member_count"] = count
            verified_any = True

    _set_user_task(user_id, giveaway_chat_id, tdata)

    def tick(v):
        return "✅" if v else "❌"

    res_lines = [
        f"🏷 <b>Group Checked:</b> {html.escape(chat.title)} (<b>{count:,} members</b>)\n",
        f"<b>Group Admin Status:</b>",
        f"{tick(miko_admin)} <b>@{MIKO_BOT_USERNAME}:</b> Admin (Req: 1,000+ members)",
        f"{tick(noah_admin)} <b>@{NOAH_BOT_USERNAME}:</b> Admin (Req: 1,000+ members)",
        f"{tick(lilyy_admin)} <b>@{LILYY_BOT_USERNAME}:</b> Admin (Req: 10,000+ members)\n",
    ]

    if count < MIN_GROUP_MEMBERS:
        res_lines.append(f"⚠️ Group has {count:,} members. Minimum required is 1,000+ members (and 10,000+ for @{LILYY_BOT_USERNAME}).")
    elif count < MIN_LILYY_GROUP_MEMBERS:
        if lilyy_admin:
            res_lines.append(f"⚠️ Note: Group has {count:,} members. @{LILYY_BOT_USERNAME} requires a group with <b>10,000+ members</b>!")

    if verified_any:
        res_lines.append("✨ Task progress has been updated!")
        return True, "\n".join(res_lines)
    else:
        res_lines.append("❌ No new tasks could be verified for this group.")
        return False, "\n".join(res_lines)


async def _verify_all_tasks(bot, user_id: int, chat_id: Any = GLOBAL_GIVEAWAY_ID) -> Dict[str, bool]:
    tdata = _get_user_task(user_id, chat_id)
    t1 = bool(tdata.get("miko_added"))
    t2 = bool(tdata.get("noah_added"))
    t3 = bool(tdata.get("lilyy_added"))
    if not (t1 and t2 and t3) and str(chat_id) != GLOBAL_GIVEAWAY_ID:
        g_tdata = _get_user_task(user_id, GLOBAL_GIVEAWAY_ID)
        if not t1:
            t1 = bool(g_tdata.get("miko_added"))
        if not t2:
            t2 = bool(g_tdata.get("noah_added"))
        if not t3:
            t3 = bool(g_tdata.get("lilyy_added"))

    t4 = await _check_channel_member(bot, user_id, UPDATES_CHANNEL)
    t5 = await _check_channel_member(bot, user_id, NETWORK_CHANNEL)
    return {"miko_added": t1, "noah_added": t2, "lilyy_added": t3, "updates": t4, "network": t5}


# ─── Log Group Notification ──────────────────────────────────────────────────

async def _send_giveaway_join_log(
    bot,
    user_id: int,
    username: str,
    first_name: str,
    gdata: Dict[str, Any],
    tdata: Dict[str, Any],
    chat_info: Optional[str] = None,
):
    """Sends a rich notification to LOG_GROUP_ID when a user completes tasks and joins."""
    try:
        ud = get_user(user_id)
        wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        rank = global_rank(user_id, "balance")

        user_mention = f'<a href="tg://user?id={user_id}">{html.escape(first_name or f"User {user_id}")}</a>'
        username_str = f"@{username}" if username and username != "N/A" else "None"
        total_entries = len(gdata.get("entries", []))

        group_name = tdata.get("verified_group_title", "N/A")
        group_id = tdata.get("verified_group_id", "N/A")
        group_count = tdata.get("verified_member_count", MIN_GROUP_MEMBERS)

        lilyy_group_name = tdata.get("verified_lilyy_group_title", group_name)
        lilyy_group_id = tdata.get("verified_lilyy_group_id", group_id)
        lilyy_group_count = tdata.get("verified_lilyy_member_count", MIN_LILYY_GROUP_MEMBERS)

        time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        log_text = (
            f"🎁 <b>[GIVEAWAY ENTRY VERIFIED &amp; JOINED]</b> 🎁\n\n"
            f"👤 <b>Participant:</b> {user_mention}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🏷 <b>Username:</b> {username_str}\n"
            f"💰 <b>Current Wealth:</b> <code>{wealth:,} Coins</code>\n"
            f"🏆 <b>Leaderboard Rank:</b> <code>#{rank}</code>\n"
        )
        if chat_info:
            log_text += f"📍 <b>Joined From:</b> {html.escape(chat_info)}\n"

        log_text += (
            f"\n📋 <b>Verified Tasks:</b>\n"
            f"  ✅ 1,000+ Group: <b>{html.escape(str(group_name))}</b> (<code>{group_id}</code> | {group_count:,} members)\n"
            f"  ✅ Bots Promoted: @{MIKO_BOT_USERNAME} &amp; @{NOAH_BOT_USERNAME} (Admin)\n"
            f"  ✅ 10,000+ Group: <b>{html.escape(str(lilyy_group_name))}</b> (<code>{lilyy_group_id}</code> | {lilyy_group_count:,} members)\n"
            f"  ✅ Bot Promoted: @{LILYY_BOT_USERNAME} (Admin)\n"
            f"  ✅ Updates Channel: {UPDATES_CHANNEL}\n"
            f"  ✅ Network Channel: {NETWORK_CHANNEL}\n\n"
            f"👥 <b>Total Verified Entries:</b> <b>{total_entries}</b>\n"
            f"⏰ <b>Timestamp:</b> <code>{time_str}</code>"
        )
        await send_log_message(bot, log_text, parse_mode="HTML")
        logger.info(f"✅ Sent giveaway join log for user {user_id} to log group.")
    except Exception as e:
        logger.error(f"Failed to send giveaway join log: {e}")


# ─── Keyboards & Text ────────────────────────────────────────────────────────

def _task_keyboard(
    chat_id: Any,
    user_id: int,
    bot_username: str = MIKO_BOT_USERNAME,
    in_group: bool = False,
    is_joined: bool = False,
) -> InlineKeyboardMarkup:
    cid = str(chat_id)
    if is_joined:
        buttons = [
            [InlineKeyboardButton("🔄 Refresh Status", callback_data=f"gw_refresh:{user_id}:{cid}")],
            [
                InlineKeyboardButton("🥇 1st Prize", url=DEFAULT_PRIZE_1_URL),
                InlineKeyboardButton("🥈 2nd Prize", url=DEFAULT_PRIZE_2_URL),
            ],
        ]
        if in_group:
            buttons.append([InlineKeyboardButton("💬 Open in DM", url=f"https://t.me/{bot_username}?start=giveaway_{cid}")])
        return InlineKeyboardMarkup(buttons)

    buttons = [
        [InlineKeyboardButton("🔗 Verify Group(s)", callback_data=f"gw_submit_group:{user_id}:{cid}")],
        [
            InlineKeyboardButton("📢 Join @i_mikoo", url="https://t.me/i_mikoo"),
            InlineKeyboardButton("🌐 Join @titanic_network", url="https://t.me/titanic_network"),
        ],
        [InlineKeyboardButton("🔍 Verify My Tasks & Join", callback_data=f"gw_verify:{user_id}:{cid}")],
    ]
    if in_group:
        buttons.append([InlineKeyboardButton("💬 Open in DM", url=f"https://t.me/{bot_username}?start=giveaway_{cid}")])
    return InlineKeyboardMarkup(buttons)


def _tasks_text(
    tasks: Dict[str, bool],
    tdata: Optional[Dict[str, Any]] = None,
    gdata: Optional[Dict[str, Any]] = None,
    user_wealth: Optional[int] = None,
    user_rank: Optional[int] = None,
    is_enrolled: bool = False,
    user_name: Optional[str] = None,
) -> str:
    def tick(v):
        return "✅" if v else "❌"

    tdata = tdata or {}
    gdata = gdata or {}
    prize_1 = gdata.get("prize_1", DEFAULT_PRIZE_1)
    prize_1_url = gdata.get("prize_1_url", DEFAULT_PRIZE_1_URL)
    prize_2 = gdata.get("prize_2", DEFAULT_PRIZE_2)
    prize_2_url = gdata.get("prize_2_url", DEFAULT_PRIZE_2_URL)
    entries_count = len(gdata.get("entries", []))

    time_remaining = ""
    if gdata.get("ends_at"):
        try:
            ends_at = datetime.fromisoformat(gdata["ends_at"])
            delta = ends_at - datetime.utcnow()
            if delta.total_seconds() > 0:
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                time_remaining = f"{days}d {hours}h {minutes}m remaining"
            else:
                time_remaining = "Ending soon..."
        except Exception:
            pass

    if is_enrolled:
        wealth_str = f"{user_wealth:,} Coins" if user_wealth is not None else "N/A"
        rank_str = f"#{user_rank}" if user_rank is not None else "N/A"
        name_str = html.escape(user_name or "Participant")
        return (
            "🎉 <b>MIKO OFFICIAL GIVEAWAY</b> 🎉\n\n"
            "✅ <b>GIVEAWAY JOINED &amp; VERIFIED!</b>\n\n"
            f"👤 <b>Participant:</b> {name_str}\n"
            f"💰 <b>Your Wealth:</b> <code>{wealth_str}</code> (Rank: <code>{rank_str}</code>)\n"
            f"👥 <b>Total Entries:</b> <b>{entries_count}</b>\n\n"
            f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>\n"
            f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>\n"
            f"⏳ <b>Duration:</b> 7 Days ({time_remaining})\n\n"
            "🏆 <i>Reminder: The richest players on the leaderboard at the end of 7 days win the prizes! Keep grinding coins!</i>"
        )

    group_info = ""
    if tdata.get("verified_group_title"):
        group_info = f"\n   <i>(Verified: {html.escape(tdata['verified_group_title'])})</i>"

    lilyy_info = ""
    if tdata.get("verified_lilyy_group_title"):
        lilyy_info = f"\n   <i>(Verified: {html.escape(tdata['verified_lilyy_group_title'])})</i>"

    all_done = all(tasks.values())
    status_hint = "✨ <b>All tasks complete! Tap Verify My Tasks &amp; Join!</b>" if all_done else "👉 <i>Complete all tasks and tap <b>Verify My Tasks &amp; Join</b>!</i>"

    return (
        "🎉 <b>MIKO OFFICIAL GIVEAWAY</b> 🎉\n\n"
        f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>\n"
        f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>\n"
        f"⏳ <b>Duration:</b> 7 Days ({time_remaining})\n"
        f"👥 <b>Total Verified Entries:</b> {entries_count}\n"
        "🏆 <b>Winner Rule:</b> Top Rich Players on Leaderboard Win!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📋 <b>REQUIRED TASKS TO JOIN:</b>\n\n"
        f"{tick(tasks['miko_added'])} 1️⃣ Add <b>@{MIKO_BOT_USERNAME}</b> to a group with <b>1,000+ members</b> (Admin){group_info}\n"
        f"{tick(tasks['noah_added'])} 2️⃣ Add <b>@{NOAH_BOT_USERNAME}</b> to a group with <b>1,000+ members</b> (Admin)\n"
        f"{tick(tasks['lilyy_added'])} 3️⃣ Add <b>@{LILYY_BOT_USERNAME}</b> to a group with <b>10,000+ members</b> (Admin){lilyy_info}\n"
        f"{tick(tasks['updates'])} 4️⃣ Join <b>{UPDATES_CHANNEL}</b> (Updates Channel)\n"
        f"{tick(tasks['network'])} 5️⃣ Join <b>{NETWORK_CHANNEL}</b> (Network Channel)\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <i>To verify group(s), send:</i>\n"
        "<code>/gwgroup @yourgroup</code>\n\n"
        f"{status_hint}"
    )


# ─── End Giveaway & Announce Leaderboard Winners ──────────────────────────────

async def end_giveaway_and_announce(bot, chat_id: Any) -> Tuple[bool, str]:
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
        if str(chat_id) != GLOBAL_GIVEAWAY_ID:
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except Exception:
                pass
        await send_log_message(bot, f"🎁 <b>[GIVEAWAY ENDED]</b>\nChat: {chat_id}\nNo verified participants joined.")
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

    # Post to chat if group chat
    if str(chat_id) != GLOBAL_GIVEAWAY_ID:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=result_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as err:
            logger.error(f"Failed to send giveaway results to group {chat_id}: {err}")

    # Always log results to LOG GROUP
    log_results = f"🏆 <b>[GIVEAWAY WINNERS ANNOUNCED]</b>\nChat/Scope: <code>{chat_id}</code>\n\n{result_text}"
    await send_log_message(bot, log_results, parse_mode="HTML")

    return True, result_text


# ─── Periodic Monitor for 7-Day Expirations ──────────────────────────────────

async def check_all_expired_giveaways(bot) -> None:
    """Checks for active giveaways that exceeded their 7-day duration."""
    chat_ids_to_check = set()
    chat_ids_to_check.add(GLOBAL_GIVEAWAY_ID)

    r = get_redis_client()
    if r:
        try:
            active_ids = r.smembers("miko:active_giveaways")
            for cid in active_ids:
                if isinstance(cid, bytes):
                    cid = cid.decode("utf-8")
                chat_ids_to_check.add(cid)
        except Exception:
            pass

    db = get_mongo_db()
    if db is not None:
        try:
            for doc in db.giveaways.find({"active": True}, {"_id": 1}):
                chat_ids_to_check.add(str(doc["_id"]))
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
                logger.info(f"Giveaway in scope {cid} expired after 7 days. Auto-ending...")
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


# ─── /join_giveaway (User Entry Command: Works in Every Group & DM) ─────────

async def cmd_join_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Global command to open the giveaway panel with tasks.
    Works in EVERY group chat and private DM!
    """
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    in_group = (chat.type != "private")
    bot_username = await _get_bot_username(context)

    # Determine giveaway scope
    target_chat_id = None
    if context.args and not in_group:
        param = context.args[0]
        if param.startswith("giveaway_"):
            try:
                target_chat_id = param.split("_", 1)[1]
            except Exception:
                pass
        elif param == "giveaway":
            target_chat_id = GLOBAL_GIVEAWAY_ID

    if not target_chat_id:
        if in_group:
            target_chat_id = chat.id
        else:
            target_chat_id = _get_user_active_chat(user.id) or GLOBAL_GIVEAWAY_ID

    gdata, gw_id = get_effective_giveaway(target_chat_id)
    _set_user_active_chat(user.id, gw_id)

    entries = gdata.get("entries", [])
    is_enrolled = any(e["user_id"] == user.id for e in entries)

    tasks = await _verify_all_tasks(context.bot, user.id, gw_id)
    tdata = _get_user_task(user.id, gw_id)

    ud = get_user(user.id)
    wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
    rank = global_rank(user.id, "balance")

    text = _tasks_text(
        tasks=tasks,
        tdata=tdata,
        gdata=gdata,
        user_wealth=wealth,
        user_rank=rank,
        is_enrolled=is_enrolled,
        user_name=user.first_name or user.username,
    )
    kb = _task_keyboard(
        chat_id=gw_id,
        user_id=user.id,
        bot_username=bot_username,
        in_group=in_group,
        is_joined=is_enrolled,
    )
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)


# ─── /gwgroup (Verify Group(s): Works in DM & Groups) ──────────────────────

async def cmd_gwgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Direct command for user to verify the group they added the bots to.
    Usage: /gwgroup <@group or ID>
    Works in DM and every group chat! If called inside a group without args,
    automatically checks the current group!
    """
    msg = update.message
    if not msg:
        return
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    in_group = (chat.type != "private")
    args = context.args or []

    # If called inside a group with no arguments, inspect current group
    if not args and in_group:
        group_input = str(chat.id)
    elif args:
        group_input = args[0]
    else:
        bot_username = await _get_bot_username(context)
        await msg.reply_text(
            "📋 <b>Group Verification Usage:</b>\n\n"
            "<code>/gwgroup @yourgroup</code>\n\n"
            "• Replace <code>@yourgroup</code> with your group's @username or Chat ID\n"
            "• For Tasks 1 &amp; 2: Group must have at least <b>1,000 members</b> with <b>@i_mikobot</b> &amp; <b>@noahsongbot</b> as Admins\n"
            f"• For Task 3: Group must have at least <b>10,000 members</b> with <b>@{LILYY_BOT_USERNAME}</b> as Admin\n\n"
            "💡 <i>Or send <code>/gwgroup</code> directly inside that group!</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Open in DM", url=f"https://t.me/{bot_username}?start=gwgroup")]
            ]) if in_group else None,
            parse_mode="HTML",
        )
        return

    giveaway_chat_id = _get_user_active_chat(user.id) or (chat.id if in_group else GLOBAL_GIVEAWAY_ID)
    status_msg = await msg.reply_text("🔍 <i>Checking group, member count, and bot admin permissions...</i>", parse_mode="HTML")

    success, response_text = await _verify_group_for_user(
        context.bot,
        user.id,
        group_input,
        giveaway_chat_id,
    )

    await status_msg.edit_text(response_text, parse_mode="HTML")

    if success:
        bot_username = await _get_bot_username(context)
        gdata, effective_gw_id = get_effective_giveaway(giveaway_chat_id)
        entries = gdata.get("entries", [])
        is_enrolled = any(e["user_id"] == user.id for e in entries)

        tasks = await _verify_all_tasks(context.bot, user.id, effective_gw_id)
        tdata = _get_user_task(user.id, effective_gw_id)

        ud = get_user(user.id)
        wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        rank = global_rank(user.id, "balance")

        # Auto-enroll if all 5 tasks are satisfied now!
        if all(tasks.values()) and not is_enrolled:
            username = user.username or "N/A"
            name = user.first_name or user.username or f"User {user.id}"
            entry = {
                "user_id": user.id,
                "username": username,
                "name": name,
                "joined_at": datetime.utcnow().isoformat(),
            }
            entries.append(entry)
            gdata["entries"] = entries
            _set_giveaway(effective_gw_id, gdata)
            is_enrolled = True

            # Send log group notification!
            chat_info = f"{chat.title} ({chat.id})" if in_group else "Private DM"
            await _send_giveaway_join_log(
                bot=context.bot,
                user_id=user.id,
                username=username,
                first_name=name,
                gdata=gdata,
                tdata=tdata,
                chat_info=chat_info,
            )

        text = _tasks_text(
            tasks=tasks,
            tdata=tdata,
            gdata=gdata,
            user_wealth=wealth,
            user_rank=rank,
            is_enrolled=is_enrolled,
            user_name=user.first_name or user.username,
        )
        kb = _task_keyboard(
            chat_id=effective_gw_id,
            user_id=user.id,
            bot_username=bot_username,
            in_group=in_group,
            is_joined=is_enrolled,
        )
        await msg.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)


# ─── /gcheck (Re-Check Tasks Command) ───────────────────────────────────────

async def cmd_gcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-check giveaway tasks and open updated panel. Works in DM and groups."""
    await cmd_join_giveaway(update, context)


# ─── Callback Handler ────────────────────────────────────────────────────────

async def giveaway_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    caller = query.from_user
    chat = update.effective_chat
    if not caller or not chat:
        return

    parts = data.split(":")
    action = parts[0]

    # Handle /start button or quick open
    if action == "gw_open":
        target_gw_id = parts[2] if len(parts) > 2 else GLOBAL_GIVEAWAY_ID
        gdata, effective_gw_id = get_effective_giveaway(target_gw_id)
        _set_user_active_chat(caller.id, effective_gw_id)

        bot_username = await _get_bot_username(context)
        entries = gdata.get("entries", [])
        is_enrolled = any(e["user_id"] == caller.id for e in entries)

        tasks = await _verify_all_tasks(context.bot, caller.id, effective_gw_id)
        tdata = _get_user_task(caller.id, effective_gw_id)

        ud = get_user(caller.id)
        wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        rank = global_rank(caller.id, "balance")

        in_group = (chat.type != "private")
        text = _tasks_text(
            tasks=tasks,
            tdata=tdata,
            gdata=gdata,
            user_wealth=wealth,
            user_rank=rank,
            is_enrolled=is_enrolled,
            user_name=caller.first_name or caller.username,
        )
        kb = _task_keyboard(
            chat_id=effective_gw_id,
            user_id=caller.id,
            bot_username=bot_username,
            in_group=in_group,
            is_joined=is_enrolled,
        )
        try:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass
        return

    if len(parts) < 3:
        return

    try:
        target_uid = int(parts[1])
        gw_id = str(parts[2])
    except Exception:
        return

    bot_username = await _get_bot_username(context)
    in_group = (chat.type != "private")
    effective_user_id = caller.id

    _set_user_active_chat(effective_user_id, gw_id)
    gdata, effective_gw_id = get_effective_giveaway(gw_id)

    # ── SUBMIT GROUP BUTTON ──────────────────────────────────────────────────
    if action == "gw_submit_group":
        instructions = (
            "💬 <b>Group Verification Instructions:</b>\n\n"
            f"1️⃣ Add <b>@{MIKO_BOT_USERNAME}</b> and <b>@{NOAH_BOT_USERNAME}</b> to a group with <b>1,000+ members</b> (Admin)\n"
            f"2️⃣ Add <b>@{LILYY_BOT_USERNAME}</b> to a group with <b>10,000+ members</b> (Admin)\n"
            "3️⃣ Send this command here (or inside that group):\n"
            "<code>/gwgroup @yourgroup</code>\n\n"
            "<i>(Replace <code>@yourgroup</code> with your group's @username or Chat ID)</i>"
        )
        if in_group:
            await query.answer("Check instructions sent!", show_alert=False)
            try:
                await query.message.reply_text(instructions, parse_mode="HTML")
            except Exception:
                pass
        else:
            await query.message.reply_text(instructions, parse_mode="HTML")
        return

    # ── REFRESH STATUS BUTTON ────────────────────────────────────────────────
    if action == "gw_refresh":
        ud = get_user(effective_user_id)
        wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        rank = global_rank(effective_user_id, "balance")
        entries = gdata.get("entries", [])
        is_enrolled = any(e["user_id"] == effective_user_id for e in entries)
        tasks = await _verify_all_tasks(context.bot, effective_user_id, effective_gw_id)
        tdata = _get_user_task(effective_user_id, effective_gw_id)

        text = _tasks_text(
            tasks=tasks,
            tdata=tdata,
            gdata=gdata,
            user_wealth=wealth,
            user_rank=rank,
            is_enrolled=is_enrolled,
            user_name=caller.first_name or caller.username,
        )
        kb = _task_keyboard(
            chat_id=effective_gw_id,
            user_id=effective_user_id,
            bot_username=bot_username,
            in_group=in_group,
            is_joined=is_enrolled,
        )
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            await query.answer("🔄 Status refreshed!", show_alert=False)
        except Exception:
            pass
        return

    # ── VERIFY MY TASKS & JOIN BUTTON ─────────────────────────────────────────
    if action == "gw_verify":
        entries = gdata.get("entries", [])

        # Check if user is already enrolled
        if any(e["user_id"] == effective_user_id for e in entries):
            await query.answer("✅ You are already enrolled in this giveaway!", show_alert=True)
            ud = get_user(effective_user_id)
            wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
            rank = global_rank(effective_user_id, "balance")
            tdata = _get_user_task(effective_user_id, effective_gw_id)
            tasks = await _verify_all_tasks(context.bot, effective_user_id, effective_gw_id)
            text = _tasks_text(
                tasks=tasks,
                tdata=tdata,
                gdata=gdata,
                user_wealth=wealth,
                user_rank=rank,
                is_enrolled=True,
                user_name=caller.first_name or caller.username,
            )
            kb = _task_keyboard(effective_gw_id, effective_user_id, bot_username, in_group, is_joined=True)
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                pass
            return

        # Check all 5 tasks
        tasks = await _verify_all_tasks(context.bot, effective_user_id, effective_gw_id)
        tdata = _get_user_task(effective_user_id, effective_gw_id)
        all_done = all(tasks.values())

        if not all_done:
            missing = []
            if not tasks["miko_added"] or not tasks["noah_added"]:
                missing.append("• 1,000+ Member Group with @i_mikobot & @noahsongbot as Admins (use /gwgroup @group)")
            if not tasks["lilyy_added"]:
                missing.append(f"• 10,000+ Member Group with @{LILYY_BOT_USERNAME} as Admin (use /gwgroup @group)")
            if not tasks["updates"]:
                missing.append(f"• Join {UPDATES_CHANNEL} Updates Channel")
            if not tasks["network"]:
                missing.append(f"• Join {NETWORK_CHANNEL} Channel")

            alert_msg = "❌ Incomplete tasks:\n" + "\n".join(missing)
            await query.answer(alert_msg[:200], show_alert=True)

            # Update panel if caller owns it or in DM
            if not in_group or caller.id == target_uid:
                text = _tasks_text(
                    tasks=tasks,
                    tdata=tdata,
                    gdata=gdata,
                    is_enrolled=False,
                    user_name=caller.first_name or caller.username,
                )
                kb = _task_keyboard(effective_gw_id, effective_user_id, bot_username, in_group, is_joined=False)
                try:
                    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
                except Exception:
                    pass
            return

        # ── ALL 5 TASKS COMPLETED! ENROLL USER ──────────────────────────────
        username = caller.username or "N/A"
        name = caller.first_name or caller.username or f"User {caller.id}"
        entry = {
            "user_id": effective_user_id,
            "username": username,
            "name": name,
            "joined_at": datetime.utcnow().isoformat(),
        }
        entries.append(entry)
        gdata["entries"] = entries
        _set_giveaway(effective_gw_id, gdata)

        ud = get_user(effective_user_id)
        wealth = int(ud.get("balance", 0)) + int(ud.get("wallet_balance", 0))
        rank = global_rank(effective_user_id, "balance")

        # 1. Update panel message
        text = _tasks_text(
            tasks=tasks,
            tdata=tdata,
            gdata=gdata,
            user_wealth=wealth,
            user_rank=rank,
            is_enrolled=True,
            user_name=name,
        )
        kb = _task_keyboard(effective_gw_id, effective_user_id, bot_username, in_group, is_joined=True)
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            pass

        await query.answer("🎉 Enrolled into giveaway successfully!", show_alert=True)

        # 2. SEND MESSAGE TO LOG GROUP
        chat_info = f"{chat.title} ({chat.id})" if in_group else "Private DM"
        await _send_giveaway_join_log(
            bot=context.bot,
            user_id=effective_user_id,
            username=username,
            first_name=name,
            gdata=gdata,
            tdata=tdata,
            chat_info=chat_info,
        )

        # 3. If in group, notify group chat
        if in_group:
            try:
                mention = f'<a href="tg://user?id={effective_user_id}">{html.escape(name)}</a>'
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        f"🎟 {mention} has verified all tasks and entered the giveaway!\n"
                        f"💰 Net Worth: <code>{wealth:,} Coins</code> (Rank: #{rank})\n"
                        f"👥 Total verified entries: <b>{len(entries)}</b>"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass


# ─── /giveaway (Admin / Management Command) ──────────────────────────────────

async def cmd_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    in_group = (chat.type != "private")
    target_gw_id = chat.id if in_group else GLOBAL_GIVEAWAY_ID

    args = context.args or []
    sub = args[0].lower() if args else "info"

    # Support /giveaway global <subcommand>
    if sub == "global" and len(args) > 1:
        target_gw_id = GLOBAL_GIVEAWAY_ID
        sub = args[1].lower()
        args = args[1:]

    # Check permissions
    if not await _is_owner_or_sudoer(user.id, target_gw_id, context):
        await msg.reply_text("🚫 Only the bot owner or group admins can manage giveaways!")
        return

    # ── CREATE ──────────────────────────────────────────────────────────────
    if sub == "create":
        existing = _get_giveaway(target_gw_id)
        if existing and existing.get("active"):
            await msg.reply_text(
                "⚠️ A giveaway is already running!\n"
                "Use <code>/giveaway end</code> or <code>/giveaway cancel</code> first.",
                parse_mode="HTML",
            )
            return

        prize_1 = DEFAULT_PRIZE_1
        prize_1_url = DEFAULT_PRIZE_1_URL
        prize_2 = DEFAULT_PRIZE_2
        prize_2_url = DEFAULT_PRIZE_2_URL

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
            "chat_id": target_gw_id,
            "chat_title": (chat.title or "Group") if in_group else "Global Miko Giveaway",
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
        _set_giveaway(target_gw_id, gdata)

        bot_username = await _get_bot_username(context)
        ends_at_str = ends_at.strftime("%Y-%m-%d %H:%M UTC")

        text = (
            "🎉 <b>GIVEAWAY STARTED!</b> 🎉\n\n"
            f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>\n"
            f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>\n\n"
            f"⏳ <b>Duration:</b> 7 Days (Ends: <code>{ends_at_str}</code>)\n"
            "🏆 <b>Winner Criteria:</b> Top Rich Players on Leaderboard!\n\n"
            "📋 <b>Tasks to Qualify:</b>\n"
            f"1️⃣ Add <b>@{MIKO_BOT_USERNAME}</b> to a group with <b>1,000+ members</b> (Admin)\n"
            f"2️⃣ Add <b>@{NOAH_BOT_USERNAME}</b> to a group with <b>1,000+ members</b> (Admin)\n"
            f"3️⃣ Add <b>@{LILYY_BOT_USERNAME}</b> to a group with <b>10,000+ members</b> (Admin)\n"
            f"4️⃣ Join <b>{UPDATES_CHANNEL}</b> (Updates Channel)\n"
            f"5️⃣ Join <b>{NETWORK_CHANNEL}</b>\n\n"
            "✨ Send <code>/join_giveaway</code> to complete tasks and enroll!"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🥇 1st Prize", url=prize_1_url)],
            [InlineKeyboardButton("🥈 2nd Prize", url=prize_2_url)],
            [InlineKeyboardButton("🎟 Join Giveaway", url=f"https://t.me/{bot_username}?start=giveaway_{target_gw_id}")],
        ])
        await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # ── SET PRIZE ───────────────────────────────────────────────────────────
    if sub in ("setprize", "prize"):
        gdata, effective_gw_id = get_effective_giveaway(target_gw_id)
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
        _set_giveaway(effective_gw_id, gdata)
        await msg.reply_text(
            f"✅ Prizes updated:\n"
            f"🥇 1st: <b>{html.escape(gdata.get('prize_1', 'N/A'))}</b>\n"
            f"🥈 2nd: <b>{html.escape(gdata.get('prize_2', 'N/A'))}</b>",
            parse_mode="HTML",
        )
        return

    # ── END / PICK WINNERS ──────────────────────────────────────────────────
    if sub == "end":
        success, text = await end_giveaway_and_announce(context.bot, target_gw_id)
        if not success:
            await msg.reply_text(text)
        return

    # ── CANCEL ──────────────────────────────────────────────────────────────
    if sub == "cancel":
        gdata = _get_giveaway(target_gw_id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway to cancel.")
            return
        _del_giveaway(target_gw_id)
        await msg.reply_text("❌ Giveaway cancelled. No winners were picked.")
        return

    # ── ENTRIES ─────────────────────────────────────────────────────────────
    if sub == "entries":
        gdata, _ = get_effective_giveaway(target_gw_id)
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
    gdata, effective_gw_id = get_effective_giveaway(target_gw_id)
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

    scope_title = "Global Giveaway" if effective_gw_id == GLOBAL_GIVEAWAY_ID else f"Group: {chat.title}"
    text = (
        f"🎉 <b>Giveaway Information ({scope_title})</b>\n\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🥇 <b>1st Prize:</b> <a href=\"{prize_1_url}\">{html.escape(prize_1)}</a>\n"
        f"🥈 <b>2nd Prize:</b> <a href=\"{prize_2_url}\">{html.escape(prize_2)}</a>\n"
        f"🏆 <b>Rule:</b> Top Rich Players on Leaderboard Win!{time_remaining}\n"
        f"👥 <b>Verified Entries:</b> {len(entries)}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 1st Prize", url=prize_1_url)],
        [InlineKeyboardButton("🥈 2nd Prize", url=prize_2_url)],
    ])
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")
