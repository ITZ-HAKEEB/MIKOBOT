"""
Giveaway System for Miko Bot
============================
Commands (owner/sudoers only):
  /giveaway create <prize>         — Create a new giveaway in this chat
  /giveaway setprize <prize>       — Update the prize description
  /giveaway end                    — Pick winner & close giveaway
  /giveaway cancel                 — Cancel giveaway without winner
  /giveaway info                   — View current giveaway status
  /giveaway entries                — List all participants

User commands:
  /join_giveaway  (or /gjoin)      — Start task verification flow (DM)
  /gcheck                          — Re-check task verification status

Giveaway Tasks to complete:
  1. Add @i_mikobot to a group with >1000 members
  2. Add @noahsongbot to a group with >1000 members
  3. Join @i_mikoo (updates channel)
  4. Join @titanic_network
"""

from __future__ import annotations

import json
import os
import html
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from modules.utils.db import get_mongo_db, get_redis_client, _sanitize_doc, _json_serial

# ─── channels & bots that users must be in / have added ─────────────────────
UPDATES_CHANNEL = "@i_mikoo"
NETWORK_CHANNEL = "@titanic_network"
MIKO_BOT_USERNAME = "i_mikobot"
NOAH_BOT_USERNAME = "noahsongbot"

# ─── minimum group member count for the "add bot" tasks ─────────────────────
MIN_GROUP_MEMBERS = 1000

# ─── Redis / Mongo helpers ───────────────────────────────────────────────────
_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "giveaway_data.json",
)


def _load() -> Dict[str, Any]:
    """Load giveaway data from file fallback."""
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


# ─── user task state ──────────────────────────────────────────────────────────

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


async def _get_bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Safely obtain the bot's username with fallback."""
    if context.bot:
        if getattr(context.bot, "username", None):
            return context.bot.username
        try:
            me = await context.bot.get_me()
            if me and me.username:
                return me.username
        except Exception:
            pass
    return "i_mikobot"


# ─── sudoer / owner check ─────────────────────────────────────────────────────

async def _is_owner_or_sudoer(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    from modules.utils.db import is_sudo_user
    if is_sudo_user(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


# ─── task verification helpers ────────────────────────────────────────────────

async def _check_channel_member(bot, user_id: int, channel: str) -> bool:
    """Return True if user is a member of the channel."""
    try:
        m = await bot.get_chat_member(channel, user_id)
        return m.status not in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT, "kicked")
    except Exception:
        return False


async def _verify_all_tasks(bot, user_id: int, chat_id: int) -> Dict[str, bool]:
    """
    Verify the 4 tasks. Tasks 1 & 2 (add bots to big groups) are
    self-reported — we store them in task-state; tasks 3 & 4 can be
    verified via the Telegram API.
    """
    tdata = _get_user_task(user_id, chat_id)

    t1 = bool(tdata.get("miko_added"))      # self-reported
    t2 = bool(tdata.get("noah_added"))      # self-reported
    t3 = await _check_channel_member(bot, user_id, UPDATES_CHANNEL)
    t4 = await _check_channel_member(bot, user_id, NETWORK_CHANNEL)

    return {"miko_added": t1, "noah_added": t2, "updates": t3, "network": t4}


def _task_keyboard(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Build the task instruction inline keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I added @i_mikobot to my group", callback_data=f"gw_miko:{user_id}:{chat_id}")],
        [InlineKeyboardButton("✅ I added @noahsongbot to my group", callback_data=f"gw_noah:{user_id}:{chat_id}")],
        [InlineKeyboardButton("📢 Join @i_mikoo Updates", url="https://t.me/i_mikoo")],
        [InlineKeyboardButton("🌐 Join @titanic_network", url="https://t.me/titanic_network")],
        [InlineKeyboardButton("🔍 Verify My Tasks", callback_data=f"gw_verify:{user_id}:{chat_id}")],
    ])


def _tasks_text(tasks: Dict[str, bool]) -> str:
    def tick(v):
        return "✅" if v else "❌"

    return (
        "📋 <b>Giveaway Tasks</b>\n\n"
        f"{tick(tasks['miko_added'])} Add <b>@i_mikobot</b> to a group with 1000+ members\n"
        f"{tick(tasks['noah_added'])} Add <b>@noahsongbot</b> to a group with 1000+ members\n"
        f"{tick(tasks['updates'])} Join <b>@i_mikoo</b> (Updates Channel)\n"
        f"{tick(tasks['network'])} Join <b>@titanic_network</b>\n\n"
        "Complete all 4 tasks and tap <b>🔍 Verify My Tasks</b>."
    )


# ─── /giveaway (owner command) ────────────────────────────────────────────────

async def cmd_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main giveaway management command for owner/sudoers."""
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    if chat.type == "private":
        await msg.reply_text(
            "⚠️ Giveaway commands must be used in a <b>group chat</b>.",
            parse_mode="HTML",
        )
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
                "Use /giveaway end or /giveaway cancel first.",
                parse_mode="HTML",
            )
            return

        prize = " ".join(args[1:]).strip() if len(args) > 1 else "🎁 Mystery Prize"
        gdata = {
            "chat_id": chat.id,
            "chat_title": chat.title or "Group",
            "prize": prize,
            "active": True,
            "created_by": user.id,
            "created_at": datetime.utcnow().isoformat(),
            "entries": [],   # list of {"user_id", "username", "name", "joined_at"}
        }
        _set_giveaway(chat.id, gdata)

        text = (
            "🎉 <b>GIVEAWAY STARTED!</b> 🎉\n\n"
            f"🏆 <b>Prize:</b> {html.escape(prize)}\n\n"
            "📋 <b>How to Join:</b>\n"
            "Complete these 4 tasks then use /join_giveaway\n\n"
            "1️⃣ Add <b>@i_mikobot</b> to a group with <b>1000+ members</b>\n"
            "2️⃣ Add <b>@noahsongbot</b> to a group with <b>1000+ members</b>\n"
            "3️⃣ Join <b>@i_mikoo</b> (Updates Channel)\n"
            "4️⃣ Join <b>@titanic_network</b>\n\n"
            "✨ After completing all tasks, tap the button below!"
        )
        bot_username = await _get_bot_username(context)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎟 Join Giveaway", url=f"https://t.me/{bot_username}?start=giveaway_{chat.id}")],
        ])
        await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # ── SET PRIZE ───────────────────────────────────────────────────────────
    if sub in ("setprize", "prize"):
        gdata = _get_giveaway(chat.id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway. Use /giveaway create <prize>")
            return
        if len(args) < 2:
            await msg.reply_text("Usage: /giveaway setprize <prize description>")
            return
        prize = " ".join(args[1:]).strip()
        gdata["prize"] = prize
        _set_giveaway(chat.id, gdata)
        await msg.reply_text(f"✅ Prize updated to: <b>{html.escape(prize)}</b>", parse_mode="HTML")
        return

    # ── END / PICK WINNER ───────────────────────────────────────────────────
    if sub == "end":
        gdata = _get_giveaway(chat.id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway to end.")
            return
        entries = gdata.get("entries", [])
        if not entries:
            await msg.reply_text(
                "🎁 Giveaway ended but <b>no one joined</b>. No winner picked.",
                parse_mode="HTML",
            )
            gdata["active"] = False
            _set_giveaway(chat.id, gdata)
            return

        winner = random.choice(entries)
        prize = gdata.get("prize", "🎁 Mystery Prize")
        winner_mention = f'<a href="tg://user?id={winner["user_id"]}">{html.escape(winner["name"])}</a>'

        text = (
            "🎊 <b>GIVEAWAY ENDED!</b> 🎊\n\n"
            f"🏆 <b>Prize:</b> {html.escape(prize)}\n\n"
            f"🥳 <b>Winner:</b> {winner_mention}\n"
            f"👤 @{winner.get('username', 'N/A')}\n\n"
            f"Total entries: <b>{len(entries)}</b>\n\n"
            "🎉 Congratulations to the lucky winner!"
        )
        gdata["active"] = False
        gdata["winner"] = winner
        gdata["ended_at"] = datetime.utcnow().isoformat()
        _set_giveaway(chat.id, gdata)
        await msg.reply_text(text, parse_mode="HTML")
        return

    # ── CANCEL ──────────────────────────────────────────────────────────────
    if sub == "cancel":
        gdata = _get_giveaway(chat.id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway to cancel.")
            return
        _del_giveaway(chat.id)
        await msg.reply_text("❌ Giveaway cancelled. No winner was picked.")
        return

    # ── ENTRIES ─────────────────────────────────────────────────────────────
    if sub == "entries":
        gdata = _get_giveaway(chat.id)
        if not gdata:
            await msg.reply_text("⚠️ No giveaway data found.")
            return
        entries = gdata.get("entries", [])
        if not entries:
            await msg.reply_text("📭 No entries yet.")
            return
        lines = [f"🎟 <b>Giveaway Entries ({len(entries)}):</b>\n"]
        for i, e in enumerate(entries, 1):
            lines.append(f"{i}. <a href=\"tg://user?id={e['user_id']}\">{html.escape(e['name'])}</a> (@{e.get('username', 'N/A')})")
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return

    # ── INFO (default) ───────────────────────────────────────────────────────
    gdata = _get_giveaway(chat.id)
    if not gdata:
        await msg.reply_text(
            "ℹ️ No active giveaway.\n\nUse <code>/giveaway create &lt;prize&gt;</code> to start one!",
            parse_mode="HTML",
        )
        return

    status = "🟢 Active" if gdata.get("active") else "🔴 Ended"
    entries = gdata.get("entries", [])
    prize = gdata.get("prize", "N/A")
    winner_info = ""
    if not gdata.get("active") and gdata.get("winner"):
        w = gdata["winner"]
        winner_info = f"\n🏆 <b>Winner:</b> <a href=\"tg://user?id={w['user_id']}\">{html.escape(w['name'])}</a>"

    text = (
        f"🎉 <b>Giveaway Info</b>\n\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🏆 <b>Prize:</b> {html.escape(prize)}\n"
        f"👥 <b>Entries:</b> {len(entries)}"
        f"{winner_info}"
    )
    await msg.reply_text(text, parse_mode="HTML")


# ─── /join_giveaway (user command) ───────────────────────────────────────────

async def cmd_join_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Let users initiate giveaway entry.
    Works in group (redirects to DM for verification) and in private (shows tasks).
    """
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    # Determine target group
    # If called from group → use that group. If from DM → look for deeplink param.
    if chat.type != "private":
        group_chat_id = chat.id
        gdata = _get_giveaway(group_chat_id)
        if not gdata or not gdata.get("active"):
            await msg.reply_text("⚠️ No active giveaway in this group.")
            return

        # Check if already entered
        entries = gdata.get("entries", [])
        already = any(e["user_id"] == user.id for e in entries)
        if already:
            await msg.reply_text("✅ You are already enrolled in the giveaway!", parse_mode="HTML")
            return

        bot_username = await _get_bot_username(context)
        bot_link = f"https://t.me/{bot_username}?start=giveaway_{group_chat_id}"
        await msg.reply_text(
            "🎟 <b>Join Giveaway</b>\n\n"
            "Click below to verify your tasks in private and get enrolled!\n\n"
            "<i>Complete all 4 tasks to qualify.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Verify Tasks (Private)", url=bot_link)]
            ]),
            parse_mode="HTML",
        )
        return

    # ── DM flow (can come from /start giveaway_<chat_id> deep link) ──────────
    group_chat_id = None
    if context.args:
        param = context.args[0]
        if param.startswith("giveaway_"):
            try:
                group_chat_id = int(param.split("_", 1)[1])
            except Exception:
                pass

    if not group_chat_id:
        await msg.reply_text(
            "⚠️ Please use /join_giveaway in the group where the giveaway is running,\n"
            "or click the bot link shared in the group."
        )
        return

    gdata = _get_giveaway(group_chat_id)
    if not gdata or not gdata.get("active"):
        await msg.reply_text("⚠️ No active giveaway found for that group.")
        return

    # Check if already entered
    entries = gdata.get("entries", [])
    already = any(e["user_id"] == user.id for e in entries)
    if already:
        await msg.reply_text("✅ You are already enrolled in the giveaway! 🎉")
        return

    tasks = await _verify_all_tasks(context.bot, user.id, group_chat_id)
    text = _tasks_text(tasks)
    kb = _task_keyboard(group_chat_id, user.id)
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ─── /gcheck command ─────────────────────────────────────────────────────────

async def cmd_gcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-verify tasks in DM."""
    msg = update.message
    if not msg:
        return
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if chat.type != "private":
        await msg.reply_text("💌 Use this command in my DM to re-verify your giveaway tasks.")
        return

    # Find which giveaway they are trying to join
    # Look up by user task data — store last group_chat_id
    # We look at args or user-task data
    if context.args:
        try:
            group_chat_id = int(context.args[0])
        except Exception:
            group_chat_id = None
    else:
        group_chat_id = None

    if not group_chat_id:
        await msg.reply_text(
            "⚠️ Please specify the group ID: /gcheck <group_id>\n"
            "Or use the Join Giveaway button from your group."
        )
        return

    gdata = _get_giveaway(group_chat_id)
    if not gdata or not gdata.get("active"):
        await msg.reply_text("⚠️ No active giveaway found for that group.")
        return

    tasks = await _verify_all_tasks(context.bot, user.id, group_chat_id)
    text = _tasks_text(tasks)
    kb = _task_keyboard(group_chat_id, user.id)
    await msg.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ─── Callback handler ────────────────────────────────────────────────────────

async def giveaway_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles:
      gw_miko:<user_id>:<chat_id>   — self-report miko bot added
      gw_noah:<user_id>:<chat_id>   — self-report noah bot added
      gw_verify:<user_id>:<chat_id> — verify all & enroll if done
    """
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

    tdata = _get_user_task(target_uid, chat_id)

    if action == "gw_miko":
        tdata["miko_added"] = True
        _set_user_task(target_uid, chat_id, tdata)
        tasks = await _verify_all_tasks(context.bot, target_uid, chat_id)
        text = _tasks_text(tasks)
        kb = _task_keyboard(chat_id, target_uid)
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer("✅ Marked @i_mikobot as added!", show_alert=False)
        return

    if action == "gw_noah":
        tdata["noah_added"] = True
        _set_user_task(target_uid, chat_id, tdata)
        tasks = await _verify_all_tasks(context.bot, target_uid, chat_id)
        text = _tasks_text(tasks)
        kb = _task_keyboard(chat_id, target_uid)
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await query.answer("✅ Marked @noahsongbot as added!", show_alert=False)
        return

    if action == "gw_verify":
        tasks = await _verify_all_tasks(context.bot, target_uid, chat_id)
        all_done = all(tasks.values())

        if not all_done:
            text = _tasks_text(tasks)
            kb = _task_keyboard(chat_id, target_uid)
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            await query.answer(
                "❌ Please complete all 4 tasks first!", show_alert=True
            )
            return

        # All tasks done — enroll in giveaway
        gdata = _get_giveaway(chat_id)
        if not gdata or not gdata.get("active"):
            await query.answer("⚠️ The giveaway has ended.", show_alert=True)
            return

        entries = gdata.get("entries", [])
        already = any(e["user_id"] == target_uid for e in entries)
        if already:
            await query.answer("✅ You're already enrolled!", show_alert=True)
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

        success_text = (
            "🎊 <b>You're In!</b>\n\n"
            f"✅ All tasks verified!\n"
            f"🎟 You have been enrolled in the giveaway!\n\n"
            f"🏆 <b>Prize:</b> {html.escape(gdata.get('prize', '🎁 Mystery Prize'))}\n"
            f"👥 <b>Total Entries:</b> {len(entries)}\n\n"
            "🍀 Good luck! Winner will be picked by the bot owner."
        )
        try:
            await query.edit_message_text(success_text, parse_mode="HTML")
        except Exception:
            pass
        await query.answer("🎉 Enrolled successfully!", show_alert=True)

        # Notify the group
        try:
            mention = f'<a href="tg://user?id={target_uid}">{html.escape(name)}</a>'
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎟 {mention} has joined the giveaway! ({len(entries)} entries so far)",
                parse_mode="HTML",
            )
        except Exception:
            pass
