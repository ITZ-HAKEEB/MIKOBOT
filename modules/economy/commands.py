import html
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from modules.utils.storage import (
    get_user,
    update_user,
    get_all_users,
    add_xp,
    global_rank,
    POWERS_CATALOG,
    get_group,
    update_group,
)
from modules.utils.commands_list import ADVAY_NAME

COMING_SOON = "⏳"

NAME_PREFIX = "⎯꯭‌❃⃪꯭‌ "
NAME_SUFFIX = " ࿐"


def _clean_decorations(name: str) -> str:
    s = str(name).strip()
    for _ in range(5):
        s = s.strip()
        matched = False
        for p in ["⎯꯭‌❃⃪꯭‌", "⎯꯭❃⃪꯭", "⎯꯭", "❃⃪", "꯭‌", "꯭", "⎯", "❃"]:
            if s.startswith(p):
                s = s[len(p):].strip()
                matched = True
        if not matched:
            break

    for _ in range(5):
        s = s.strip()
        matched = False
        for sf in ["࿐", "亗", "🌸"]:
            if s.endswith(sf):
                s = s[:-len(sf)].strip()
                matched = True
        if not matched:
            break

    return s.strip()


def _styled_name(raw_name: str) -> str:
    cleaned = _clean_decorations(raw_name)
    if not cleaned:
        cleaned = str(raw_name).strip()
    return f"{NAME_PREFIX}{cleaned}{NAME_SUFFIX}"


def _bold(name: str) -> str:
    return f"<b>{name}</b>"


def _name_for(user_id: int, info=None) -> str:
    if not info:
        info = get_user(user_id)
    raw = info.get("display_name") or info.get("username") or "User"
    return _bold(_styled_name(raw))


async def _econ_gate(update: Update) -> bool:
    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)
    if not chat or getattr(chat, "type", None) == "private":
        return True
    settings = get_group(chat.id)
    if user:
        members = list(settings.get("members") or [])
        if user.id not in members:
            members.append(user.id)
            update_group(chat.id, members=members)
    if settings.get("economy_enabled", True):
        return True
    await update.message.reply_text(
        "🚫 All Economy Commands Have Been Disabled In This Group."
    )
    return False


def _block(stats_block: str) -> str:
    return stats_block


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    username = user.username or user.first_name or "User"
    display_name = user.first_name or username
    get_user(user.id, username, display_name)

    if chat and chat.type != "private":
        bot_username = context.bot.username
        if not bot_username:
            try:
                bot_user = await context.bot.get_me()
                bot_username = bot_user.username
            except Exception:
                bot_username = "i_mikobot"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 START IN DM", url=f"https://t.me/{bot_username}?start=true")]
        ])
        await update.message.reply_text(
            "💙 ᴘʟᴇᴀꜱᴇ ꜱᴛᴀʀᴛ ᴍᴇ ɪɴ ᴅᴍ ᴛᴏ ᴄʜᴇᴄᴋ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ ᴀɴᴅ ᴜꜱᴇ ᴀʟʟ ꜰᴇᴀᴛᴜʀᴇꜱ.",
            reply_markup=kb,
        )
        return

    ud = get_user(user.id, username, display_name)
    keyboard = [
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
    reply_markup = InlineKeyboardMarkup(keyboard)
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
    text = (
        f"💙 ʜɪᴇᴇᴇᴇᴇᴇᴇ  ⎯꯭‌❃⃪꯭‌ {ADVAY_NAME} ࿐ ɪ'ᴍ ᴍɪᴋᴏ - ᴀ ɢᴀᴍɪɴɢ ᴀɴᴅ ᴄʜᴀᴛᴛɪɴɢ ɢɪʀʟ ʜᴀᴠɪɴɢ ʟᴏᴛꜱ ᴏꜰ ꜰᴇᴀᴛᴜʀᴇꜱ ᴛᴏ ᴇɴɢᴀɢᴇ ʏᴏᴜʀ ɢʀᴏᴜᴘ.\n"
        f"{stats_block}\n"
        f"<b>🕹️ ʜᴏᴡ ᴛᴏ ᴘʟᴀʏ?</b>\n"
        f"💰 /bal - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ\n"
        f"👤 /pfp - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴘꜰᴘ\n"
        f"🎁 /daily - ɢᴇᴛ ꜰʀᴇᴇ ᴄᴏɪɴꜱ\n"
        f"🛡️ /protect - ꜱᴀᴠᴇ ʏᴏᴜʀꜱᴇʟꜰ\n"
        f"⚔️ /kill &amp; /rob - ʟᴏᴏᴛ ᴏᴛʜᴇʀꜱ\n\n"
        f"👇 ᴄʜᴏᴏꜱᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ :"
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def bal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        user = update.effective_user

    username = user.username or user.first_name or "User"
    display_name = user.first_name or username
    ud = get_user(user.id, username, display_name)
    toprich_rank = global_rank(user.id, "balance")
    kill_rank = global_rank(user.id, "kills")
    raw_name = ud.get("display_name") or user.first_name or username
    name_display = _styled_name(raw_name)
    status = "alive" if ud.get("status") == "alive" else "dead"
    status_icon = "🔓" if status == "alive" else "💀"
    block = (
        f"👤 <b>Nᴀᴍᴇ:</b> {name_display}\n"
        f"💰 <b>Bᴀʟᴀɴᴄᴇ:</b> ${ud['balance']}\n"
        f"🏆 <b>Gʟᴏʙᴀʟ Rᴀɴᴋ:</b> {toprich_rank}\n"
        f"{status_icon} <b>Sᴛᴀᴛᴜꜱ:</b> {status}\n"
        f"⚔️ <b>Kɪʟʟꜱ:</b> {ud['kills']} (#{kill_rank})\n"
        f"🟤 <b>Lᴇᴠᴇʟ {ud['level']}:</b> {ud['xp']}/{ud['xp_max']}"
    )
    await update.message.reply_text(block, parse_mode="HTML")


async def gems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type != "private":
        await update.message.reply_text("⚠️ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Oɴʟʏ Wᴏʀᴋꜱ Iɴ Tʜᴇ ᴍɪᴋᴏ Bᴏᴛ'ꜱ Dᴍ.")
        return
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    premium = ud.get("premium", False)
    status = "👑 PREMIUM" if premium else "👤 NORMAL"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 ʙᴜʏ ɢᴇᴍꜱ", url="https://t.me/i_mikoo/12"),
            InlineKeyboardButton("💰 ᴀᴅᴅ ꜰᴜɴᴅꜱ", url="https://t.me/i_mikoo/14"),
        ],
        [
            InlineKeyboardButton("ℹ️ ᴀʙᴏᴜᴛ ɢᴇᴍꜱ", url="https://t.me/i_mikoo/12"),
            InlineKeyboardButton("📜 ᴛᴇʀᴍꜱ ᴀɴᴅ ʀᴇꜰᴜɴᴅ", url="https://t.me/i_mikoo"),
        ],
    ])
    text = (
        "<b>KNOW ABOUT MIKO GEMS 💎</b>\n\n"
        "1 gem = $10000 coins = ₹8\n"
        "Check your gems : /pfp\n\n"
        "1) you can convert miko gems into coins using /convert command - only premium users can convert miko gems into coins.\n\n"
        "2) you can use miko gems for playing miko games like card, bomb, hack, roulette and bluff too.\n\n"
        "3) whether it's a premium user or a normal user they can buy miko gems but for using gems you will need the miko premium subscription.\n\n"
        "4) you can buy an unlimited number of gems but you can only use 50 gems per day.\n\n"
        "6) you can't give or rob miko gems like miko coins.\n\n"
        "<b>How to use gems in miko mini games?</b>\n\n"
        "👉 in card game use <code>/bet amount gems</code>\n\n"
        "User A starts the game using : <code>/card 1000</code>\n\n"
        "You have two choices\n\n"
        "<code>/bet 1000 coins</code>\n"
        "<code>/bet 1000 gems</code> - 0.1 gem used 💎\n\n"
        f"👑 <b>ʏᴏᴜʀ ꜱᴛᴀᴛᴜꜱ:</b> {status}"
    )
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)


async def convert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)

    if not ud.get("premium", False):
        await update.message.reply_text(
            "💓 Oɴʟʏ Pʀᴇᴍɪᴜᴍ Uꜱᴇʀꜱ Cᴀɴ Cᴏɴᴠᴇʀᴛ Mɪᴋᴏ Gᴇᴍꜱ Iɴᴛᴏ Cᴏɪɴꜱ.\n"
            "Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ → /pay"
        )
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("💎 <b>Uꜱᴀɢᴇ:</b> <code>/convert &lt;gems_amount&gt;</code>\nRate: 1 Gem = $10,000 Coins", parse_mode="HTML")
        return

    try:
        gems_amount = float(args[0])
        if gems_amount <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("⚠️ Please enter a valid positive number of gems.")
        return

    user_gems = ud.get("gems", 0)
    if user_gems < gems_amount:
        await update.message.reply_text(
            f"❌ Not enough gems! You have {user_gems:.2f} gems.\nBuy more via /gems"
        )
        return

    daily_used = ud.get("daily_gems_used", 0)
    if daily_used + gems_amount > 50:
        remaining_daily = max(0.0, 50 - daily_used)
        await update.message.reply_text(
            f"⚠️ Daily limit reached! You can only use 50 gems per day.\n"
            f"You have {remaining_daily:.2f} gems usage remaining for today."
        )
        return

    coins_gained = int(gems_amount * 10000)
    new_gems = round(user_gems - gems_amount, 2)
    new_balance = ud["balance"] + coins_gained
    new_daily_used = round(daily_used + gems_amount, 2)

    update_user(
        user.id,
        gems=new_gems,
        balance=new_balance,
        daily_gems_used=new_daily_used,
    )

    await update.message.reply_text(
        f"💎 <b>GEMS CONVERTED SUCCESSFULLY!</b>\n\n"
        f"🔄 Converted: <b>{gems_amount} Gems</b> ➡️ <b>${coins_gained} Coins</b>\n"
        f"💰 New Balance: <b>${new_balance}</b>\n"
        f"💎 Remaining Gems: <b>{new_gems:.2f}</b>\n"
        f"📊 Daily Gems Used: <b>{new_daily_used}/50</b>",
        parse_mode="HTML",
    )


async def fgems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    await update.message.reply_text(
        "💎 <b>ʙᴜʏ ɢᴇᴍꜱ ᴡɪᴛʜ ᴛᴇʟᴇɢʀᴀᴍ ꜱᴛᴀʀꜱ</b>\n\n"
        "This option lets non-Indian users buy gems via Telegram Stars.\n"
        "Detailed Star invoice will be implemented when you share pricing tiers.\n\n"
        "Pricing preview:\n"
        "• 1 Gem = 50 Stars (example)\n"
        "• 5 Gems = 200 Stars\n"
        "• 10 Gems = 350 Stars\n",
        parse_mode="HTML",
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        t = update.message.reply_to_message.from_user
        await update.message.reply_text(
            f"🆔 <b>{t.first_name}</b>\n"
            f"Telegram ID: <code>{t.id}</code>\n"
            f"Username: @{t.username or 'N/A'}",
            parse_mode="HTML",
        )
        return
    msg = f"🆔 ʏᴏᴜʀ ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ: <code>{user.id}</code>"
    if chat and chat.type != "private":
        msg += f"\n👥 ɢʀᴏᴜᴘ ɪᴅ: <code>{chat.id}</code>"
    await update.message.reply_text(msg, parse_mode="HTML")


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    if update.effective_chat and update.effective_chat.type != "private":
        await update.message.reply_text("🎁 Yᴏᴜ Cᴀɴ Cʟᴀɪᴍ Dᴀɪʟʏ Rᴇᴡᴀʀᴅ Iɴ Dᴍ Oɴʟʏ.")
        return
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    now = datetime.now()
    if ud.get("last_daily"):
        last = datetime.fromisoformat(ud["last_daily"])
        if now - last < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last)
            hrs, rem = divmod(remaining.seconds, 3600)
            mins, _ = divmod(rem, 60)
            await update.message.reply_text(
                f"⏰ ʏᴏᴜ'ᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ! ᴡᴀɪᴛ {hrs}ʜ {mins}ᴍ."
            )
            return
    reward = 5000 if ud.get("premium") else 2000
    xp_reward = 200 if ud.get("premium") else 50
    gem_reward = 1.0 if ud.get("premium") else 0.5
    update_user(
        user.id,
        balance=ud["balance"] + reward,
        gems=round(ud.get("gems", 0) + gem_reward, 2),
        last_daily=now.isoformat(),
        status="alive",
    )
    add_xp(user.id, xp_reward)
    await update.message.reply_text(
        f"🎁 ʏᴏᴜ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ!\n"
        f"💰 +${reward}\n"
        f"⭐ +{xp_reward} XP\n"
        f"💎 +{gem_reward:.2f} ɢᴇᴍꜱ\n"
        f"ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: ${ud['balance'] + reward}"
    )


async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if not ud.get("premium"):
        await update.message.reply_text("❗️ Oɴʟʏ Pʀᴇᴍɪᴜᴍ Uꜱᴇʀꜱ Cᴀɴ Uꜱᴇ Wᴀʟʟᴇᴛ Fᴏʀ ꜱᴇᴄᴜʀɪɴɢ Sᴀꜰᴇ Uꜱᴇ Oꜰ Wᴀʟʟᴇᴛ.")
        return
    await update.message.reply_text(
        "💰 <b>ꜱᴀꜰᴇᴛʏ ᴡᴀʟʟᴇᴛ</b>\n\n"
        "Protects 70% of your balance from robbery when Vault power is active.\n"
        f"Current balance: ${ud['balance']}\n"
        f"Active powers: {', '.join(ud.get('powers') or ['(none)'])}\n"
        f"Vault status: {'ACTIVE ✅' if 'vault' in (ud.get('powers') or []) else 'inactive'}",
        parse_mode="HTML",
    )


async def protect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    if not context.args:
        await update.message.reply_text("⚠️  Uꜱᴀɢᴇ: /protect 1ᴅ/2ᴅ")
        return
    
    arg = context.args[0].lower().strip().replace("ᴅ", "d")
    if arg not in ("1d", "2d", "1", "2"):
        await update.message.reply_text("⚠️  Uꜱᴀɢᴇ: /protect 1ᴅ/2ᴅ")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    days = 1 if arg in ("1d", "1") else 2
    if days == 2 and not ud.get("premium"):
        await update.message.reply_text("🌟 2-Day protection is only available for Premium users! Buy 1-day or upgrade with /premium.")
        return

    cost = 500 if days == 1 else 900
    if ud["balance"] < cost:
        await update.message.reply_text(
            f"💸 ɴᴇᴇᴅ ${cost}. ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ: ${ud['balance']}"
        )
        return

    import time
    now_ts = time.time()
    protected_until = now_ts + (days * 86400)
    update_user(user.id, balance=ud["balance"] - cost, protected=True, protected_until=protected_until)
    await update.message.reply_text(
        f"🛡️ ʏᴏᴜ'ʀᴇ ɴᴏᴡ ᴘʀᴏᴛᴇᴄᴛᴇᴅ ꜰʀᴏᴍ /kill &amp; /rob ꜰᴏʀ {days} ᴅᴀʏ(ꜱ)! (-${cost})",
        parse_mode="HTML",
    )


def _get_target(update: Update, context: ContextTypes.DEFAULT_TYPE, attacker_id: int = None):
    target = None
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    elif context.args:
        try:
            tid = int(str(context.args[0]).replace("@", "").strip())
            all_users = get_all_users()
            if str(tid) in all_users:

                class F:
                    id = tid
                    first_name = all_users[str(tid)]["username"]
                    username = all_users[str(tid)]["username"]

                target = F()
        except Exception:
            pass
    return target


async def kill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    attacker = update.effective_user
    ad = get_user(attacker.id, attacker.username or attacker.first_name or "User", attacker.first_name)
    target = _get_target(update, context, attacker_id=attacker.id)
    if not target or target.id == attacker.id:
        await update.message.reply_text(
            "⚠️ Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Tᴏ Kɪʟʟ Tʜᴇᴍ."
        )
        return
    tn_raw = getattr(target, "first_name", None) or getattr(target, "username", "User")
    tn = _bold(_styled_name(tn_raw))
    td = get_user(target.id, getattr(target, "username", tn_raw), tn_raw)
    if td.get("status") == "dead":
        await update.message.reply_text(
            "💀 Vɪᴄᴛɪᴍ Iꜱ Aʟʀᴇᴀᴅʏ Dᴇᴀᴅ.\n"
            "✨ Rᴇᴠɪᴠᴇ Vɪᴄᴛɪᴍ Uꜱɪɴɢ → /revive"
        )
        return
    powers = td.get("powers") or []
    if "cloak" in powers:
        powers.remove("cloak")
        update_user(target.id, powers=powers)
        await update.message.reply_html(f"🥷 {tn} used Cloak! Attack blocked.")
        return
    import time
    if td.get("protected"):
        protected_until = td.get("protected_until")
        if protected_until and time.time() > protected_until:
            update_user(target.id, protected=False)
        else:
            await update.message.reply_text(
                "🛡️ Vɪᴄᴛɪᴍ Iꜱ Pʀᴏᴛᴇᴄᴛᴇᴅ Rɪɢʜᴛ Nᴏᴡ.\n"
                "🔒Cʜᴇᴄᴋ Pʀᴏᴛᴇᴄᴛɪᴏɴ Tɪ姆ᴇ → /check"
                .replace("姆", "")
            )
            return
    chance = 0.85 if "rampage" in (ad.get("powers") or []) else 0.65
    success = random.random() < chance
    if success:
        loot_pct = 1.2 if "rampage" in (ad.get("powers") or []) else 1.0
        base_loot = random.randint(50, 250)
        max_loot = int(base_loot * loot_pct)
        victim_loss = min(td.get("balance", 0), max_loot)

        update_user(
            attacker.id,
            balance=ad.get("balance", 0) + max_loot,
            kills=ad.get("kills", 0) + 1,
            daily_kills=ad.get("daily_kills", 0) + 1,
        )
        update_user(target.id, balance=max(0, td.get("balance", 0) - victim_loss), status="dead")
        xp_gain = random.randint(3, 10)
        add_xp(attacker.id, xp_gain)
        await update.message.reply_html(
            f"👤 {_name_for(attacker.id, ad)} Kɪʟʟᴇᴅ {tn}!\n"
            f"💰 Eᴀʀɴᴇᴅ: ${max_loot}, +{xp_gain} Xᴘ"
        )
    else:
        fine = min(ad["balance"], random.randint(5, 30))
        update_user(attacker.id, balance=ad["balance"] - fine)
        await update.message.reply_html(
            f"⚔️ ❌ {_name_for(attacker.id, ad)} Mɪꜱꜱᴇᴅ!\n💸 Lᴏꜱᴛ: ${fine}"
        )


async def rob_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ A Uꜱᴇʀ Tᴏ Rᴏʙ.")
        return

    target = update.message.reply_to_message.from_user
    robber = update.effective_user

    if target.id == robber.id:
        await update.message.reply_text("⚠️ You cannot rob yourself!")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: /rob <ᴀᴍᴏᴜɴᴛ>")
        return

    try:
        amount = int(args[0])
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: /rob <ᴀᴍᴏᴜɴᴛ>")
        return

    rd = get_user(robber.id, robber.username or robber.first_name or "User", robber.first_name)
    td = get_user(target.id, target.username or target.first_name or "User", target.first_name)

    if td.get("balance", 0) < amount:
        await update.message.reply_text(f"💸 Target only has ${td.get('balance', 0)} to rob!")
        return

    powers = td.get("powers") or []
    if "cloak" in powers:
        powers.remove("cloak")
        update_user(target.id, powers=powers)
        await update.message.reply_html(f"🥷 Target used Cloak! Robbery blocked.")
        return
    import time
    if td.get("protected"):
        protected_until = td.get("protected_until")
        if protected_until and time.time() > protected_until:
            update_user(target.id, protected=False)
        else:
            await update.message.reply_text(
                "🛡️ Vɪᴄᴛɪᴍ Iꜱ Pʀᴏᴛᴇᴄᴛᴇᴅ Rɪɢʜᴛ Nᴏᴡ.\n"
                "🔒Cʜᴇᴄᴋ Pʀᴏᴛᴇᴄᴛɪᴏɴ Tɪ姆ᴇ → /check"
                .replace("姆", "")
            )
            return

    gained = int(amount * 0.90)

    update_user(target.id, balance=td.get("balance", 0) - amount)
    update_user(
        robber.id,
        balance=rd.get("balance", 0) + gained,
        daily_robs=rd.get("daily_robs", 0) + 1,
        robs=rd.get("robs", 0) + 1,
    )

    a_name = rd.get("display_name") or getattr(robber, "full_name", None) or robber.first_name or "User"
    t_name = td.get("display_name") or getattr(target, "full_name", None) or target.first_name or "User"

    a_mention = f'<a href="tg://user?id={robber.id}">{html.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={target.id}">{html.escape(t_name)}</a>'

    text = (
        f"👤 {a_mention} Rᴏʙʙᴇᴅ ${amount} Fʀᴏᴍ {t_mention}\n"
        f"💰 Gᴀɪɴᴇᴅ ${gained}, +0 Xᴘ Aꜰᴛᴇʀ 10% Dᴇᴅᴜᴄᴛɪᴏɴ."
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    target_id = user.id
    tn_raw = user.first_name or user.username or "You"
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        t = update.message.reply_to_message.from_user
        target_id = t.id
        tn_raw = t.first_name or t.username or "User"
        get_user(target_id, t.username or tn_raw, t.first_name)
    tn = _bold(_styled_name(tn_raw))
    td = get_user(target_id)
    if td.get("status") != "dead":
        await update.message.reply_html(f"✨ {tn} Iꜱ Aʟʀᴇᴀᴅʏ Aʟɪᴠᴇ!")
        return
    cost = 500
    now = datetime.now()
    is_free = True
    if ud.get("last_free_revive"):
        try:
            last = datetime.fromisoformat(ud["last_free_revive"])
            if now - last < timedelta(hours=24):
                is_free = False
        except Exception:
            is_free = True

    if is_free:
        update_user(user.id, last_free_revive=now.isoformat())
        update_user(target_id, status="alive")
        await update.message.reply_html(
            f"👤 {_name_for(user.id, ud)} Rᴇᴠɪᴠᴇᴅ {tn}! 🎁 (Fʀᴇᴇ Dᴀɪʟʏ Rᴇᴠɪᴠᴇ)"
        )
        return

    if ud["balance"] < cost:
        await update.message.reply_text(
            f"💸 Yᴏᴜ Nᴇᴇᴅ ${cost} Tᴏ Rᴇᴠɪᴠᴇ, Bᴜᴛ Yᴏᴜ Hᴀᴠᴇ Oɴʟʏ ${ud['balance']}"
        )
        return
    update_user(user.id, balance=ud["balance"] - cost)
    update_user(target_id, status="alive")
    await update.message.reply_html(
        f"👤 {_name_for(user.id, ud)} Rᴇᴠɪᴠᴇᴅ {tn}! -${cost}"
    )


async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if not (update.message.reply_to_message and update.message.reply_to_message.from_user):
        await update.message.reply_text("💸 ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜꜱᴇʀ: /give <amount>")
        return
    if not context.args:
        await update.message.reply_text("💸 ᴜꜱᴀɢᴇ: ʀᴇᴘʟʏ + /give <amount>")
        return
    try:
        amount = max(0, int(float(str(context.args[0]).replace("$", "").replace(",", ""))))
    except Exception:
        await update.message.reply_text("💸 ᴜꜱᴀɢᴇ: ʀᴇᴘʟʏ + /give 50")
        return
    if amount <= 0 or amount > ud["balance"]:
        await update.message.reply_text(f"💸 ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ. ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ: ${ud['balance']}")
        return
    t = update.message.reply_to_message.from_user
    td = get_user(t.id, t.username or t.first_name or "User", t.first_name)
    
    tax = int(amount * 0.10)
    received = amount - tax
    new_bal = ud["balance"] - amount

    update_user(user.id, balance=new_bal)
    update_user(t.id, balance=td["balance"] + received)

    a_name = ud.get("display_name") or getattr(user, "full_name", None) or user.first_name or "User"
    t_name = td.get("display_name") or getattr(t, "full_name", None) or t.first_name or "User"

    a_mention = f'<a href="tg://user?id={user.id}">{html.escape(a_name)}</a>'
    t_mention = f'<a href="tg://user?id={t.id}">{html.escape(t_name)}</a>'

    await update.message.reply_text(
        f"💸 {a_mention} ɢᴀᴠᴇ ${amount} ᴛᴏ {t_mention}!\n"
        f"👤 {t_mention} Rᴇᴄᴇɪᴠᴇᴅ ${received}\n"
        f"💸 Tᴀx: ${tax} (10%)\n"
        f"ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: ${new_bal}",
        parse_mode="HTML",
    )


async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    br = global_rank(user.id, "balance")
    kr = global_rank(user.id, "kills")
    await update.message.reply_text(
        f"🏆 <b>ʏᴏᴜʀ ʀᴀɴᴋ</b>\n"
        f"Global Rank: {ud['rank']}\n"
        f"💰 Balance Rank: #{br}\n"
        f"⚔️ Kills Rank: #{kr}\n"
        f"🟤 Level {ud['level']} ({ud['xp']}/{ud['xp_max']})",
        parse_mode="HTML",
    )


def render_toprich_message(chat_id: int, mode: str = "global"):
    data = get_all_users()
    g_info = get_group(chat_id) if chat_id else {}
    g_members = set(g_info.get("members", []))

    if mode == "group" and g_members:
        filtered = {k: v for k, v in data.items() if int(k) in g_members}
        if not filtered:
            filtered = data
        title = "🏆 <b>Gʀᴏᴜᴘ Tᴏᴘ 10 Rɪᴄʜᴇꜱᴛ:</b>"
        btn = InlineKeyboardButton("🌍 Global Top 10", callback_data=f"toprich_global_{chat_id}")
    else:
        filtered = data
        title = "🏆 <b>Gʟᴏʙᴀʟ Tᴏᴘ 10 Rɪᴄʜᴇꜱᴛ:</b>"
        btn = InlineKeyboardButton("👥 Group Top 10", callback_data=f"toprich_group_{chat_id}")

    ranked = sorted(filtered.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]

    lines = [title, ""]
    for uid, info in ranked:
        name = info.get("display_name") or info.get("first_name") or info.get("username") or f"User {uid}"
        icon = "💓" if info.get("premium") else "👤"
        mention = f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
        bal = info.get("balance", 0)
        lines.append(f"{icon} {mention}: ${bal}")

    lines.append("")
    lines.append("💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ")
    lines.append("✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : /pay")

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup([[btn]])
    return text, keyboard


async def toprich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0
    text, keyboard = render_toprich_message(chat_id, "global")
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


def render_topkill_message(chat_id: int, mode: str = "global"):
    data = get_all_users()
    g_info = get_group(chat_id) if chat_id else {}
    g_members = set(g_info.get("members", []))

    if mode == "group" and g_members:
        filtered = {k: v for k, v in data.items() if int(k) in g_members}
        if not filtered:
            filtered = data
        title = "⚔️ <b>Gʀᴏᴜᴘ Tᴏᴘ 10 Kɪʟʟᴇʀꜱ:</b>"
        btn = InlineKeyboardButton("🌍 Global Top 10", callback_data=f"topkill_global_{chat_id}")
    else:
        filtered = data
        title = "⚔️ <b>Tᴏᴘ 10 Kɪʟʟᴇʀꜱ:</b>"
        btn = InlineKeyboardButton("👥 Group Top 10", callback_data=f"topkill_group_{chat_id}")

    ranked = sorted(filtered.items(), key=lambda x: x[1].get("kills", 0), reverse=True)[:10]

    lines = [title, ""]
    for uid, info in ranked:
        name = info.get("display_name") or info.get("first_name") or info.get("username") or f"User {uid}"
        icon = "💓" if info.get("premium") else "👤"
        mention = f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
        kills = info.get("kills", 0)
        lines.append(f"{icon} {mention}: {kills}")

    lines.append("")
    lines.append("💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n")
    lines.append("✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : /pay")

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup([[btn]])
    return text, keyboard


async def topkill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0
    text, keyboard = render_topkill_message(chat_id, "global")
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


def render_toprob_message(chat_id: int, mode: str = "global"):
    data = get_all_users()
    g_info = get_group(chat_id) if chat_id else {}
    g_members = set(g_info.get("members", []))

    if mode == "group" and g_members:
        filtered = {k: v for k, v in data.items() if int(k) in g_members}
        if not filtered:
            filtered = data
        title = "🥷 <b>Gʀᴏᴜᴘ Tᴏᴘ 10 Rᴏʙʙᴇʀꜱ:</b>"
        btn = InlineKeyboardButton("🌍 Global Top 10", callback_data=f"toprob_global_{chat_id}")
    else:
        filtered = data
        title = "🥷 <b>Tᴏᴘ 10 Rᴏʙʙᴇʀꜱ:</b>"
        btn = InlineKeyboardButton("👥 Group Top 10", callback_data=f"toprob_group_{chat_id}")

    ranked = sorted(filtered.items(), key=lambda x: x[1].get("robs", 0), reverse=True)[:10]

    lines = [title, ""]
    for uid, info in ranked:
        name = info.get("display_name") or info.get("first_name") or info.get("username") or f"User {uid}"
        icon = "💓" if info.get("premium") else "👤"
        mention = f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
        robs_count = info.get("robs", 0)
        lines.append(f"{icon} {mention}: {robs_count}")

    lines.append("")
    lines.append("💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n")
    lines.append("✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : /pay")

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup([[btn]])
    return text, keyboard


async def toprob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await _econ_gate(update)):
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0
    text, keyboard = render_toprob_message(chat_id, "global")
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


HANDLERS = {
    "start": start,
    "bal": bal,
    "gems": gems,
    "fgems": fgems,
    "id": cmd_id,
    "daily": daily,
    "wallet": wallet,
    "protect": protect_cmd,
    "kill": kill_cmd,
    "rob": rob_cmd,
    "revive": revive,
    "give": give,
    "rank": rank_cmd,
    "toprich": toprich,
    "topkill": topkill,
    "toprob": toprob,
    "convert": convert_cmd,
}
