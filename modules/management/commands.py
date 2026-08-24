from __future__ import annotations

import os
import json
import re
import html as html_lib
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List

from telegram import (
    Update,
    User,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes

from modules.utils.storage import get_user, get_all_users

MGMT_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "group_management.json"
)


def _load_mgmt_data() -> Dict[str, Any]:
    if not os.path.exists(MGMT_DATA_FILE):
        return {}
    try:
        with open(MGMT_DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_mgmt_data(data: Dict[str, Any]) -> None:
    try:
        with open(MGMT_DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _get_group_mgmt(chat_id: int) -> Dict[str, Any]:
    data = _load_mgmt_data()
    cid = str(chat_id)
    if cid not in data:
        data[cid] = {"warns": {}, "baka_promoted": []}
        _save_mgmt_data(data)
    return data[cid]


def _save_group_mgmt(chat_id: int, gdata: Dict[str, Any]) -> None:
    data = _load_mgmt_data()
    data[str(chat_id)] = gdata
    _save_mgmt_data(data)


async def _is_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except Exception:
        return False


def _parse_time(time_str: str) -> Optional[timedelta]:
    if not time_str:
        return None
    time_str = time_str.lower().strip()
    match = re.match(r"^(\d+)([smhd])$", time_str)
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s":
        return timedelta(seconds=val)
    elif unit == "m":
        return timedelta(minutes=val)
    elif unit == "h":
        return timedelta(hours=val)
    elif unit == "d":
        return timedelta(days=val)
    return None


async def _resolve_target(
    update: Update, context: ContextTypes.DEFAULT_TYPE, args: List[str]
) -> Tuple[Optional[int], Optional[str], List[str]]:
    replied = update.message.reply_to_message if update.message else None
    if replied and replied.from_user:
        target_id = replied.from_user.id
        target_name = replied.from_user.first_name or replied.from_user.username or "User"
        return target_id, target_name, args

    if not args:
        return None, None, []

    first_arg = args[0].strip()
    remaining_args = args[1:]

    # Numeric user_id
    if first_arg.lstrip("-").isdigit():
        target_id = int(first_arg)
        ud = get_user(target_id)
        name = ud.get("display_name") or ud.get("username") or f"User {target_id}"
        return target_id, name, remaining_args

    # Username @...
    if first_arg.startswith("@"):
        uname = first_arg[1:].lower()
        all_u = get_all_users()
        for uid, udata in all_u.items():
            if str(udata.get("username", "")).lower() == uname:
                name = udata.get("display_name") or udata.get("username") or first_arg
                return int(uid), name, remaining_args
        return None, first_arg, remaining_args

    return None, None, args


# --- COMMAND IMPLEMENTATIONS ---


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, is_dban: bool = False):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        await update.message.reply_text("🛡️ This command can only be used in groups!")
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .ban <reply/username/userid>")
        return

    if await _is_admin(chat.id, target_id, context):
        await update.message.reply_text("❌ Cannot ban an admin!")
        return

    try:
        await context.bot.ban_chat_member(chat.id, target_id)
        if is_dban and update.message.reply_to_message:
            try:
                await update.message.reply_to_message.delete()
            except Exception:
                pass
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(f"🔨 Banned {mention} from the group!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to ban: {e}")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .unban <reply/username/userid>")
        return

    try:
        await context.bot.unban_chat_member(chat.id, target_id, only_if_banned=True)
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(f"✅ Unbanned {mention}!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unban: {e}")


async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .kick <reply/username/userid>")
        return

    if await _is_admin(chat.id, target_id, context):
        await update.message.reply_text("❌ Cannot kick an admin!")
        return

    try:
        await context.bot.ban_chat_member(chat.id, target_id)
        await context.bot.unban_chat_member(chat.id, target_id)
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(f"👢 Kicked {mention} from the group!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to kick: {e}")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE, is_dmute: bool = False):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, remaining_args = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .mute <user> [time (e.g. 30m, 2h)]")
        return

    if await _is_admin(chat.id, target_id, context):
        await update.message.reply_text("❌ Cannot mute an admin!")
        return

    time_str = remaining_args[0] if remaining_args else None
    td = _parse_time(time_str) if time_str else None
    until_date = datetime.utcnow() + td if td else None

    try:
        await context.bot.restrict_chat_member(
            chat.id,
            target_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
        if is_dmute and update.message.reply_to_message:
            try:
                await update.message.reply_to_message.delete()
            except Exception:
                pass

        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        duration_text = f"for {time_str}" if td else "indefinitely"
        await update.message.reply_text(f"🔇 Muted {mention} {duration_text}!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute: {e}")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .unmute <reply/username/userid>")
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id,
            target_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_polls=True,
                can_invite_users=True,
            ),
        )
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(f"🔊 Unmuted {mention}!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unmute: {e}")


async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .warn <reply/username/userid>")
        return

    if await _is_admin(chat.id, target_id, context):
        await update.message.reply_text("❌ Cannot warn an admin!")
        return

    gdata = _get_group_mgmt(chat.id)
    warns = gdata.get("warns", {})
    t_id_str = str(target_id)
    current_warns = warns.get(t_id_str, 0) + 1
    mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'

    if current_warns >= 3:
        warns[t_id_str] = 0
        gdata["warns"] = warns
        _save_group_mgmt(chat.id, gdata)
        try:
            await context.bot.ban_chat_member(chat.id, target_id)
            await update.message.reply_text(
                f"🚫 {mention} reached 3/3 warnings and has been banned!",
                parse_mode="HTML",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to ban after 3 warns: {e}")
    else:
        warns[t_id_str] = current_warns
        gdata["warns"] = warns
        _save_group_mgmt(chat.id, gdata)
        await update.message.reply_text(
            f"⚠️ Warned {mention}! ({current_warns}/3 warnings)",
            parse_mode="HTML",
        )


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        target_id = update.effective_user.id
        target_name = update.effective_user.first_name or "You"

    gdata = _get_group_mgmt(chat.id)
    current_warns = gdata.get("warns", {}).get(str(target_id), 0)
    mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
    await update.message.reply_text(
        f"📊 {mention} has <b>{current_warns}/3</b> warnings.",
        parse_mode="HTML",
    )


async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .unwarn <reply/username/userid>")
        return

    gdata = _get_group_mgmt(chat.id)
    warns = gdata.get("warns", {})
    t_id_str = str(target_id)
    current_warns = max(0, warns.get(t_id_str, 0) - 1)
    warns[t_id_str] = current_warns
    gdata["warns"] = warns
    _save_group_mgmt(chat.id, gdata)

    mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
    await update.message.reply_text(
        f"✅ Removed 1 warning for {mention}! ({current_warns}/3 warnings left)",
        parse_mode="HTML",
    )


async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, remaining_args = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .promote <user> [0/1/2/3]")
        return

    level = 1
    if remaining_args and remaining_args[0].isdigit():
        level = int(remaining_args[0])

    try:
        if level == 0:
            await context.bot.promote_chat_member(
                chat.id,
                target_id,
                can_manage_chat=True,
                can_pin_messages=True,
            )
        elif level == 1:
            await context.bot.promote_chat_member(
                chat.id,
                target_id,
                can_manage_chat=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
            )
        elif level == 2:
            await context.bot.promote_chat_member(
                chat.id,
                target_id,
                can_manage_chat=True,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=True,
            )
        else:
            await context.bot.promote_chat_member(
                chat.id,
                target_id,
                can_manage_chat=True,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=True,
                can_manage_video_chats=True,
            )

        gdata = _get_group_mgmt(chat.id)
        baka_promoted = gdata.get("baka_promoted", [])
        if target_id not in baka_promoted:
            baka_promoted.append(target_id)
            gdata["baka_promoted"] = baka_promoted
            _save_group_mgmt(chat.id, gdata)

        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(f"⭐ Promoted {mention} to Admin (Tier {level})!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to promote: {e}")


async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, _ = await _resolve_target(update, context, args)
    if not target_id:
        await update.message.reply_text("⚠️ Usage: .demote <user>")
        return

    try:
        await context.bot.promote_chat_member(
            chat.id,
            target_id,
            can_manage_chat=False,
            can_change_info=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False,
            can_manage_video_chats=False,
        )

        gdata = _get_group_mgmt(chat.id)
        baka_promoted = gdata.get("baka_promoted", [])
        if target_id in baka_promoted:
            baka_promoted.remove(target_id)
            gdata["baka_promoted"] = baka_promoted
            _save_group_mgmt(chat.id, gdata)

        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(f"🔽 Demoted {mention} from Admin!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to demote: {e}")


async def cmd_demote_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    gdata = _get_group_mgmt(chat.id)
    baka_promoted = list(gdata.get("baka_promoted", []))
    if not baka_promoted:
        await update.message.reply_text("ℹ️ No bot-promoted admins found to demote.")
        return

    count = 0
    for uid in baka_promoted:
        try:
            await context.bot.promote_chat_member(
                chat.id,
                uid,
                can_manage_chat=False,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_manage_video_chats=False,
            )
            count += 1
        except Exception:
            pass

    gdata["baka_promoted"] = []
    _save_group_mgmt(chat.id, gdata)
    await update.message.reply_text(f"🔽 Demoted {count} Miko-promoted admins!")


async def cmd_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, remaining_args = await _resolve_target(update, context, args)
    if not target_id or not remaining_args:
        await update.message.reply_text("⚠️ Usage: .title <user> <custom_title>")
        return

    new_title = " ".join(remaining_args)[:16]
    try:
        await context.bot.set_chat_administrator_custom_title(chat.id, target_id, new_title)
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        await update.message.reply_text(
            f"🏷️ Title for {mention} set to: <b>{html_lib.escape(new_title)}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to set title: {e}")


async def cmd_res(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, remaining_args = await _resolve_target(update, context, args)
    if not target_id or not remaining_args:
        await update.message.reply_text("⚠️ Usage: .res <user> +-<power_name>\nPowers: messages, media, polls, links, invites, pin, info")
        return

    power_str = remaining_args[0].lower()
    enable = not power_str.startswith("-")
    power = power_str.lstrip("+-")

    perm_kwargs: Dict[str, bool] = {}
    if power in ("messages", "msg"):
        perm_kwargs["can_send_messages"] = enable
    elif power in ("media", "photos", "videos"):
        perm_kwargs["can_send_media_messages"] = enable
    elif power in ("polls", "poll"):
        perm_kwargs["can_send_polls"] = enable
    elif power in ("links", "link", "web"):
        perm_kwargs["can_add_web_page_previews"] = enable
    elif power in ("invites", "invite"):
        perm_kwargs["can_invite_users"] = enable
    elif power in ("pin", "pins"):
        perm_kwargs["can_pin_messages"] = enable
    elif power in ("info", "changeinfo"):
        perm_kwargs["can_change_info"] = enable
    else:
        await update.message.reply_text("⚠️ Unknown power! Use: messages, media, polls, links, invites, pin, info")
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id,
            target_id,
            permissions=ChatPermissions(**perm_kwargs),
        )
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        status = "Granted" if enable else "Restricted"
        await update.message.reply_text(f"🛡️ {status} <b>{power}</b> for {mention}!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to restrict: {e}")


async def cmd_add_power(update: Update, context: ContextTypes.DEFAULT_TYPE, is_remove: bool = False):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    args = context.args or []
    target_id, target_name, remaining_args = await _resolve_target(update, context, args)
    if not target_id or not remaining_args:
        action = ".remove" if is_remove else ".add"
        await update.message.reply_text(f"⚠️ Usage: {action} <user> <power>\nPowers: delete, ban, restrict, invite, pin, promote, info")
        return

    power = remaining_args[0].lower()
    flag = not is_remove
    kwargs: Dict[str, bool] = {}
    if power in ("delete", "del"):
        kwargs["can_delete_messages"] = flag
    elif power in ("ban", "kick"):
        kwargs["can_restrict_members"] = flag
    elif power in ("restrict", "mute"):
        kwargs["can_restrict_members"] = flag
    elif power in ("invite", "inv"):
        kwargs["can_invite_users"] = flag
    elif power in ("pin", "pins"):
        kwargs["can_pin_messages"] = flag
    elif power in ("promote", "prom"):
        kwargs["can_promote_members"] = flag
    elif power in ("info", "changeinfo"):
        kwargs["can_change_info"] = flag
    elif power in ("all", "full"):
        kwargs = {
            "can_manage_chat": True,
            "can_delete_messages": flag,
            "can_restrict_members": flag,
            "can_invite_users": flag,
            "can_pin_messages": flag,
            "can_promote_members": flag,
            "can_change_info": flag,
        }
    else:
        await update.message.reply_text("⚠️ Unknown power! Use: delete, ban, restrict, invite, pin, promote, info, all")
        return

    try:
        await context.bot.promote_chat_member(chat.id, target_id, **kwargs)
        mention = f'<a href="tg://user?id={target_id}">{html_lib.escape(target_name or "User")}</a>'
        act_word = "Removed" if is_remove else "Added"
        await update.message.reply_text(f"⭐ {act_word} admin power <b>{power}</b> for {mention}!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to update power: {e}")


async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    replied = update.message.reply_to_message
    if not replied:
        await update.message.reply_text("⚠️ Reply to a message to pin it: .pin")
        return

    try:
        await context.bot.pin_chat_message(chat.id, replied.message_id)
        await update.message.reply_text("📌 Message pinned successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to pin: {e}")


async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        await update.message.reply_text("🚫 You must be an admin to use this command!")
        return

    replied = update.message.reply_to_message
    msg_id = replied.message_id if replied else None
    try:
        await context.bot.unpin_chat_message(chat.id, msg_id)
        await update.message.reply_text("📌 Message unpinned!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unpin: {e}")


async def cmd_delete_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type == "private":
        return

    if not (await _is_admin(chat.id, user.id, context)):
        return

    replied = update.message.reply_to_message
    if not replied:
        return

    try:
        await replied.delete()
        await update.message.delete()
    except Exception:
        pass


async def cmd_mgmt_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✅ <b>Manage your group with some amazing group management commands of miko!</b>\n\n"
        "<code>.res &lt;user&gt; +-power_name</code> - restrict a member with given power\n\n"
        "<code>.add &lt;user&gt; &lt;power&gt;</code> - add given power for an admin\n"
        "<code>.remove &lt;user&gt; &lt;power&gt;</code> - remove given power for an admin\n\n"
        "<code>.promote &lt;user&gt; 0/1/2/3</code> - Promote user to admin\n"
        "<code>.demote &lt;user&gt;</code> - Demote admin\n\n"
        "<code>.demote_all</code> - demote all miko promoted admins\n\n"
        "<code>.title &lt;user&gt; &lt;title&gt;</code> - Set custom title\n\n"
        "<code>.warns &lt;user&gt;</code> - Get all warnings\n"
        "<code>.warn &lt;user&gt;</code> - Warn a user (3 = ban)\n"
        "<code>.unwarn &lt;user&gt;</code> - Remove 1 warning\n\n"
        "<code>.mute &lt;user&gt; 30m</code> - Mute temp/permanent\n"
        "<code>.dmute &lt;reply&gt; &lt;time&gt;</code> - delete replied message and mute user\n"
        "<code>.unmute &lt;user&gt;</code> - Unmute the user\n\n"
        "<code>.ban &lt;user&gt;</code> - Ban user\n"
        "<code>.dban &lt;reply&gt;</code> - delete replied msg and ban user\n"
        "<code>.unban &lt;user&gt;</code> - Unban user\n"
        "<code>.kick &lt;user&gt;</code> - Kick from group\n\n"
        "<code>.pin &lt;reply&gt;</code> - Pin replied message\n"
        "<code>.unpin</code> - Unpin the current message\n"
        "<code>.d</code> - delete a message\n"
        "<code>.help</code> - Show this help\n\n"
        "<b>Note:</b>\n"
        "  1) You can use <code>.</code> or <code>!</code> or <code>/</code> as prefix.\n"
        "  2) <code>&lt;user&gt;</code> = reply/username/userid"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Cʟɪᴄᴋ Hᴇʀᴇ Fᴏʀ Cᴏᴍᴍᴀɴᴅ Lɪꜱᴛ", url="https://t.me/i_mikoo/9")]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


# Helper dispatch for prefix . and ! messages
async def handle_prefix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    raw = msg.text.strip()
    if not (raw.startswith(".") or raw.startswith("!")):
        return

    prefix = raw[0]
    tokens = raw[1:].strip().split()
    if not tokens:
        return

    cmd = tokens[0].lower()
    context.args = tokens[1:]

    if cmd == "ban":
        await cmd_ban(update, context, is_dban=False)
    elif cmd == "dban":
        await cmd_ban(update, context, is_dban=True)
    elif cmd == "unban":
        await cmd_unban(update, context)
    elif cmd == "kick":
        await cmd_kick(update, context)
    elif cmd == "mute":
        await cmd_mute(update, context, is_dmute=False)
    elif cmd == "dmute":
        await cmd_mute(update, context, is_dmute=True)
    elif cmd == "unmute":
        await cmd_unmute(update, context)
    elif cmd == "warn":
        await cmd_warn(update, context)
    elif cmd == "warns":
        await cmd_warns(update, context)
    elif cmd == "unwarn":
        await cmd_unwarn(update, context)
    elif cmd == "promote":
        await cmd_promote(update, context)
    elif cmd == "demote":
        await cmd_demote(update, context)
    elif cmd == "demote_all":
        await cmd_demote_all(update, context)
    elif cmd == "title":
        await cmd_title(update, context)
    elif cmd == "res":
        await cmd_res(update, context)
    elif cmd == "add":
        await cmd_add_power(update, context, is_remove=False)
    elif cmd == "remove":
        await cmd_add_power(update, context, is_remove=True)
    elif cmd == "pin":
        await cmd_pin(update, context)
    elif cmd == "unpin":
        await cmd_unpin(update, context)
    elif cmd in ("d", "del", "delete"):
        await cmd_delete_msg(update, context)
    elif cmd in ("broadcast", "gcast"):
        from modules.management.broadcast import broadcast_cmd
        await broadcast_cmd(update, context)
    elif cmd in ("addsudo", "add_sudo"):
        from modules.management.sudo import addsudo_cmd
        await addsudo_cmd(update, context)
    elif cmd in ("delsudo", "rmsudo", "del_sudo"):
        from modules.management.sudo import delsudo_cmd
        await delsudo_cmd(update, context)
    elif cmd in ("sudolist", "sudos", "sudo_list"):
        from modules.management.sudo import sudolist_cmd
        await sudolist_cmd(update, context)
    elif cmd in ("help", "ghelp", "mgmt"):
        await cmd_mgmt_help(update, context)


from modules.management.broadcast import broadcast_cmd
from modules.management.sudo import addsudo_cmd, delsudo_cmd, sudolist_cmd, addprem_cmd, delprem_cmd, addfund_cmd

MANAGEMENT_COMMANDS = {
    "ban": lambda u, c: cmd_ban(u, c, is_dban=False),
    "dban": lambda u, c: cmd_ban(u, c, is_dban=True),
    "unban": cmd_unban,
    "kick": cmd_kick,
    "mute": lambda u, c: cmd_mute(u, c, is_dmute=False),
    "dmute": lambda u, c: cmd_mute(u, c, is_dmute=True),
    "unmute": cmd_unmute,
    "warn": cmd_warn,
    "warns": cmd_warns,
    "unwarn": cmd_unwarn,
    "promote": cmd_promote,
    "demote": cmd_demote,
    "demote_all": cmd_demote_all,
    "title": cmd_title,
    "res": cmd_res,
    "add": lambda u, c: cmd_add_power(u, c, is_remove=False),
    "remove": lambda u, c: cmd_add_power(u, c, is_remove=True),
    "pin": cmd_pin,
    "unpin": cmd_unpin,
    "d": cmd_delete_msg,
    "ghelp": cmd_mgmt_help,
    "broadcast": broadcast_cmd,
    "gcast": broadcast_cmd,
    "addsudo": addsudo_cmd,
    "delsudo": delsudo_cmd,
    "rmsudo": delsudo_cmd,
    "sudolist": sudolist_cmd,
    "sudos": sudolist_cmd,
    "addprem": addprem_cmd,
    "delprem": delprem_cmd,
    "giveprem": addprem_cmd,
    "addfund": addfund_cmd,
    "addfunds": addfund_cmd,
}
