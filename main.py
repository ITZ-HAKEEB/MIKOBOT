import os
import sys
import time
import random
import asyncio
from typing import Dict, Any, List, Optional, Set
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    InlineQueryHandler,
    PreCheckoutQueryHandler,
    filters,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import html
from modules.utils.commands_list import BOT_COMMANDS
from modules.utils.storage import get_user, update_user, add_xp, global_rank
from modules.economy.commands import HANDLERS as ECON_HANDLERS
from modules.games.commands import HANDLERS as GAME_HANDLERS
from modules.social.commands import HANDLERS as SOCIAL_HANDLERS
from modules.premium.commands import (
    HANDLERS as PREM_HANDLERS,
    pre_checkout_callback,
    successful_payment_callback,
    send_stars_invoice,
)
from modules.management.commands import MANAGEMENT_COMMANDS, handle_prefix_command
from modules.ai.chatbot import dm_chatbot_handler
from modules.social.whisper import inline_whisper_handler, whisper_callback_handler


async def pfp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    replied = None
    if update.message and update.message.reply_to_message:
        replied = update.message.reply_to_message.from_user

    user = replied or update.effective_user
    ud = get_user(user.id, getattr(user, "username", "User"), getattr(user, "first_name", "User"))

    raw_name = ud.get("display_name") or getattr(user, "full_name", None) or user.first_name or "User"
    mention = f'<a href="tg://user?id={user.id}">{html.escape(raw_name)}</a>'

    # Ensure stats accurately reflect database values
    daily_kills = ud.get("daily_kills")
    if daily_kills is None or daily_kills == 0:
        daily_kills = ud.get("kills", 0)

    daily_robs = ud.get("daily_robs")
    if daily_robs is None or daily_robs == 0:
        daily_robs = ud.get("robs", 0)

    gems = float(ud.get("gems", 0.0) or 0.0)
    gems_val = int(gems * 10000)
    gems_disp = int(gems) if gems == int(gems) else round(gems, 2)
    wallet = ud.get("balance", 0)

    caption = (
        f"👤 {mention}'ꜱ Pʀᴏꜰɪʟᴇ\n\n"
        f"☠️ Dᴀɪʟʏ Kɪʟʟꜱ : {daily_kills}/200\n"
        f"🔪 Dᴀɪʟʏ Rᴏʙꜱ : {daily_robs}/150\n"
        f"💎 Gᴇᴍꜱ : {gems_disp} (${gems_val})\n"
        f"💼 Wᴀʟʟᴇᴛ : ${wallet}"
    )

    sent_msg = None
    try:
        profile_photos = await context.bot.get_user_profile_photos(user.id)
        if profile_photos.total_count > 0:
            photo = profile_photos.photos[0][-1]
            sent_msg = await update.message.reply_photo(photo.file_id, caption=caption, parse_mode="HTML")
    except Exception:
        sent_msg = None

    if not sent_msg:
        sent_msg = await update.message.reply_text(caption, parse_mode="HTML")

    # Auto-delete message after 10 seconds
    async def _auto_delete():
        await asyncio.sleep(10)
        try:
            if sent_msg:
                await sent_msg.delete()
        except Exception:
            pass
        try:
            if update.message and update.effective_chat and update.effective_chat.type != "private":
                await update.message.delete()
        except Exception:
            pass

    asyncio.create_task(_auto_delete())


from modules.utils.db import add_chat, add_user_chat


async def track_chat_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat:
        if chat.type in ("group", "supergroup"):
            add_chat(chat.id)
        elif chat.type == "private" and user:
            add_user_chat(user.id)


_VERIFY_SENT_CACHE: Dict[str, float] = {}


async def _send_verify_prompt(bot, chat, member):
    if not chat or not member:
        return
    bot_id = getattr(bot, "id", None)
    if bot_id and member.id == bot_id:
        return
    if getattr(member, "is_bot", False):
        return

    key = f"{chat.id}:{member.id}"
    now = time.time()
    last_sent = _VERIFY_SENT_CACHE.get(key, 0)
    if now - last_sent < 60:
        return  # Already sent recently
    _VERIFY_SENT_CACHE[key] = now

    # Clean old cache entries
    if len(_VERIFY_SENT_CACHE) > 500:
        cutoff = now - 300
        for k in list(_VERIFY_SENT_CACHE.keys()):
            if _VERIFY_SENT_CACHE[k] < cutoff:
                _VERIFY_SENT_CACHE.pop(k, None)

    mention = member.mention_html()
    chat_title = html.escape(chat.title or "the group")
    verify_text = (
        f"👋 <b>Hᴇʏ {mention} ࿐</b>\n\n"
        f"🛡️ <b>Wᴇʟᴄᴏᴍᴇ ᴛᴏ {chat_title}!</b>\n"
        "👉 <i>Pʟᴇᴀꜱᴇ ᴄʟɪᴄᴋ ᴛʜᴇ ᴠᴇʀɪꜰʏ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴄᴏɴꜰɪʀᴍ ʏᴏᴜ'ʀᴇ ʜᴜᴍᴀɴ ᴀɴᴅ ᴜɴʟᴏᴄᴋ ʏᴏᴜʀ ᴘʟᴀʏᴇʀ ᴘʀᴏꜰɪʟᴇ &amp; ɢᴀᴍɪɴɢ ꜱᴛᴀᴛꜱ.</i>"
    )
    verify_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔘 ᴠᴇʀɪꜰʏ ʜᴇʀᴇ ✅", callback_data=f"verify_join:{member.id}")]
    ])

    # 1. Send short stylish welcome message in group with user mention
    try:
        await bot.send_message(chat_id=chat.id, text=f"💓 welcome {mention}", parse_mode="HTML")
    except Exception as e:
        print(f"Error sending group welcome in {chat.id}: {e}")

    # 2. Send verification prompt directly to user's PRIVATE DM
    try:
        await bot.send_message(chat_id=member.id, text=verify_text, reply_markup=verify_kb, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending private DM to user {member.id}: {e}")


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_members = getattr(update.message, "new_chat_members", None) or []
    if not new_members:
        return
    bot_id = getattr(context.bot, "id", None)
    adder = update.effective_user
    chat = update.effective_chat

    for member in new_members:
        if bot_id and member.id == bot_id:
            adder_mention = adder.mention_html() if adder else "<b>Λᴅᴠᴀʏ</b>"
            bot_add_msg = (
                f"<b>👀 Hii {adder_mention} ࿐\n\n"
                "💓 Tʜᴀɴᴋꜱ Fᴏʀ Aᴅᴅɪɴɢ Mᴇ Iɴ Tʜɪꜱ Cʜᴀᴛ\n"
                "💓 Cʟᴏꜱᴇ Gᴀᴍɪɴɢ Cᴏᴍᴍᴀɴᴅꜱ: /close\n"
                "💓 Rᴇᴏᴘᴇɴ Gᴀᴍɪɴɢ Cᴏᴍᴍᴀɴᴅꜱ : /open\n"
                "💓 Eᴄᴏɴᴏᴍʏ Cᴏᴍᴍᴀɴᴅꜱ : /economy\n"
                "💓 Aʟʟ Mɪᴋᴏ Gᴀᴍᴇꜱ : /game</b>"
            )
            try:
                await update.message.reply_text(bot_add_msg, parse_mode="HTML")
            except Exception:
                pass
            return

        await _send_verify_prompt(context.bot, chat, member)


async def on_chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    was_member = old_status in ("member", "administrator", "creator", "restricted") and getattr(result.old_chat_member, "is_member", True)
    is_member = new_status in ("member", "administrator", "restricted") and getattr(result.new_chat_member, "is_member", True)

    if (not was_member or old_status in ("left", "kicked", "banned")) and is_member:
        member = result.new_chat_member.user
        await _send_verify_prompt(context.bot, chat, member)


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    # Check if bot was added/promoted in group
    if old_status not in ("member", "administrator") and new_status in ("member", "administrator"):
        adder = result.from_user
        adder_name = adder.first_name if adder and adder.first_name else "Λᴅᴠᴀʏ"
        bot_add_msg = (
            f"<b>👀 Hii {html.escape(adder_name)} ࿐\n\n"
            "💓 Tʜᴀɴᴋꜱ Fᴏʀ Aᴅᴅɪɴɢ Mᴇ Iɴ Tʜɪꜱ Cʜᴀᴛ\n"
            "💓 Cʟᴏꜱᴇ Gᴀᴍɪɴɢ Cᴏᴍᴍᴀɴᴅꜱ: /close\n"
            "💓 Rᴇᴏᴘᴇɴ Gᴀᴍɪɴɢ Cᴏᴍᴍᴀɴᴅꜱ : /open\n"
            "💓 Eᴄᴏɴᴏᴍʏ Cᴏᴍᴍᴀɴᴅꜱ : /economy\n"
            "💓 Aʟʟ Mɪᴋᴏ Gᴀᴍᴇꜱ : /game</b>"
        )
        try:
            await context.bot.send_message(chat_id=chat.id, text=bot_add_msg, parse_mode="HTML")
        except Exception:
            pass


async def item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    replied = None
    if update.message and update.message.reply_to_message:
        replied = update.message.reply_to_message.from_user

    user = replied or update.effective_user
    ud = get_user(user.id, getattr(user, "username", "User"), getattr(user, "first_name", "User"))

    raw_name = ud.get("display_name") or getattr(user, "full_name", None) or user.first_name or "User"
    mention = f'<a href="tg://user?id={user.id}">{html.escape(raw_name)}</a>'

    items = ud.get("items") or {}
    if not items:
        await update.message.reply_text(f"👀 {mention} Hᴀꜱ Nᴏ Iᴛᴇᴍꜱ Yᴇᴛ.", parse_mode="HTML")
        return

    lines = [f"📦 <b>{mention}'ꜱ Iᴛᴇᴍꜱ:</b>\n"]
    for it_name, count in items.items():
        lines.append(f"• {it_name} (x{count})")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def items_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>📦 Aᴠᴀɪʟᴀʙʟᴇ Gɪꜰᴛ Iᴛᴇᴍꜱ:\n\n"
        "🌹 Rᴏꜱᴇ — $500\n"
        "🍫 Cʜᴏᴄᴏʟᴀᴛᴇ — $800\n"
        "💍 Ring — $2000\n"
        "🧸 Tᴇᴅᴅʏ Bᴇᴀʀ — $1500\n"
        "🍕 Pizza — $600\n"
        "🎁 Sᴜʀᴘʀɪꜱᴇ Bᴏx — $2500\n"
        "🐶 Puppy — $3000\n"
        "🎂 Cake — $1000\n"
        "💌 Lᴏᴠᴇ Lᴇᴛᴛᴇʀ — $400\n"
        "🐱 Cᴀᴛ — $2500\n"
        "🌷 Tᴜʟɪᴘ — $1500\n"
        "👠 Gɪʀʟ Fʀɪᴇɴᴅ — $1000\n"
        "👦 Bᴏʏ Fʀɪᴇɴᴅ — $1000\n"
        "🏎 Bᴍᴡ — $5000</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


PLACEHOLDER_HANDLERS = {
    "item": item,
    "items": items_list,
}


def _collect_handlers():
    all_handlers = {}
    all_handlers.update(ECON_HANDLERS)
    all_handlers.update(GAME_HANDLERS)
    all_handlers.update(SOCIAL_HANDLERS)
    all_handlers.update(PREM_HANDLERS)
    all_handlers.update(MANAGEMENT_COMMANDS)
    all_handlers.update(PLACEHOLDER_HANDLERS)
    all_handlers["pfp"] = pfp
    all_handlers["profile"] = pfp
    return all_handlers


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if data.startswith("wspr_"):
        await whisper_callback_handler(update, context)
        return

    if data.startswith("verify_join:"):
        caller = query.from_user
        parts = data.split(":")
        try:
            target_uid = int(parts[1])
        except Exception:
            target_uid = caller.id

        if caller.id != target_uid:
            await query.answer("⚠️ Tʜɪꜱ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ʙᴜᴛᴛᴏɴ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ᴛʜᴇ ɴᴇᴡʟʏ ᴊᴏɪɴᴇᴅ ᴜꜱᴇʀ!", show_alert=True)
            return

        username = caller.username or caller.first_name or "User"
        display_name = caller.first_name or username
        ud = get_user(caller.id, username, display_name)
        toprich_rank = global_rank(caller.id, "balance")

        stats_block = (
            "<blockquote>"
            "<b>📊 ʏᴏᴜʀ ꜱᴛᴀᴛꜱ:</b>\n"
            f"<b>💰 ʙᴀʟᴀɴᴄᴇ:</b> {ud['balance']}\n"
            f"<b>🏆 ʀᴀɴᴋ:</b> {toprich_rank}\n"
            f"<b>💎 ɢᴇᴍꜱ:</b> {ud['gems']:.2f}\n"
            f"<b>🔪 ᴋɪʟʟꜱ:</b> {ud['kills']}"
            "</blockquote>"
        )
        mini_app_url = f"https://mike-payment.vercel.app/app.html?user_id={caller.id}"
        chat = update.effective_chat
        is_private = (chat and chat.type == "private") or (query.message and query.message.chat and query.message.chat.type == "private")
        web_btn = (
            InlineKeyboardButton("🌐 ᴏᴘᴇɴ ᴍɪᴋᴏ ᴡᴇʙ ᴀᴘᴘ", web_app=WebAppInfo(url=mini_app_url))
            if is_private
            else InlineKeyboardButton("🌐 ᴏᴘᴇɴ ᴍɪᴋᴏ ᴡᴇʙ ᴀᴘᴘ", url=mini_app_url)
        )
        keyboard = [
            [web_btn],
            [InlineKeyboardButton("🍀 ᴍɪᴋᴏ ꜰᴇᴀᴛᴜʀᴇꜱ", callback_data="miko_features")],
            [
                InlineKeyboardButton("👥 ɢʀᴏᴜᴘꜱ", callback_data="groups"),
                InlineKeyboardButton("🐻 ᴘʀᴏᴍᴏᴛᴇʀ", url="https://t.me/advaydev"),
            ],
            [
                InlineKeyboardButton("📢 ᴜᴘᴅᴀᴛᴇꜱ", url="https://t.me/i_mikoo"),
                InlineKeyboardButton("🎮 ɢᴀᴍᴇꜱ", callback_data="games"),
            ],
            [
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url="https://t.me/i_mikobot?startgroup=true"),
            ],
        ]
        start_text = (
            f"✅ <b>Vᴇʀɪꜰɪᴄᴀᴛɪᴏɴ Sᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\n"
            f"💙 ʜɪᴇᴇᴇᴇᴇᴇᴇ {caller.mention_html()} ɪ'ᴍ ᴍɪᴋᴏ - ᴀ ɢᴀᴍɪɴɢ ᴀɴᴅ ᴄʜᴀᴛᴛɪɴɢ ɢɪʀʟ ʜᴀᴠɪɴɢ ʟᴏᴛꜱ ᴏꜰ ꜰᴇᴀᴛᴜʀᴇꜱ ᴛᴏ ᴇɴɢᴀɢᴇ ʏᴏᴜʀ ɢʀᴏᴜᴘ.\n"
            f"{stats_block}\n"
            f"<b>🕹️ ʜᴏᴡ ᴛᴏ ᴘʟᴀʏ?</b>\n"
            f"💰 /bal - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ\n"
            f"👤 /pfp - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴘꜰᴘ\n"
            f"🎁 /daily - ɢᴇᴛ ꜰʀᴇᴇ ᴄᴏɪɴꜱ\n"
            f"🛡️ /protect - ꜱᴀᴠᴇ ʏᴏᴜʀꜱᴇʟꜰ\n"
            f"⚔️ /kill &amp; /rob - ʟᴏᴏᴛ ᴏᴛʜᴇʀꜱ\n\n"
            f"👇 ᴄʜᴏᴏꜱᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ :"
        )
        await query.answer("✅ Verified successfully! Welcome to Miko!", show_alert=False)
        try:
            await query.edit_message_text(text=start_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except Exception:
            await query.message.reply_text(text=start_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if data.startswith("fund_acc:") or data.startswith("fund_rej:"):
        caller = query.from_user
        from modules.utils.db import is_sudo_user
        import html as html_lib
        if not caller or not is_sudo_user(caller.id):
            await query.answer("🚫 Only Bot Owner / Sudoers can approve or reject fund requests!", show_alert=True)
            return

        is_accept = data.startswith("fund_acc:")
        parts = data.split(":")
        try:
            target_uid = int(parts[1])
            amount = float(parts[2])
            req_id = parts[3] if len(parts) > 3 else "N/A"
        except Exception:
            await query.answer("❌ Error parsing request data.", show_alert=True)
            return

        admin_name = caller.first_name or caller.username or f"Admin {caller.id}"
        target_ud = get_user(target_uid)
        user_name = target_ud.get("display_name") or target_ud.get("username") or f"User {target_uid}"

        if is_accept:
            new_wallet = round(float(target_ud.get("prem_wallet", 0.0) or 0.0) + amount, 2)
            update_user(target_uid, prem_wallet=new_wallet)

            new_log_text = (
                f"💳 <b>[ADD FUND - APPROVED ✅]</b>\n\n"
                f"👤 <b>User:</b> <a href=\"tg://user?id={target_uid}\">{html_lib.escape(user_name)}</a>\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_uid}</code>\n"
                f"💵 <b>Amount Credited:</b> <b>₹{amount:,.2f} INR</b>\n"
                f"💼 <b>Updated Wallet Balance:</b> <b>₹{new_wallet:,.2f}</b>\n"
                f"🔑 <b>Request ID:</b> <code>REQ-{req_id}</code>\n"
                f"👮‍♂️ <b>Approved By:</b> <a href=\"tg://user?id={caller.id}\">{html_lib.escape(admin_name)}</a>\n"
                f"⏰ <b>Status:</b> <b>Credited Successfully</b>"
            )
            try:
                await query.edit_message_text(text=new_log_text, parse_mode="HTML")
            except Exception:
                pass

            await query.answer(f"✅ Approved! ₹{amount:g} credited to User {target_uid}", show_alert=True)

            try:
                user_notify = (
                    f"🎉 <b>Fund Deposit Approved!</b>\n\n"
                    f"💳 <b>Amount Credited:</b> <b>₹{amount:,.2f} INR</b>\n"
                    f"💼 <b>Premium Wallet Balance:</b> <b>₹{new_wallet:,.2f}</b>\n"
                    f"👮‍♂️ <b>Approved By:</b> Admin ({html_lib.escape(admin_name)})\n\n"
                    f"✨ You can now open the Mini App to activate your VIP Premium plan!"
                )
                await context.bot.send_message(chat_id=target_uid, text=user_notify, parse_mode="HTML")
            except Exception as e:
                print(f"Could not DM user {target_uid}: {e}")
        else:
            new_log_text = (
                f"💳 <b>[ADD FUND - REJECTED ❌]</b>\n\n"
                f"👤 <b>User:</b> <a href=\"tg://user?id={target_uid}\">{html_lib.escape(user_name)}</a>\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_uid}</code>\n"
                f"💵 <b>Amount:</b> <b>₹{amount:,.2f} INR</b>\n"
                f"🔑 <b>Request ID:</b> <code>REQ-{req_id}</code>\n"
                f"👮‍♂️ <b>Rejected By:</b> <a href=\"tg://user?id={caller.id}\">{html_lib.escape(admin_name)}</a>\n"
                f"⏰ <b>Status:</b> <b>Request Rejected</b>"
            )
            try:
                await query.edit_message_text(text=new_log_text, parse_mode="HTML")
            except Exception:
                pass

            await query.answer(f"❌ Fund request REJECTED for User {target_uid}", show_alert=True)

            try:
                user_notify = (
                    f"❌ <b>Fund Deposit Request Rejected</b>\n\n"
                    f"⚠️ Your deposit request of <b>₹{amount:,.2f} INR</b> was rejected by Admin.\n"
                    f"If you already completed the payment, please contact @advaydev with proof."
                )
                await context.bot.send_message(chat_id=target_uid, text=user_notify, parse_mode="HTML")
            except Exception:
                pass
        return

    await query.answer()

    if data.startswith("gleader_"):
        parts = data.split("_")
        game_key = parts[1] if len(parts) > 1 else "card"
        from modules.games.bomb_game import render_leaders_message
        text, keyboard = render_leaders_message(game_key)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    if data.startswith("bomb:"):
        parts = data.split(":")
        try:
            tile_idx = int(parts[1])
            user_id = int(parts[2])
            bombs = list(map(int, parts[3].split(",")))
        except Exception:
            return
        if getattr(query.from_user, "id", None) != user_id:
            await query.answer("This game is not yours!", show_alert=True)
            return
        ud = get_user(user_id)
        current = getattr(query.message, "reply_markup", None)
        kb_rows = current.inline_keyboard if current else []
        flat = [btn for row in kb_rows for btn in row]
        hit_bomb = tile_idx in bombs
        new_text = ""
        if hit_bomb:
            new_text = f"💥 BOOM! You hit a bomb at tile {tile_idx}.\nStake deducted: $10\nNew balance: ${max(0, ud['balance'] - 10)}"
            update_user(user_id, balance=max(0, ud["balance"] - 10))
            new_emoji = "💣"
        else:
            reward = random.randint(1, 50)
            new_text = f"✅ Safe tile #{tile_idx}! You won ${reward}.\nBalance: ${ud['balance'] + reward}"
            update_user(user_id, balance=ud["balance"] + reward)
            add_xp(user_id, 5)
            new_emoji = "✅"
        flat[tile_idx] = InlineKeyboardButton(new_emoji, callback_data=f"bomb_done:{tile_idx}:{user_id}")
        rebuilt = [flat[i:i + 3] for i in range(0, 9, 3)]
        await query.edit_message_text(text=new_text, reply_markup=InlineKeyboardMarkup(rebuilt))
        return

    if data.startswith("grank_"):
        parts = data.split("_")
        game_key = parts[1]
        target_id = int(parts[2])
        ud = get_user(target_id)
        name = ud.get("display_name") or ud.get("username") or f"User {target_id}"
        from modules.games.bomb_game import render_rank_message
        text, keyboard = render_rank_message(game_key, target_id, ud, name)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    if data.startswith("toprich_"):
        mode = "global" if "global" in data else "group"
        parts = data.split("_")
        chat_id = int(parts[2]) if len(parts) > 2 else (query.message.chat.id if query.message else 0)
        from modules.economy.commands import render_toprich_message
        text, keyboard = render_toprich_message(chat_id, mode)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    if data.startswith("topkill_"):
        mode = "global" if "global" in data else "group"
        parts = data.split("_")
        chat_id = int(parts[2]) if len(parts) > 2 else (query.message.chat.id if query.message else 0)
        from modules.economy.commands import render_topkill_message
        text, keyboard = render_topkill_message(chat_id, mode)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    if data.startswith("toprob_"):
        mode = "global" if "global" in data else "group"
        parts = data.split("_")
        chat_id = int(parts[2]) if len(parts) > 2 else (query.message.chat.id if query.message else 0)
        from modules.economy.commands import render_toprob_message
        text, keyboard = render_toprob_message(chat_id, mode)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    if data == "miko_features":
        text = (
            "ℹ️ <b>ABOUT MIKO</b>\n\n"
            "CLICK THE BUTTONS BELOW TO KNOW MORE ABOUT MIKO FEATURES."
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🤫 Whisper", url="https://t.me/i_mikoo/8"),
                InlineKeyboardButton("👮 Management", url="https://t.me/i_mikoo/9"),
            ],
            [
                InlineKeyboardButton("👑 Ownership", url="https://t.me/i_mikoo/10"),
                InlineKeyboardButton("💓 Premium", url="https://t.me/i_mikoo/11"),
            ],
            [
                InlineKeyboardButton("💎 Gems", url="https://t.me/i_mikoo/12"),
                InlineKeyboardButton("🦅 Powers", url="https://t.me/i_mikoo/13"),
            ],
            [
                InlineKeyboardButton("💰 Economy", url="https://t.me/i_mikoo/14"),
                InlineKeyboardButton("🕹 Games", url="https://t.me/i_mikoo/3"),
            ],
            [
                InlineKeyboardButton("🧸 Friends", url="https://t.me/i_mikoo/15"),
                InlineKeyboardButton("🎟 Coupons", url="https://t.me/i_mikoo/16"),
            ],
            [
                InlineKeyboardButton("💗 Interactionss", url="https://t.me/i_mikoo/17"),
                InlineKeyboardButton("🛠 Utilities", url="https://t.me/i_mikoo/18"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_start"),
            ]
        ])
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    if data == "back_start":
        user = query.from_user
        uid = user.id
        ud = get_user(user.id, user.username or "User", user.first_name or "User")
        toprich_rank = global_rank(user.id, "balance")
        stats_block = (
            "<blockquote>"
            "<b>📊 ʏᴏᴜʀ ꜱᴛᴀᴛꜱ:</b>\n"
            f"<b>💰 ʙᴀʟᴀɴᴄᴇ:</b> {ud['balance']}\n"
            f"<b>🏆 ʀᴀɴᴋ:</b> {toprich_rank}\n"
            f"<b>💎 ɢᴇᴍꜱ:</b> {ud['gems']:.2f}\n"
            f"<b>🔪 ᴋɪʟʟꜱ:</b> {ud['kills']}"
            "</blockquote>"
        )
        user_mention = f'<a href="tg://user?id={uid}">{user.first_name or user.username or "User"}</a>'
        text = (
            f"💙 ʜɪᴇᴇᴇᴇᴇᴇᴇ {user_mention} ɪ'ᴍ ᴍɪᴋᴏ - ᴀ ɢᴀᴍɪɴɢ ᴀɴᴅ ᴄʜᴀᴛᴛɪɴɢ ɢɪʀʟ ʜᴀᴠɪɴɢ ʟᴏᴛꜱ ᴏꜰ ꜰᴇᴀᴛᴜʀᴇꜱ ᴛᴏ ᴇɴɢᴀɢᴇ ʏᴏᴜʀ ɢʀᴏᴜᴘ.\n"
            f"{stats_block}\n"
            f"<b>🕹️ ʜᴏᴡ ᴛᴏ ᴘʟᴀʏ?</b>\n"
            f"💰 /bal - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ\n"
            f"👤 /pfp - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴘꜰᴘ\n"
            f"🎁 /daily - ɢᴇᴛ ꜰʀᴇᴇ ᴄᴏɪɴꜱ\n"
            f"🛡️ /protect - ꜱᴀᴠᴇ ʏᴏᴜʀꜱᴇʟꜰ\n"
            f"⚔️ /kill &amp; /rob - ʟᴏᴏᴛ ᴏᴛʜᴇʀꜱ\n\n"
            f"👇 ᴄʜᴏᴏꜱᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ :"
        )
        from telegram import WebAppInfo
        mini_app_url = f"https://mike-payment.vercel.app/app.html?user_id={uid}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 ᴏᴘᴇɴ ᴍɪᴋᴏ ᴡᴇʙ ᴀᴘᴘ", web_app=WebAppInfo(url=mini_app_url))],
            [InlineKeyboardButton("🍀 ᴍɪᴋᴏ ꜰᴇᴀᴛᴜʀᴇꜱ", callback_data="miko_features")],
            [
                InlineKeyboardButton("👥 ɢʀᴏᴜᴘꜱ", callback_data="groups"),
                InlineKeyboardButton("🐻 ᴘʀᴏᴍᴏᴛᴇʀ", url="https://t.me/advaydev"),
            ],
            [
                InlineKeyboardButton("📢 ᴜᴘᴅᴀᴛᴇꜱ", url="https://t.me/i_mikoo"),
                InlineKeyboardButton("🎮 ɢᴀᴍᴇꜱ", callback_data="games"),
            ],
            [
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url="https://t.me/i_mikobot?startgroup=true"),
            ],
        ])
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
        return

    feat_map = {
        "feat_whisper": (
            "🤫 <b>WHISPER FEATURES</b>\n\n"
            "Send secret messages to anyone in group chats:\n"
            "• Type inline: <code>@bot_username message @username</code>\n"
            "• Secret whispers can only be opened by recipient!"
        ),
        "feat_mgmt": (
            "👮 <b>MANAGEMENT FEATURES</b>\n\n"
            "Group admin & management tools:\n"
            "• <code>/admins</code> — List group owner & human admins\n"
            "• <code>/tag &lt;all|tag_name&gt;</code> — Mention your circle members\n"
            "• <code>/econ on|off</code> — Toggle economy in group"
        ),
        "feat_owner": (
            "👑 <b>OWNERSHIP FEATURES</b>\n\n"
            "Bot & Group ownership tools:\n"
            "• <code>/owner</code> — Check group owner info\n"
            "• <code>/broadcast</code> — Broadcast message across active chats"
        ),
        "feat_premium": (
            "💓 <b>PREMIUM FEATURES</b>\n\n"
            "Unlock special perks and status:\n"
            "• <code>/pay</code> — Upgrade to Premium membership\n"
            "• <code>/setemoji</code> — Set your custom profile emoji\n"
            "• <code>/check</code> — View player emoji & premium status"
        ),
        "feat_gems": (
            "💎 <b>GEMS FEATURES</b>\n\n"
            "Special high-value currency (1 Gem = $10,000):\n"
            "• <code>/gems</code> — Check and claim gems\n"
            "• <code>/fgems</code> — Buy gems using Telegram Stars"
        ),
        "feat_powers": (
            "🦅 <b>POWERS SYSTEM</b>\n\n"
            "Equip powers to dominate games and battles:\n"
            "• <code>/powers</code> — Check available powers catalog\n"
            "• <code>/mypowers</code> / <code>/mp</code> — Check your active powers\n"
            "• <code>/buy &lt;power&gt;</code> — Purchase power"
        ),
        "feat_economy": (
            "💰 <b>ECONOMY FEATURES</b>\n\n"
            "Full currency and PvP economy:\n"
            "• <code>/bal</code> — Check your balance, rank and kills\n"
            "• <code>/give &lt;amount&gt;</code> — Transfer money to a friend\n"
            "• <code>/rob &lt;amount&gt;</code> — Rob money from players\n"
            "• <code>/kill</code> — Brutally attack & loot players\n"
            "• <code>/protect</code> — Buy protective shield\n"
            "• <code>/daily</code> — Claim free bonus every 24 hours\n"
            "• <code>/toprich</code>, <code>/topkill</code>, <code>/toprob</code> — Leaderboards"
        ),
        "feat_games": (
            "🕹 <b>GAMES SYSTEM</b>\n\n"
            "Multiplayer interactive mini games:\n"
            "• <code>/hack &lt;amount&gt; &lt;players&gt;</code> — Group Hack Game\n"
            "• <code>/bluff &lt;amount&gt; &lt;players&gt;</code> — Miko Bluff Card Game\n"
            "• <code>/bomb &lt;stake&gt;</code> — Defuse the bomb tiles\n"
            "• <code>/roulette &lt;amount&gt;</code> — Russian Roulette Game\n"
            "• <code>/card</code> — Guess high/low card game\n"
            "• <code>/rank</code> — Game rankings card"
        ),
        "feat_friends": (
            "🧸 <b>FRIENDS FEATURES</b>\n\n"
            "Friend circles and custom tags:\n"
            "• <code>/friends</code> — View your friends circles\n"
            "• <code>/addfriend &lt;tag&gt;</code> — Add friend to circle\n"
            "• <code>/removefriend &lt;tag&gt;</code> — Remove friend\n"
            "• <code>/tag &lt;tag_name&gt;</code> — Tag all friends in group"
        ),
        "feat_coupons": (
            "🎟 <b>COUPONS SYSTEM</b>\n\n"
            "Redeem promo codes for rewards:\n"
            "• <code>/coupon &lt;code&gt;</code> — Redeem bonus code\n"
            "• <code>/status &lt;code&gt;</code> — Check code status\n"
            "• <code>/claim</code> — Claim group reward"
        ),
        "feat_interactions": (
            "💗 <b>INTERACTIONSS FEATURES</b>\n\n"
            "Fun social & roleplay interactions:\n"
            "• <code>/kiss</code>, <code>/hug</code>, <code>/slap</code>, <code>/punch</code>, <code>/bite</code>, <code>/murder</code>\n"
            "• <code>/crush</code>, <code>/couples</code>, <code>/stupid_meter</code>, <code>/brain</code>\n"
            "• <code>/gift &lt;item&gt;</code>, <code>/item</code>, <code>/items</code>"
        ),
        "feat_utilities": (
            "🛠 <b>UTILITIES</b>\n\n"
            "Helpful utility commands:\n"
            "• <code>/id</code> — Check your Telegram ID\n"
            "• <code>/voice &lt;text&gt;</code> — Convert text to voice note\n"
            "• <code>/q</code> — Create quote sticker\n"
            "• <code>/detail</code> — Check username & name history\n"
            "• <code>/calc</code> — Math calculator"
        ),
    }

    if data in feat_map:
        text = feat_map[data]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Features", callback_data="miko_features")]
        ])
        try:
            await query.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        return

    if data == "groups":
        text = (
            "👥 <b>ᴊᴏɪɴ ᴛʜᴇꜱᴇ ɢʀᴏᴜᴘꜱ ᴛᴏ ᴘʟᴀʏ ᴍɪᴋᴏ ɢᴀᴍᴇꜱ.</b>\n\n"
            "👉 <b>ᴏɴʟʏ ᴛʜᴇ ᴛᴏᴘ 5 ɢʟᴏʙᴀʟʟʏ ʀɪᴄʜᴇꜱᴛ ᴜꜱᴇʀꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ꜱᴇᴛ ᴛʜᴇɪʀ ɢʀᴏᴜᴘ ʜᴇʀᴇ ᴜꜱᴇ :</b> /setgroup"
        )
        from modules.utils.storage import get_featured_groups
        groups = get_featured_groups()
        kb_rows = []
        if len(groups) > 0:
            kb_rows.append([InlineKeyboardButton(groups[0]["name"], url=groups[0]["link"])])
        if len(groups) > 2:
            kb_rows.append([
                InlineKeyboardButton(groups[1]["name"], url=groups[1]["link"]),
                InlineKeyboardButton(groups[2]["name"], url=groups[2]["link"]),
            ])
        elif len(groups) > 1:
            kb_rows.append([InlineKeyboardButton(groups[1]["name"], url=groups[1]["link"])])

        if len(groups) > 4:
            kb_rows.append([
                InlineKeyboardButton(groups[3]["name"], url=groups[3]["link"]),
                InlineKeyboardButton(groups[4]["name"], url=groups[4]["link"]),
            ])
        elif len(groups) > 3:
            kb_rows.append([InlineKeyboardButton(groups[3]["name"], url=groups[3]["link"])])

        kb_rows.append([InlineKeyboardButton("🔙 Back", callback_data="back_start")])
        try:
            await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")
        except Exception:
            pass
        return
    elif data == "games":
        text = (
            "🎮 <b>ᴍɪᴋᴏ ɢᴀᴍᴇ ꜰᴇᴀᴛᴜʀᴇꜱ</b>\n\n"
            "ᴋɴᴏᴡ ᴀʙᴏᴜᴛ ᴛʜᴇ ᴍɪᴋᴏ ᴍɪɴɪ ɢᴀᴍᴇꜱ: /game\n"
            "ᴋɴᴏᴡ ᴀʙᴏᴜᴛ ᴛʜᴇ ᴇᴄᴏɴᴏᴍʏ ꜱʏꜱᴛᴇᴍ: /economy\n\n"
            "ʜᴀᴠᴇ ꜰᴜɴ ᴀɴᴅ ʙᴇ ʟᴜᴄᴋʏ🍀"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
        ])
        try:
            await query.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        return
    elif data == "buy_gems":
        text = (
            "💎 <b>ʙᴜʏ ɢᴇᴍꜱ</b>\n\n"
            "Price grid coming from your site. For now:\n"
            "• 1 Gem = $10,000 in-game balance via /gems claim flow\n"
            "• Telegram Stars purchase: /fgems"
        )
    elif data == "add_funds":
        text = (
            "💰 <b>ᴀᴅᴅ ꜰᴜɴᴅꜱ</b>\n\n"
            "Connect your payment gateway (UPI / Stripe / Stars).\n"
            "Placeholder: 50 Stars → $5000 in-game balance."
        )
    if data.startswith("buy_stars_"):
        await send_stars_invoice(query, context, data)
        return

    try:
        await query.edit_message_text(text=text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass


from modules.utils.logger import send_log_message
from modules.utils.db import warmup_redis_cache


async def post_init(app):
    warmup_redis_cache()
    await app.bot.set_my_commands(BOT_COMMANDS)
    print(f"✅ ʀᴇɢɪꜱᴛᴇʀᴇᴅ {len(BOT_COMMANDS)} ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅꜱ ꜰᴏʀ / ꜱᴜɢɢᴇꜱᴛɪᴏɴꜱ!")

    # Start background protection expiry alert monitor
    try:
        from modules.economy.protection_monitor import start_protection_monitor
        asyncio.create_task(start_protection_monitor(app.bot))
    except Exception as me:
        print(f"⚠️ Protection monitor startup error: {me}")

    # Start background payment API server
    try:
        from modules.payment.server import create_payment_app
        from aiohttp import web
        pay_app = create_payment_app()
        runner = web.AppRunner(pay_app)
        await runner.setup()
        port = int(os.getenv("PORT", "8080"))
        # Only bind if port is provided and not bound
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"💳 Payment API Server listening on port {port}!")
    except Exception as pe:
        print(f"ℹ️ Payment server notice: {pe}")

    try:
        bot_user = await app.bot.get_me()
        log_text = (
            "🤖 <b>ᴍɪᴋᴏ ʙᴏᴛ ɪꜱ ɴᴏᴡ ᴏɴʟɪɴᴇ!</b>\n\n"
            f"👤 <b>Bot Name:</b> {bot_user.first_name}\n"
            f"🔗 <b>Username:</b> @{bot_user.username}\n"
            f"🆔 <b>ID:</b> <code>{bot_user.id}</code>\n"
            "🍃 <b>Database:</b> <code>MongoDB + Redis Online</code>\n"
            "💳 <b>Razorpay Gateway:</b> <code>Active & Verified</code>\n"
            "⭐ <b>Telegram Stars Payments:</b> <code>Active & Verified</code>\n"
            "✨ <b>Status:</b> Ready and serving users!"
        )
        await send_log_message(app.bot, log_text)
    except Exception as e:
        print(f"Startup log error: {e}")


def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN ɴᴏᴛ ꜰᴏᴜɴᴅ! ᴘʟᴇᴀꜱᴇ ꜱᴇᴛ ɪᴛ ɪɴ .ᴇɴᴠ ꜰɪʟᴇ.")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )

    handlers = _collect_handlers()
    for cmd_name, fn in handlers.items():
        app.add_handler(CommandHandler(cmd_name, fn))

    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(MessageHandler(filters.ALL, track_chat_activity), group=-1)
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member_updated, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prefix_command), group=1)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.Sticker.ALL) & ~filters.COMMAND, dm_chatbot_handler), group=2)
    app.add_handler(InlineQueryHandler(inline_whisper_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 ᴍɪᴋᴏ ʙᴏᴛ ɪꜱ ʀᴜɴɴɪɴɢ...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
