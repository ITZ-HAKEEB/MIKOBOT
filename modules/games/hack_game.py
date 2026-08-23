import random
import html
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes
from modules.utils.storage import get_user, update_user, add_xp

# In-memory hack games per chat_id: Dict[int, Dict[str, Any]]
HACK_GAMES: Dict[int, Dict[str, Any]] = {}


def _calculate_hacks_glitches(secret: str, guess: str):
    hacks = 0
    glitches = 0
    secret_unmatched = []
    guess_unmatched = []

    for s_char, g_char in zip(secret, guess):
        if s_char == g_char:
            hacks += 1
        else:
            secret_unmatched.append(s_char)
            guess_unmatched.append(g_char)

    for g_char in guess_unmatched:
        if g_char in secret_unmatched:
            glitches += 1
            secret_unmatched.remove(g_char)

    return hacks, glitches


async def cmd_hack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🎮 You can only start the Hack game inside a group!")
        return

    chat_id = chat.id
    if chat_id in HACK_GAMES:
        await update.message.reply_text(
            "⚠️ A Hack game is already active in this group!\n"
            "Use /guess <pass> to play or /end to cancel.",
            parse_mode="HTML",
        )
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("💡 Uꜱᴀɢᴇ: /hack amount digits (3-6)")
        return

    try:
        amount = int(float(str(args[0]).replace("$", "").replace(",", "")))
        digits = int(args[1])
    except Exception:
        await update.message.reply_text("💡 Uꜱᴀɢᴇ: /hack amount digits (3-6)")
        return

    if amount < 100:
        await update.message.reply_text("❌ Minimum game amount is $100.")
        return

    if digits < 3 or digits > 6:
        await update.message.reply_text("💡 Uꜱᴀɢᴇ: /hack amount digits (3-6)")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if ud["balance"] < amount:
        await update.message.reply_text(
            f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nNeed: ${amount} | You have: ${ud['balance']}"
        )
        return

    # Deduct host entry fee
    update_user(user.id, balance=ud["balance"] - amount)

    # Generate secret password of given digits
    secret = "".join([str(random.randint(0, 9)) for _ in range(digits)])

    HACK_GAMES[chat_id] = {
        "host_id": user.id,
        "host_name": user.first_name or "Host",
        "entry_fee": amount,
        "digits": digits,
        "secret": secret,
        "total_pool": amount,
        "players": {},
        "guesses": 0,
    }

    await update.message.reply_text(
        "💻 <b>Hᴀᴄᴋᴇʀ Lᴏʙʙʏ Sᴛᴀʀᴛᴇᴅ!</b>\n\n"
        f"💰 <b>Eɴᴛʀʏ Fᴇᴇ:</b> {amount} Cᴏɪɴꜱ\n"
        f"🔐 <b>Tᴀʀɢᴇᴛ Lᴇɴɢᴛʜ:</b> {digits} Dɪɢɪᴛꜱ\n\n"
        f"👉 <b>Rᴇɢɪꜱᴛᴇʀ Uꜱɪɴɢ:</b> <code>/register {amount} gems/coins</code>",
        parse_mode="HTML",
    )


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in HACK_GAMES:
        await update.message.reply_text("⚠️ No active Hack game in this group. Start one with /hack <amount> <digits>!")
        return

    args = context.args or []
    if len(args) > 1:
        c_str = str(args[1]).lower().strip()
        if c_str in ("coins", "coin"):
            currency = "coins"
        elif c_str in ("gems", "gem"):
            currency = "gems"
        else:
            await update.message.reply_text("🚫 Iɴᴠᴀʟɪᴅ ᴄᴜʀʀᴇɴᴄʏ. Uꜱᴇ 'gems' ᴏʀ 'coins'.")
            return
    else:
        currency = "coins"

    game = HACK_GAMES[chat_id]
    user = update.effective_user

    if user.id in game["players"]:
        await update.message.reply_text("⚠️ You are already registered in this Hack game!")
        return

    if currency == "gems":
        gem_cost = round(fee / 1000.0, 2)
        if gem_cost < 0.1:
            gem_cost = 0.1
        if ud.get("gems", 0.0) < gem_cost:
            await update.message.reply_text(f"💎 Insufficient gems! Need: {gem_cost} gems | You have: {ud.get('gems', 0.0):.2f}")
            return
        update_user(user.id, gems=round(ud.get("gems", 0.0) - gem_cost, 2))
    else:
        if ud["balance"] < fee:
            await update.message.reply_text(
                f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nRequired to join: ${fee} | You have: ${ud['balance']}"
            )
            return
        update_user(user.id, balance=ud["balance"] - fee)

    game["players"][user.id] = fee
    game["total_pool"] += fee
    total_count = len(game["players"])

    mention = f'<a href="tg://user?id={user.id}">{html.escape(user.first_name or "Player")}</a>'
    await update.message.reply_text(
        f"👤 {mention} ᴊᴏɪɴᴇᴅ ᴛʜᴇ Hᴀᴄᴋ Tᴇᴀᴍ! (Tᴏᴛᴀʟ: {total_count})",
        parse_mode="HTML",
    )


async def cmd_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in HACK_GAMES:
        await update.message.reply_text("⚠️ No active Hack game in this group. Start one with /hack <amount> <digits>!")
        return

    game = HACK_GAMES[chat_id]
    user = update.effective_user

    if user.id not in game["players"]:
        await update.message.reply_text(
            f"⚠️ Only registered players can guess!\nRegister with: <code>/register {game['entry_fee']}</code>",
            parse_mode="HTML",
        )
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"⚠️ Uꜱᴀɢᴇ: <code>/guess &lt;{game['digits']} digits&gt;</code>\nExample: <code>/guess {'1' * game['digits']}</code>",
            parse_mode="HTML",
        )
        return

    guess_str = str(args[0]).strip()
    if len(guess_str) != game["digits"] or not guess_str.isdigit():
        await update.message.reply_text(
            f"❌ Your guess must be exactly {game['digits']} digits! (e.g. <code>/guess {'1' * game['digits']}</code>)",
            parse_mode="HTML",
        )
        return

    game["guesses"] += 1
    hacks, glitches = _calculate_hacks_glitches(game["secret"], guess_str)

    if hacks == game["digits"]:
        # Player cracked the password!
        prize = game["total_pool"]
        ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
        update_user(user.id, balance=ud["balance"] + prize)
        add_xp(user.id, 50)
        del HACK_GAMES[chat_id]

        await update.message.reply_text(
            f"🎉 <b>BOOM! YOU HACKED IT!</b> 🔓\n\n"
            f"👑 <b>Hacker:</b> <a href=\"tg://user?id={user.id}\">{html.escape(user.first_name or 'User')}</a>\n"
            f"🔑 <b>Password:</b> <code>{guess_str}</code>\n"
            f"💰 <b>Total Won:</b> ${prize}\n\n"
            f"Congratulations on cracking Miko's mainframe! 🌸",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"🔍 <b>Guess:</b> <code>{guess_str}</code>\n\n"
            f"🟢 <b>HACKS:</b> {hacks} (right position)\n"
            f"🟡 <b>GLITCHES:</b> {glitches} (wrong position)\n\n"
            f"Keep going! You can do it! ✨",
            parse_mode="HTML",
        )


async def cmd_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in HACK_GAMES:
        await update.message.reply_text("🚫 Nᴏ ᴀᴄᴛɪᴠᴇ Hᴀᴄᴋ ɢᴀᴍᴇ ᴛᴏ ᴄᴀɴᴄᴇʟ ʜᴇʀᴇ.")
        return

    game = HACK_GAMES[chat_id]
    user = update.effective_user

    # Only host can end
    if user.id != game["host_id"]:
        await update.message.reply_text("❌ Only the host who started the game can end it.")
        return

    # Refund host
    host_id = game["host_id"]
    host_ud = get_user(host_id)
    update_user(host_id, balance=host_ud["balance"] + game["entry_fee"])

    # Refund registered players
    for p_id, p_fee in game["players"].items():
        p_ud = get_user(p_id)
        update_user(p_id, balance=p_ud["balance"] + p_fee)

    del HACK_GAMES[chat_id]

    await update.message.reply_text("👥 Nᴏᴛ ᴇɴᴏᴜɢʜ ᴘʟᴀʏᴇʀꜱ ᴊᴏɪɴᴇᴅ. Gᴀᴍᴇ Cᴀɴᴄᴇʟʟᴇᴅ ᴀɴᴅ ꜰᴜɴᴅꜱ ʀᴇꜰᴜɴᴅᴇᴅ.")
