from __future__ import annotations

import os
import time
import html as html_lib
from typing import Optional
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

LOG_GROUP_ID = os.getenv("LOG_GROUP_ID", "-1004381844703")


def get_log_group_id() -> Optional[int]:
    try:
        val = os.getenv("LOG_GROUP_ID", LOG_GROUP_ID)
        return int(val)
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


async def send_fund_approval_log(
    bot: Bot,
    user_id: int,
    user_name: str,
    amount: float,
    req_id: Optional[str] = None,
    method: str = "Razorpay.me / UPI",
    notes: str = ""
):
    """Sends an approval request to the Log Group with Accept and Reject buttons."""
    log_id = get_log_group_id()
    if not log_id:
        print("⚠️ No LOG_GROUP_ID configured for fund approval log.")
        return

    if not req_id:
        req_id = str(int(time.time()))[-6:]

    safe_name = html_lib.escape(user_name or f"User {user_id}")
    time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    text = (
        f"💳 <b>[ADD FUND APPROVAL REQUEST]</b>\n\n"
        f"👤 <b>User:</b> <a href=\"tg://user?id={user_id}\">{safe_name}</a>\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"💵 <b>Amount:</b> <b>₹{amount:,.2f} INR</b>\n"
        f"🏷️ <b>Gateway:</b> {html_lib.escape(method)}\n"
        f"🔑 <b>Request ID:</b> <code>REQ-{req_id}</code>\n"
        f"⏰ <b>Timestamp:</b> <code>{time_str}</code>\n"
    )
    if notes:
        text += f"📝 <b>Note:</b> {html_lib.escape(notes)}\n"

    text += (
        f"\n<i>⚡ Admins, verify payment on Razorpay and click Accept or Reject below:</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ ACCEPT & CREDIT (₹{amount:g})",
                callback_data=f"fund_acc:{user_id}:{amount}:{req_id}"
            ),
            InlineKeyboardButton(
                "❌ REJECT",
                callback_data=f"fund_rej:{user_id}:{amount}:{req_id}"
            )
        ]
    ])

    try:
        await bot.send_message(
            chat_id=log_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        print(f"✅ Sent Fund Approval Request for User {user_id} (₹{amount}) to Log Group {log_id}")
    except Exception as e:
        print(f"⚠️ Failed to send fund approval log to {log_id}: {e}")

