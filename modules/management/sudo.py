from __future__ import annotations

import html as html_lib
from typing import Optional, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from modules.utils.db import (
    get_owner_id,
    add_sudo_user,
    rm_sudo_user,
    get_sudo_users,
    is_sudo_user,
)
from modules.utils.storage import get_user, get_all_users


def _is_bot_owner(user_id: int) -> bool:
    return user_id == get_owner_id()


async def _resolve_sudo_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[int], str]:
    replied = update.message.reply_to_message if update.message else None
    if replied and replied.from_user:
        target_user = replied.from_user
        name = target_user.first_name or target_user.username or "User"
        return target_user.id, name

    args = context.args or []
    if not args:
        return None, ""

    arg = args[0].strip()
    if arg.isdigit():
        uid = int(arg)
        u_info = get_user(uid)
        name = u_info.get("display_name") or u_info.get("username") or f"User {uid}"
        return uid, name

    if arg.startswith("@"):
        uname = arg[1:].lower()
        all_u = get_all_users()
        for uid_str, uinfo in all_u.items():
            if (uinfo.get("username") or "").lower() == uname:
                uid = int(uid_str)
                name = uinfo.get("display_name") or uinfo.get("username") or f"User {uid}"
                return uid, name

    return None, ""


async def addsudo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user
    if not caller or not _is_bot_owner(caller.id):
        await update.message.reply_text("🚫 Only the Bot Owner can add sudo users!")
        return

    target_id, target_name = await _resolve_sudo_target(update, context)
    if not target_id:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "• Reply to a user with <code>/addsudo</code>\n"
            "• Or type <code>/addsudo &lt;user_id|@username&gt;</code>",
            parse_mode="HTML",
        )
        return

    if is_sudo_user(target_id):
        await update.message.reply_text(
            f"ℹ️ <b>{html_lib.escape(target_name)}</b> (<code>{target_id}</code>) is already a Sudoer!",
            parse_mode="HTML",
        )
        return

    add_sudo_user(target_id)
    await update.message.reply_text(
        f"✅ <b>Added to Sudoers!</b>\n\n"
        f"👤 <b>Name:</b> {html_lib.escape(target_name)}\n"
        f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        f"👑 Granted full broadcast and sudo privileges.",
        parse_mode="HTML",
    )


async def delsudo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user
    if not caller or not _is_bot_owner(caller.id):
        await update.message.reply_text("🚫 Only the Bot Owner can remove sudo users!")
        return

    target_id, target_name = await _resolve_sudo_target(update, context)
    if not target_id:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "• Reply to a user with <code>/delsudo</code>\n"
            "• Or type <code>/delsudo &lt;user_id|@username&gt;</code>",
            parse_mode="HTML",
        )
        return

    if target_id == get_owner_id():
        await update.message.reply_text("❌ Cannot remove the primary Bot Owner from Sudoers!")
        return

    rm_sudo_user(target_id)
    await update.message.reply_text(
        f"🗑️ <b>Removed from Sudoers!</b>\n\n"
        f"👤 <b>Name:</b> {html_lib.escape(target_name)}\n"
        f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        f"🚫 Sudo privileges revoked.",
        parse_mode="HTML",
    )


async def sudolist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user
    if not caller or not is_sudo_user(caller.id):
        await update.message.reply_text("🚫 Only Sudoers can view the Sudoers list!")
        return

    owner_id = get_owner_id()
    sudo_ids = get_sudo_users()

    lines = ["👑 <b>Miko Sudoers & Owner List:</b>\n"]
    lines.append(f"<b>⭐️ Owner:</b> <code>{owner_id}</code>")

    lines.append("\n<b>⚡ Sudo Users:</b>")
    idx = 1
    for sid in sudo_ids:
        if sid == owner_id:
            continue
        u_info = get_user(sid)
        name = u_info.get("display_name") or u_info.get("username") or f"User {sid}"
        mention = f'<a href="tg://user?id={sid}">{html_lib.escape(name)}</a>'
        lines.append(f"{idx}. {mention} (<code>{sid}</code>)")
        idx += 1

    if idx == 1:
        lines.append("<i>No extra sudo users added yet.</i>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def addprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner / Sudo command to instantly grant VIP Premium & Free Gems"""
    caller = update.effective_user
    if not caller or not is_sudo_user(caller.id):
        await update.message.reply_text("🚫 Only Bot Owner / Sudoers can grant VIP Premium!")
        return

    target_id, target_name = await _resolve_sudo_target(update, context)
    if not target_id:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/addprem &lt;user_id|@username&gt; [months]</code>", parse_mode="HTML")
        return

    months = 1
    args = context.args or []
    if len(args) > 1 and args[1].isdigit():
        req_m = int(args[1])
        if req_m in [1, 2, 3, 6, 12]:
            months = req_m

    gems_map = {1: 1.0, 2: 2.0, 3: 3.0, 6: 6.0, 12: 12.0}
    free_gems = gems_map.get(months, 1.0)

    ud = get_user(target_id)
    new_gems = round(ud.get("gems", 0.0) + free_gems, 2)
    update_user(target_id, premium=True, gems=new_gems)

    days = months * 30 if months != 12 else 365
    msg = (
        f"👑 <b>VIP Pʀᴇᴍɪᴜᴍ Aᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
        f"👤 <b>User:</b> {html_lib.escape(target_name)}\n"
        f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        f"⏳ <b>Duration:</b> {months} Month(s) ({days} Days)\n"
        f"💎 <b>Bonus Gems Credited:</b> +{int(free_gems)} 💎\n"
        f"✨ <b>Total Gems Balance:</b> {new_gems} 💎\n"
        f"🌟 <b>Status:</b> Active & Verified"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def delprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner / Sudo command to revoke VIP Premium"""
    caller = update.effective_user
    if not caller or not is_sudo_user(caller.id):
        await update.message.reply_text("🚫 Only Bot Owner / Sudoers can revoke VIP Premium!")
        return

    target_id, target_name = await _resolve_sudo_target(update, context)
    if not target_id:
        await update.message.reply_text("⚠️ <b>Usage:</b> <code>/delprem &lt;user_id|@username&gt;</code>", parse_mode="HTML")
        return

    update_user(target_id, premium=False)
    await update.message.reply_text(
        f"🚫 <b>VIP Premium Revoked!</b>\n\n"
        f"👤 <b>User:</b> {html_lib.escape(target_name)}\n"
        f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        f"❌ User is now back to Normal tier.",
        parse_mode="HTML"
    )
