import os
import json
from datetime import datetime
from typing import Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice
from telegram.ext import ContextTypes

from modules.utils.storage import get_user, update_user, get_group, update_group, POWERS_CATALOG


def _cs(cmd, desc=""):
    return f"⏳ <b>/{cmd}</b> — ᴄᴏᴍɪɴɢ ꜱᴏᴏɴ!\n<i>{desc}</i>"


async def ph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "<b>⚡ Pᴏᴡᴇʀꜱ Mᴇɴᴜ ⚡\n\n"
        "🛒 /powers - Sʜᴏᴡ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ᴘᴏᴡᴇʀꜱ\n"
        "ℹ️ /pinfo &lt;name&gt; - Sᴇᴇ ᴘᴏᴡᴇʀ ᴅᴇᴛᴀɪʟꜱ\n"
        "✅ /activate or /act - Aᴄᴛɪᴠᴀᴛᴇ ᴀ ᴘᴏᴡᴇʀ\n"
        "✨ /mypowers or /mp - Cʜᴇᴄᴋ ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ᴘᴏᴡᴇʀꜱ\n"
        "📢 /ph - Pᴏᴡᴇʀ Hᴇʟᴘ Cᴏᴍᴍᴀɴᴅꜱ</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def powers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "⚡ <b>Aᴠᴀɪʟᴀʙʟᴇ Pᴏᴡᴇʀꜱ Iɴ Sᴛᴏʀᴇ</b>\n\n"
        "🔥 Rampage (rampage)\n"
        "🥷 Cloak (cloak)\n"
        "🏦 Vault (vault)\n\n"
        "ℹ️ Uꜱᴇ /pinfo &lt;power_name&gt; ᴛᴏ ꜱᴇᴇ ᴅᴇᴛᴀɪʟꜱ ᴀɴᴅ ᴘʀɪᴄᴇꜱ."
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def pinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        keys = " • ".join(POWERS_CATALOG.keys())
        await update.message.reply_text(f"ℹ️ Usage: /pinfo &lt;power_name&gt;\nAvailable: {keys}", parse_mode="HTML")
        return
    key = str(args[0]).lower().strip()
    if key not in POWERS_CATALOG:
        await update.message.reply_text(f"❌ Unknown power. Available: {' • '.join(POWERS_CATALOG.keys())}")
        return
    info = POWERS_CATALOG[key]
    msg = (
        f"{info['emoji']} <b>{info['name'].upper()}</b>\n\n"
        f"✨ {info['desc']}\n"
        f"💎 Cost: <b>{info['price']} Gem / day</b>\n\n"
        f"👉 To activate: <code>/activate {key} &lt;days&gt;</code>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    args = context.args or []
    if not args:
        await update.message.reply_text("💡 Usage: /activate <power_name> <days>\nExample: <code>/activate rampage 3</code>", parse_mode="HTML")
        return
    key = str(args[0]).lower().strip()
    if key not in POWERS_CATALOG:
        await update.message.reply_text(f"❌ Unknown power. Available: {', '.join(POWERS_CATALOG.keys())}")
        return

    days = 1
    if len(args) > 1 and args[1].isdigit():
        days = max(1, int(args[1]))

    info = POWERS_CATALOG[key]
    total_cost = info["price"] * days
    if ud["gems"] < total_cost:
        await update.message.reply_text(
            f"💎 Need {total_cost} gems for {days} day(s). You have {ud['gems']:.2f} gems.\nBuy more at /gems"
        )
        return

    active = list(ud.get("powers") or [])
    if key not in active:
        active.append(key)
    update_user(user.id, gems=round(ud["gems"] - total_cost, 2), powers=active, premium=True)
    await update.message.reply_text(
        f"✅ <b>{info['name']}</b> activated for {days} day(s)! (-{total_cost} gems)\n"
        f"Active powers: {', '.join(active)}",
        parse_mode="HTML",
    )


async def mypowers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    active = ud.get("powers") or []
    if not active:
        await update.message.reply_text("✨ You have no active powers. See /powers or /ph")
        return
    lines = ["✨ <b>ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ᴘᴏᴡᴇʀꜱ</b>\n"]
    for k in active:
        info = POWERS_CATALOG.get(k, {"name": k, "emoji": "❓", "desc": ""})
        lines.append(f"{info['emoji']} <b>{info['name']}</b> — {info['desc']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Oɴʟʏ Wᴏʀᴋꜱ Iɴ Tʜᴇ ᴍɪᴋᴏ Bᴏᴛ'ꜱ Dᴍ.")
        return

    text = (
        "<b>ᴍɪᴋᴏ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ</b>\n\n"
        "ɪᴍᴘᴏʀᴛᴀɴᴛ ɴᴏᴛᴇ: ɪꜰ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ɪɴᴅɪᴀɴ ᴜꜱᴇʀ ᴀɴᴅ ᴜɴʙᴀʟᴇ ᴛᴏ ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ꜰʀᴏᴍ ᴛʜᴇ ꜱɪᴛᴇ ᴛʜᴇɴ ʏᴏᴜ ᴄᴀɴ ʙᴜʏ ʙᴀᴋᴀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱɪɴɢ ᴛᴇʟᴇɢʀᴀᴍ ꜱᴛᴀʀꜱ ᴜꜱɪɴɢ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ : /fpay\n\n"
        "ɪꜰ ʏᴏᴜ ᴀʀᴇ ꜰʀᴏᴍ ɪɴᴅɪᴀ ᴛʜᴇɴ ʏᴏᴜ ᴄᴀɴ ʙᴜʏ ʙᴀᴋᴀ ᴘʀᴇᴍɪᴜᴍ ꜱɪᴍᴘʟʏ ꜰʀᴏᴍ ᴛʜᴇ ʙᴇʟᴏᴡ ᴘᴀʏ ɴᴏᴡ ʙᴜᴛᴛᴏɴ\n"
        "ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ : /id\n\n"
        "ʏᴏᴜ ᴄᴀɴ ʀᴇᴘᴏʀᴛ ᴀɴʏ ɪꜱꜱᴜᴇ ᴛʜʀᴏᴜɢʜ ᴛʜᴇ ᴅᴍ ᴏꜰ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ : @Developer_World_Advay"
    )

    user = update.effective_user
    uid = user.id if user else 0

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 PAY NOW", web_app=WebAppInfo(url=f"https://mike-payment.vercel.app/checkout.html?user_id={uid}")),
            InlineKeyboardButton("💰 ADD FUNDS", web_app=WebAppInfo(url=f"https://mike-payment.vercel.app/checkout.html?plan=1_month&user_id={uid}")),
        ],
        [
            InlineKeyboardButton("💓 FEATURES", url="https://t.me/i_mikoo/11"),
            InlineKeyboardButton("📜 TERMS AND REFUND", web_app=WebAppInfo(url="https://mike-payment.vercel.app/refund.html")),
        ],
    ])

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

STARS_PLANS = {
    "stars_1_month": {"title": "1 Month VIP Premium", "stars": 50, "gems": 1.0, "months": 1},
    "stars_2_months": {"title": "2 Months VIP Premium", "stars": 100, "gems": 2.0, "months": 2},
    "stars_3_months": {"title": "3 Months VIP Premium", "stars": 130, "gems": 3.0, "months": 3},
    "stars_6_months": {"title": "6 Months VIP Premium", "stars": 160, "gems": 6.0, "months": 6},
    "stars_12_months": {"title": "12 Months VIP Premium", "stars": 250, "gems": 12.0, "months": 12},
}


async def fpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Oɴʟʏ Wᴏʀᴋꜱ Iɴ Tʜᴇ ᴍɪᴋᴏ Bᴏᴛ'ꜱ Dᴍ.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ <b>Usage :</b> <code>/fpay user_id</code>", parse_mode="HTML")
        return

    target_id_str = context.args[0].strip()
    if not target_id_str.isdigit():
        await update.message.reply_text("⚠️ <b>Usage :</b> <code>/fpay user_id</code>", parse_mode="HTML")
        return

    target_uid = int(target_id_str)
    chat_id = update.effective_chat.id

    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title="miko premium access",
            description="PAY 59 STARS TO BUY 30 DAYS MIKO PREMIUM ACCESS IN PROVIDED USER ID.",
            payload=f"fpay_{target_uid}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="miko premium access", amount=59)],
            photo_url="https://i.ibb.co/SwtfTqpP/photo-2026-08-24-03-31-04.jpg",
            photo_width=512,
            photo_height=512,
        )
    except Exception as e:
        print(f"Error sending Stars invoice: {e}")
        await update.message.reply_text("⚠️ Could not open Stars checkout invoice. Please try again.")


async def send_stars_invoice(query, context, plan_key: str):
    """Sends native Telegram Stars invoice modal"""
    if plan_key not in STARS_PLANS:
        await query.answer("⚠️ Invalid plan selected!", show_alert=True)
        return

    plan = STARS_PLANS[plan_key]
    chat_id = query.message.chat_id

    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=f"👑 Miko {plan['title']}",
            description=f"Instant VIP Premium activation for {plan['months']} month(s) + {int(plan['gems'])} Free Bonus Gem(s)!",
            payload=plan_key,
            provider_token="",  # Must be empty string for Telegram Stars (XTR)
            currency="XTR",
            prices=[LabeledPrice(label=plan["title"], amount=plan["stars"])],
            photo_url="https://i.ibb.co/SwtfTqpP/photo-2026-08-24-03-31-04.jpg",
            photo_width=512,
            photo_height=512,
        )
        await query.answer()
    except Exception as e:
        print(f"Error sending Stars invoice: {e}")
        await query.answer("⚠️ Could not open Stars checkout invoice. Please try again.", show_alert=True)


async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer Telegram Stars pre-checkout query"""
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("stars_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Payment verification error. Please contact support.")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered automatically when payment via Telegram Stars succeeds"""
    payment = update.message.successful_payment
    user = update.effective_user
    payload = payment.invoice_payload

    if payload.startswith("fpay_"):
        parts = payload.split("_")
        target_uid = int(parts[1])
        plan_title = "30 Days Miko Premium Access"
        free_gems = 1.0
    else:
        target_uid = user.id
        plan = STARS_PLANS.get(payload, {"title": "VIP Premium", "gems": 1.0, "months": 1})
        plan_title = plan["title"]
        free_gems = plan.get("gems", 1.0)

    ud = get_user(target_uid)
    new_gems = round(ud.get("gems", 0.0) + free_gems, 2)
    update_user(target_uid, premium=True, gems=new_gems)

    text = (
        f"🎉 <b>ᴍɪᴋᴏ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{target_uid}</code>\n"
        f"⭐ <b>Stars Paid:</b> {payment.total_amount} ⭐\n"
        f"💎 <b>Free Bonus Gems:</b> +{int(free_gems)} 💎\n"
        f"✨ <b>VIP Status:</b> 30 Days Active\n\n"
        f"🌟 <i>Your VIP perks are now active across all groups! Check with /pfp or /bal.</i>"
    )

    await update.message.reply_text(text, parse_mode="HTML")

async def claim(update, context):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🚫 Tʜɪꜱ Gʀᴏᴜᴘ Nᴇᴇᴅꜱ Aᴛ Lᴇᴀꜱᴛ 500 Mᴇᴍʙᴇʀꜱ Tᴏ Cʟᴀɪᴍ Rᴇᴡᴀʀᴅ.")
        return

    try:
        member_count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        member_count = 0

    if member_count < 500:
        await update.message.reply_text("🚫 Tʜɪꜱ Gʀᴏᴜᴘ Nᴇᴇᴅꜱ Aᴛ Lᴇᴀꜱᴛ 500 Mᴇᴍʙᴇʀꜱ Tᴏ Cʟᴀɪᴍ Rᴇᴡᴀʀᴅ.")
        return

    gdata = get_group(chat.id)
    today_str = datetime.now().strftime("%Y-%m-%d")

    if gdata.get("last_claim_date") == today_str:
        claimed_by = gdata.get("claimed_by_name") or "𓍯 𝗖ֹ︩︪𝗮𝗳𝗳𝗶𝗻."
        await update.message.reply_text(
            f"🚫 Tʜɪꜱ Gʀᴏᴜᴘ Rᴇᴡᴀʀᴅ Hᴀꜱ Aʟʀᴇᴀᴅʏ Bᴇᴇɴ Cʟᴀɪᴍᴇᴅ Bʏ: {claimed_by}"
        )
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    claimer_name = ud.get("display_name") or (user.first_name or user.username or "User")

    reward = 300
    new_bal = ud["balance"] + reward
    update_user(user.id, balance=new_bal)
    update_group(
        chat.id,
        last_claim_date=today_str,
        claimed_by_name=claimer_name,
        claimed_by_id=user.id,
    )

    await update.message.reply_text(
        f"🎉 Gʀᴏᴜᴘ Rᴇᴡᴀʀᴅ Cʟᴀɪᴍᴇᴅ Bʏ {claimer_name} ࿐\n\n"
        f"💰 Rᴇᴡᴀʀᴅ Aᴅᴅᴇᴅ: ${reward}\n"
        f"🏦 Nᴇᴡ Bᴀʟᴀɴᴄᴇ: ${new_bal}"
    )


COUPONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "coupons.json")


def _get_coupons() -> Dict[str, Any]:
    if not os.path.exists(COUPONS_FILE):
        return {}
    try:
        with open(COUPONS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_coupons(data: Dict[str, Any]):
    try:
        with open(COUPONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


async def _is_admin(chat, user_id, context) -> bool:
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


async def coupons(update, context):
    await update.message.reply_text(
        "🎟 ᴍɪᴋᴏ Cᴜᴛɪᴇ Cᴏᴜᴘᴏɴꜱ Gᴜɪᴅᴇ 🎟\n\n"
        "🔹 /create_coupon - ᴄʀᴇᴀᴛᴇ ᴄᴏᴜᴘᴏɴ ᴄᴏᴅᴇ ꜰᴏʀ ᴜʀ ɢᴄ\n"
        "🔹 /coupon - ᴄʟᴀɪᴍ ᴄᴏᴜᴘᴏɴ ɪɴ ᴛʜɪꜱ ɢᴄ\n"
        "🔹 /del_coupon - ᴅᴇʟᴇᴛᴇ ᴛʜᴇ ᴄᴏᴜᴘᴏɴ ᴄᴏᴅᴇ\n"
        "🔹 /status - ᴄʜᴇᴄᴋ ꜱᴛᴀᴛᴜꜱ ᴏꜰ ᴄᴏᴜᴘᴏɴ ᴄᴏᴅᴇ\n\n"
        "🥀 ʏᴏᴜ ᴄᴀɴ'ᴛ ᴄʀᴇᴀᴛᴇ 2 ᴄᴏᴜᴘᴏɴꜱ ꜰᴏʀ ꜱᴀᴍᴇ ɢʀᴏᴜᴘ. ꜰᴏʀ ᴄʀᴇᴀᴛɪɴɢ ᴀɴᴏᴛʜᴇʀ ᴄᴏᴜᴘᴏɴ ᴄᴏᴅᴇ ʏᴏᴜ ʜᴀᴠᴇ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴘʀᴇᴠɪᴏᴜꜱ ᴏɴᴇ."
    )


async def create_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🎟️ You can only create coupons inside a group!")
        return

    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: /create_coupon <code> <amount> <limit>")
        return

    all_coupons = _get_coupons()
    chat_key = str(chat.id)
    if chat_key in all_coupons:
        await update.message.reply_text("🥀 ʏᴏᴜ ᴄᴀɴ'ᴛ ᴄʀᴇᴀᴛᴇ 2 ᴄᴏᴜᴘᴏɴꜱ ꜰᴏʀ ꜱᴀᴍᴇ ɢʀᴏᴜᴘ. ꜰᴏʀ ᴄʀᴇᴀᴛɪɴɢ ᴀɴᴏᴛʜᴇʀ ᴄᴏᴜᴘᴏɴ ᴄᴏᴅᴇ ʏᴏᴜ ʜᴀᴠᴇ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴘʀᴇᴠɪᴏᴜꜱ ᴏɴᴇ.")
        return

    code = str(args[0]).upper().strip()
    try:
        amount = int(float(str(args[1]).replace("$", "").replace(",", "")))
        limit = int(args[2])
    except Exception:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: /create_coupon <code> <amount> <limit>")
        return

    if amount <= 0 or limit <= 0:
        await update.message.reply_text("❌ Amount and limit must be positive numbers.")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    total_cost = amount * limit

    if ud["balance"] < total_cost:
        await update.message.reply_text(
            f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\n"
            f"Need: ${total_cost} (${amount} × {limit} claims)\n"
            f"Your balance: ${ud['balance']}"
        )
        return

    update_user(user.id, balance=ud["balance"] - total_cost)
    all_coupons[chat_key] = {
        "code": code,
        "amount": amount,
        "limit": limit,
        "claimed_by": [],
        "created_by": user.id,
        "created_at": datetime.now().isoformat(),
    }
    _save_coupons(all_coupons)

    await update.message.reply_text(
        f"✅ <b>Cᴏᴜᴘᴏɴ Cʀᴇᴀᴛᴇᴅ!</b>\n\n"
        f"🎟️ Cᴏᴅᴇ: <code>{code}</code>\n"
        f"💰 Rᴇᴡᴀʀᴅ: ${amount} ᴇᴀᴄʜ\n"
        f"👥 Lɪᴍɪᴛ: {limit} ᴜꜱᴇʀꜱ\n"
        f"💵 Tᴏᴛᴀʟ Pᴏᴏʟ: ${total_cost}\n\n"
        f"Claim command: <code>/coupon {code}</code>",
        parse_mode="HTML",
    )


async def claim_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🎟️ Coupons can only be claimed in group chats!")
        return

    all_coupons = _get_coupons()
    chat_key = str(chat.id)
    if chat_key not in all_coupons:
        await update.message.reply_text("⚠️ Tʜɪꜱ ɢʀᴏᴜᴘ ᴅᴏᴇꜱɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴀᴄᴛɪᴠᴇ ᴄᴏᴜᴘᴏɴꜱ.")
        return

    c = all_coupons[chat_key]
    args = context.args or []
    if not args:
        await update.message.reply_text("🎟️ Usage: <code>/coupon &lt;code&gt;</code>", parse_mode="HTML")
        return

    code_input = str(args[0]).upper().strip()
    if code_input != c["code"]:
        await update.message.reply_text("❌ Invalid coupon code for this group.")
        return

    user = update.effective_user
    if user.id in c["claimed_by"]:
        await update.message.reply_text("⚠️ You have already claimed this coupon!")
        return

    if len(c["claimed_by"]) >= c["limit"]:
        await update.message.reply_text("🥀 This coupon has reached its maximum claim limit.")
        return

    c["claimed_by"].append(user.id)
    _save_coupons(all_coupons)

    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    update_user(user.id, balance=ud["balance"] + c["amount"])

    left = c["limit"] - len(c["claimed_by"])
    await update.message.reply_text(
        f"🎉 <b>Cᴏᴜᴘᴏɴ Cʟᴀɪᴍᴇᴅ!</b>\n"
        f"💰 +${c['amount']} added to your balance!\n"
        f"👥 {left} claim(s) remaining.",
        parse_mode="HTML",
    )


async def del_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🎟️ Coupons can only be deleted in group chats!")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    is_admin = await _is_admin(chat, user.id, context)
    is_prem = ud.get("premium", False)

    if not (is_admin and is_prem):
        await update.message.reply_text("❗️ Yᴏᴜ Mᴜꜱᴛ Bᴇ Pʀᴇᴍɪᴜᴍ Uꜱᴇʀ Aɴᴅ Gʀᴏᴜᴘ Aᴅᴍɪɴ Bᴏᴛʜ Tᴏ ᴅᴇʟᴇᴛᴇ ᴄᴏᴜᴘᴏɴꜱ.")
        return

    all_coupons = _get_coupons()
    chat_key = str(chat.id)
    if chat_key not in all_coupons:
        await update.message.reply_text("⚠️ Nᴏ ᴀᴄᴛɪᴠᴇ ᴄᴏᴜᴘᴏɴꜱ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.")
        return

    c = all_coupons[chat_key]
    remaining_claims = max(0, c["limit"] - len(c["claimed_by"]))
    refund = remaining_claims * c["amount"]

    if refund > 0:
        creator_d = get_user(c["created_by"])
        update_user(c["created_by"], balance=creator_d["balance"] + refund)

    del all_coupons[chat_key]
    _save_coupons(all_coupons)

    await update.message.reply_text(
        f"🗑️ <b>Cᴏᴜᴘᴏɴ <code>{c['code']}</code> Dᴇʟᴇᴛᴇᴅ!</b>\n"
        f"💵 Refunded ${refund} to creator.",
        parse_mode="HTML",
    )


async def coupon_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("ℹ️ Check coupon status in group chats!")
        return

    all_coupons = _get_coupons()
    chat_key = str(chat.id)
    if chat_key not in all_coupons:
        await update.message.reply_text("⚠️ Nᴏ ᴀᴄᴛɪᴠᴇ ᴄᴏᴜᴘᴏɴꜱ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.")
        return

    c = all_coupons[chat_key]
    claimed_count = len(c["claimed_by"])
    left = max(0, c["limit"] - claimed_count)

    await update.message.reply_text(
        f"📊 <b>Cᴏᴜᴘᴏɴ Sᴛᴀᴛᴜꜱ</b>\n\n"
        f"🎟️ Cᴏᴅᴇ: <code>{c['code']}</code>\n"
        f"💰 Rᴇᴡᴀʀᴅ: ${c['amount']} ᴇᴀᴄʜ\n"
        f"👥 Cʟᴀɪᴍᴇᴅ: {claimed_count}/{c['limit']}\n"
        f"✨ Rᴇᴍᴀɪɴɪɴɢ: {left} ᴄʟᴀɪᴍ(ꜱ)\n"
        f"🔄 Sᴛᴀᴛᴜꜱ: {'🟢 Aᴄᴛɪᴠᴇ' if left > 0 else '🔴 Exʜᴀᴜꜱᴛᴇᴅ'}",
        parse_mode="HTML",
    )


HANDLERS = {
    "ph": ph,
    "powers": powers_list,
    "pinfo": pinfo,
    "activate": activate,
    "act": activate,
    "mypowers": mypowers,
    "mp": mypowers,
    "pay": pay,
    "fpay": fpay,
    "claim": claim,
    "coupons": coupons,
    "create_coupon": create_coupon,
    "coupon": claim_coupon,
    "del_coupon": del_coupon,
    "status": coupon_status,
}
