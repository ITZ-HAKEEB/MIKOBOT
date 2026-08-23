from __future__ import annotations

import os
import asyncio
from typing import Optional

from telegram import Update
from telegram.error import Forbidden, BadRequest, RetryAfter
from telegram.ext import ContextTypes

from modules.utils.db import get_chats, get_user_chats, rm_chat, rm_user_chat

broadcasting_lock = asyncio.Lock()

OWNER_IDS = {6605051662, 5971488185, 7810795240}


def is_sudo(user_id: int) -> bool:
    env_owner = os.getenv("OWNER_ID")
    if env_owner and env_owner.isdigit() and int(env_owner) == user_id:
        return True
    return user_id in OWNER_IDS


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_sudo(user.id):
        # Also allow if user is global richest or sudoer, or check permission
        await update.message.reply_text("🚫 Only Bot Owner / Sudoers can broadcast!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "💡 <b>Broadcast Usage:</b>\n\n"
            "Reply to a message with:\n"
            "• <code>/broadcast</code> — Broadcast forwarded to all groups\n"
            "• <code>/broadcast -copy</code> — Broadcast copy without forward tag\n"
            "• <code>/broadcast -user</code> — Include all private DM users\n"
            "• <code>/broadcast -nochat</code> — Send ONLY to private users\n\n"
            "Alias: <code>/gcast</code>",
            parse_mode="HTML",
        )
        return

    if broadcasting_lock.locked():
        await update.message.reply_text("⚠️ A broadcast is already running! Please wait.")
        return

    msg = update.message.reply_to_message
    args = context.args or []
    command_text = " ".join(args).lower()

    copy_mode = "-copy" in command_text
    include_users = "-user" in command_text
    no_chat = "-nochat" in command_text

    groups_list = set() if no_chat else set(get_chats())
    users_list = set(get_user_chats()) if include_users else set()

    # Also add current group if not present
    if update.effective_chat and update.effective_chat.type != "private" and not no_chat:
        groups_list.add(update.effective_chat.id)
    if update.effective_user and include_users:
        users_list.add(update.effective_user.id)

    all_targets = list(groups_list | users_list)
    if not all_targets:
        await update.message.reply_text("❌ No active chats or users found in database to broadcast to.")
        return

    sent_status = await update.message.reply_text(
        f"⏳ <b>Starting Broadcast...</b>\n\n"
        f"👥 Groups: {len(groups_list)}\n"
        f"👤 Users: {len(users_list)}\n"
        f"Total Targets: {len(all_targets)}",
        parse_mode="HTML",
    )

    count = 0
    ucount = 0
    failed_file: Optional[str] = None
    failed_handle = None

    async with broadcasting_lock:
        for chat_id in all_targets:
            try:
                if copy_mode:
                    await context.bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id,
                        reply_markup=msg.reply_markup,
                    )
                else:
                    await context.bot.forward_message(
                        chat_id=chat_id,
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id,
                    )

                if chat_id in groups_list:
                    count += 1
                else:
                    ucount += 1

                await asyncio.sleep(0.15)

            except RetryAfter as ra:
                await asyncio.sleep(ra.retry_after + 5)
            except Forbidden:
                if chat_id in groups_list:
                    rm_chat(chat_id)
                else:
                    rm_user_chat(chat_id)
                continue
            except BadRequest as br:
                err_text = str(br).lower()
                if "chat not found" in err_text or "peer_id_invalid" in err_text or "kicked" in err_text:
                    if chat_id in groups_list:
                        rm_chat(chat_id)
                    else:
                        rm_user_chat(chat_id)
                else:
                    if not failed_handle:
                        failed_file = "broadcast_errors.txt"
                        failed_handle = open(failed_file, "w")
                    failed_handle.write(f"{chat_id} - {br}\n")
                continue
            except Exception as ex:
                if not failed_handle:
                    failed_file = "broadcast_errors.txt"
                    failed_handle = open(failed_file, "w")
                failed_handle.write(f"{chat_id} - {ex}\n")
                continue

    result_text = (
        f"📢 <b>Broadcast Completed!</b>\n\n"
        f"👥 Groups: <b>{count}</b>\n"
        f"👤 Users: <b>{ucount}</b>\n"
        f"📊 Total Sent: <b>{count + ucount}</b>"
    )

    if failed_handle:
        failed_handle.close()
        try:
            with open(failed_file, "rb") as doc_file:
                await update.message.reply_document(
                    document=doc_file,
                    caption=result_text,
                    parse_mode="HTML",
                )
            os.remove(failed_file)
        except Exception:
            pass

    try:
        await sent_status.edit_text(result_text, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(result_text, parse_mode="HTML")
