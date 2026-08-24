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


STARS_PLANS = {
    "stars_1_month": {"title": "1 Month VIP Premium", "stars": 10, "gems": 1.0, "months": 1},
    "stars_2_months": {"title": "2 Months VIP Premium", "stars": 15, "gems": 2.0, "months": 2},
    "stars_3_months": {"title": "3 Months VIP Premium", "stars": 20, "gems": 3.0, "months": 3},
    "stars_6_months": {"title": "6 Months VIP Premium", "stars": 40, "gems": 6.0, "months": 6},
    "stars_12_months": {"title": "12 Months VIP Premium", "stars": 50, "gems": 12.0, "months": 12},
}


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User command /pay: Show Baka Premium Access menu matching screenshot"""
    user = update.effective_user
    uid = user.id if user else 7408854697

    msg = (
        "<b>BAKA PREMIUM ACCESS</b>\n\n"
        "IMPORTANT NOTE: IF YOU ARE NOT AN INDIAN USER AND UNBALE TO BUY PREMIUM "
        "FROM THE SITE THEN YOU CAN BUY BAKA PREMIUM USING TELEGRAM STARS USING "
        "THIS COMMAND : /spay\n\n"
        "IF YOU ARE FROM INDIA THEN YOU CAN BUY BAKA PREMIUM SIMPLY FROM THE "
        "BELOW PAY NOW BUTTON\n"
        "CHECK YOUR TELEGRAM ID : /id\n\n"
        "YOU CAN REPORT ANY ISSUE THROUGH THE DM OF THIS CHANNEL : @Developer_World_Advay"
    )

    checkout_url = f"https://mike-payment.vercel.app/checkout.html?user_id={uid}"
    add_funds_url = f"https://mike-payment.vercel.app/app.html?tab=premium&user_id={uid}"
    features_url = "https://mike-payment.vercel.app/"
    refund_url = "https://mike-payment.vercel.app/refund.html"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 PAY NOW", web_app=WebAppInfo(url=checkout_url)),
            InlineKeyboardButton("💰 ADD FUNDS", web_app=WebAppInfo(url=add_funds_url)),
        ],
        [
            InlineKeyboardButton("💗 FEATURES", url=features_url),
            InlineKeyboardButton("📜 TERMS AND REFUND", url=refund_url),
        ],
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="HTML")


async def spay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct 1-tap Telegram Stars payment invoice: /spay <user_id> [months]"""
    if update.effective_chat and update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Oɴʟʏ Wᴏʀᴋꜱ Iɴ Tʜᴇ ᴍɪᴋᴏ Bᴏᴛ'ꜱ Dᴍ.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ <b>Usage :</b> <code>/spay user_id</code>", parse_mode="HTML")
        return

    target_id_str = context.args[0].strip()
    if not target_id_str.isdigit():
        await update.message.reply_text("⚠️ <b>Usage :</b> <code>/spay user_id</code>", parse_mode="HTML")
        return

    target_uid = int(target_id_str)
    chat_id = update.effective_chat.id

    # Support optional month parameter: /spay <user_id> [1|2|3|6|12]
    months = 1
    if len(context.args) > 1 and context.args[1].isdigit():
        req_m = int(context.args[1])
        if req_m in [1, 2, 3, 6, 12]:
            months = req_m

    plan_map = {
        1: ("stars_1_month", 10, 30, 1.0),
        2: ("stars_2_months", 15, 60, 2.0),
        3: ("stars_3_months", 20, 90, 3.0),
        6: ("stars_6_months", 40, 180, 6.0),
        12: ("stars_12_months", 50, 365, 12.0),
    }

    plan_key, stars_amount, days_count, free_gems = plan_map.get(months, ("stars_1_month", 10, 30, 1.0))

    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title="miko premium access",
            description=f"Pᴀʏ {stars_amount} Sᴛᴀʀꜱ Tᴏ Bᴜʏ {days_count} Dᴀʏꜱ Mɪᴋᴏ Pʀᴇᴍɪᴜᴍ Aᴄᴄᴇꜱꜱ Iɴ Pʀᴏᴠɪᴅᴇᴅ Uꜱᴇʀ ID.",
            payload=f"fpay_{target_uid}_{plan_key}",
            provider_token="",  # Must be empty string for Telegram Stars (XTR)
            currency="XTR",
            prices=[LabeledPrice(label="miko premium access", amount=stars_amount)],
        )
    except Exception as e:
        print(f"Error sending Stars invoice: {e}")
        await update.message.reply_text(f"⚠️ Could not open Stars checkout invoice: {e}")


async def fpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias to spay command for backward compatibility"""
    await spay_cmd(update, context)


async def send_stars_invoice(query, context, callback_data: str):
    """Sends native Telegram Stars invoice modal from button callbacks"""
    target_uid = query.from_user.id
    raw_key = callback_data.replace("buy_stars_", "")

    plan_key = None
    for pk in STARS_PLANS.keys():
        clean_pk = pk.replace("stars_", "")
        if raw_key.startswith(clean_pk):
            remainder = raw_key[len(clean_pk):]
            if remainder.startswith("_") and remainder[1:].isdigit():
                target_uid = int(remainder[1:])
            plan_key = pk
            break
        elif raw_key == pk:
            plan_key = pk
            break

    if not plan_key or plan_key not in STARS_PLANS:
        await query.answer("⚠️ Invalid plan selected!", show_alert=True)
        return

    plan = STARS_PLANS[plan_key]
    chat_id = query.message.chat_id

    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title="miko premium access",
            description=f"Pᴀʏ {plan['stars']} Sᴛᴀʀꜱ Tᴏ Bᴜʏ {plan['months'] * 30} Dᴀʏꜱ Mɪᴋᴏ Pʀᴇᴍɪᴜᴍ Aᴄᴄᴇꜱꜱ Iɴ Pʀᴏᴠɪᴅᴇᴅ Uꜱᴇʀ ID.",
            payload=f"fpay_{target_uid}_{plan_key}",
            provider_token="",  # Must be empty string for Telegram Stars (XTR)
            currency="XTR",
            prices=[LabeledPrice(label="miko premium access", amount=plan["stars"])],
        )
        await query.answer()
    except Exception as e:
        print(f"Error sending Stars invoice: {e}")
        await query.answer("⚠️ Could not open Stars checkout invoice.", show_alert=True)


async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer Telegram Stars pre-checkout query"""
    query = update.pre_checkout_query
    try:
        print(f"⭐ [STARS] Received pre_checkout_query from user {query.from_user.id} ({query.from_user.first_name}) | Payload: {query.invoice_payload}")
        await query.answer(ok=True)
        print("⭐ [STARS] PreCheckoutQuery answered ok=True successfully!")
    except Exception as e:
        print(f"❌ [STARS] Error answering pre-checkout query: {e}")
        try:
            await query.answer(ok=False, error_message="Could not process checkout. Please try again.")
        except Exception:
            pass


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered automatically when payment via Telegram Stars succeeds"""
    try:
        payment = update.message.successful_payment
        user = update.effective_user
        payload = payment.invoice_payload
        print(f"🎉 [STARS] SUCCESSFUL PAYMENT from {user.id} ({user.first_name}) | Amount: {payment.total_amount} Stars | Payload: {payload}")

        target_uid = user.id
        free_gems = 1.0
        days = 30
        plan_title = "30 Days Miko Premium Access"

        if payload.startswith("fpay_"):
            parts = payload.split("_")
            if len(parts) > 1 and parts[1].isdigit():
                target_uid = int(parts[1])

            for pk, pv in STARS_PLANS.items():
                if pk in payload:
                    plan_title = pv["title"]
                    free_gems = pv.get("gems", 1.0)
                    days = pv.get("months", 1) * 30
                    break

        ud = get_user(target_uid)
        new_gems = round(ud.get("gems", 0.0) + free_gems, 2)
        update_user(target_uid, premium=True, gems=new_gems)

        text = (
            f"🎉 <b>ᴍɪᴋᴏ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
            f"👤 <b>Target User ID:</b> <code>{target_uid}</code>\n"
            f"👑 <b>Plan:</b> {plan_title}\n"
            f"⭐ <b>Stars Paid:</b> {payment.total_amount} ⭐\n"
            f"💎 <b>Free Bonus Gems:</b> +{int(free_gems)} 💎\n"
            f"✨ <b>Total Gems Balance:</b> {new_gems} 💎\n"
            f"🌟 <b>VIP Status:</b> {days} Days Active\n\n"
            f"🌟 <i>Premium benefits are active! Check with /pfp or /bal.</i>"
        )

        await update.message.reply_text(text, parse_mode="HTML")
        print(f"🎉 [STARS] Premium credited and confirmation sent to {target_uid}!")
    except Exception as e:
        print(f"❌ [STARS] Error in successful_payment_callback: {e}")

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


async def deposit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User command: /deposit <amount> or /topup <amount> to submit a fund top-up request."""
    user = update.effective_user
    if not user:
        return

    args = context.args or []
    if not args:
        msg = (
            "💳 <b>Hᴏᴡ ᴛᴏ Aᴅᴅ Fᴜɴᴅꜱ ᴛᴏ Yᴏᴜʀ Pʀᴇᴍɪᴜᴍ Wᴀʟʟᴇᴛ:</b>\n\n"
            "1️⃣ <b>Pay via Razorpay:</b> <a href=\"https://razorpay.me/@nishkarshkumar\">razorpay.me/@nishkarshkumar</a>\n"
            "2️⃣ <b>Submit Verification:</b> <code>/deposit &lt;amount_in_inr&gt;</code>\n\n"
            "<i>Example:</i> <code>/deposit 50</code>\n\n"
            "⚡ <i>Admins will verify and approve your funds with 1 tap in the Log Group!</i>"
        )
        await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)
        return

    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for amount. Example: <code>/deposit 50</code>", parse_mode="HTML")
        return

    if amount < 10:
        await update.message.reply_text("❌ Minimum deposit amount is ₹10 INR.")
        return

    import time
    req_id = str(int(time.time()))[-6:]
    name = user.first_name or user.username or f"User {user.id}"

    from modules.utils.logger import send_fund_approval_log
    await send_fund_approval_log(
        bot=context.bot,
        user_id=user.id,
        user_name=name,
        amount=amount,
        req_id=req_id,
        method="Razorpay.me / UPI",
        notes=f"Submitted via /deposit by @{user.username}" if user.username else "Submitted via /deposit"
    )

    confirm_msg = (
        f"💳 <b>Aᴅᴅ Fᴜɴᴅ RᴇQᴜᴇꜱᴛ Sᴜʙᴍɪᴛᴛᴇᴅ!</b>\n\n"
        f"💵 <b>Amount:</b> <b>₹{amount:,.2f} INR</b>\n"
        f"🔑 <b>Request ID:</b> <code>REQ-{req_id}</code>\n"
        f"🔗 <b>Gateway Portal:</b> <a href=\"https://razorpay.me/@nishkarshkumar\">razorpay.me/@nishkarshkumar</a>\n\n"
        f"⏳ <i>An approval request with Accept/Reject buttons has been sent to our Log Group. Your balance will be credited as soon as an Admin approves it!</i>"
    )
    await update.message.reply_text(confirm_msg, parse_mode="HTML", disable_web_page_preview=True)


premium = spay_cmd
spay = spay_cmd
pay = pay_cmd

HANDLERS = {
    "ph": ph,
    "powers": powers_list,
    "pinfo": pinfo,
    "activate": activate,
    "act": activate,
    "mypowers": mypowers,
    "mp": mypowers,
    "pay": pay_cmd,
    "spay": spay_cmd,
    "starspay": spay_cmd,
    "stars_pay": spay_cmd,
    "premium": pay_cmd,
    "prem": pay_cmd,
    "fpay": spay_cmd,
    "deposit": deposit_cmd,
    "topup": deposit_cmd,
    "claim": claim,
    "coupons": coupons,
    "create_coupon": create_coupon,
    "coupon": claim_coupon,
    "del_coupon": del_coupon,
    "status": coupon_status,
}
