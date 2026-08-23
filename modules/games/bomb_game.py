import random
import html
import asyncio
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from modules.utils.storage import get_user, update_user, add_xp

# In-memory bomb games: Dict[chat_id, GameState]
BOMB_GAMES: Dict[int, Dict[str, Any]] = {}


async def _is_admin(chat, user_id, context) -> bool:
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


async def cmd_bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("💣 You can only start the Bomb Game in a group!")
        return

    chat_id = chat.id
    if chat_id in BOMB_GAMES:
        await update.message.reply_text("⚠️ A Bomb Game is already active in this group!")
        return

    args = context.args or []
    amount = 500
    if args:
        try:
            amount = int(float(str(args[0]).replace("$", "").replace(",", "")))
        except Exception:
            amount = 500

    if amount < 50:
        await update.message.reply_text("❌ Minimum entry fee is $50.")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if ud["balance"] < amount:
        await update.message.reply_text(f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nNeed: ${amount} | You have: ${ud['balance']}")
        return

    update_user(user.id, balance=ud["balance"] - amount)

    BOMB_GAMES[chat_id] = {
        "status": "lobby",
        "host_id": user.id,
        "entry_fee": amount,
        "players": [user.id],
        "player_names": {user.id: user.first_name or "Host"},
        "holder": user.id,
        "ticks_to_explode": random.randint(2, 5),
        "total_pool": amount,
    }

    await update.message.reply_text(
        "🎮 <b>Bᴏᴍʙ Gᴀᴍᴇ Rᴜʟᴇꜱ</b> 🎮\n\n"
        f"💚 /bomb {amount} — Sᴛᴀʀᴛ A Bᴏᴍʙ Gᴀᴍᴇ Wɪᴛʜ Eɴᴛʀʏ Fᴇᴇ 💸\n"
        f"💚 /joinbomb — Jᴏɪɴ Tʜᴇ Gᴀᴍᴇ Bᴇꜰᴏʀᴇ Iᴛ Sᴛᴀʀᴛꜱ\n"
        f"💚 /pass — Pᴀꜱꜱ Tʜᴇ Bᴏᴍʙ Wʜᴇɴ Yᴏᴜ Hᴀᴠᴇ Iᴛ\n"
        f"💚 /rank — Cʜᴇᴄᴋ Yᴏᴜʀ Oʀ Yᴏᴜʀ Fʀɪᴇɴᴅ'ꜱ Rᴀɴᴋ\n"
        f"💚 /leaders — Cʜᴇᴄᴋ Bᴏᴍʙ Gᴀᴍᴇ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ\n\n"
        "➡️ <b>Rᴜʟᴇꜱ:</b>\n"
        "🌸 Bᴏᴍʙ Exᴘʟᴏᴅᴇꜱ Rᴀɴᴅᴏᴍʟʏ Eᴠᴇʀʏ Rᴏᴜɴᴅ 💥\n"
        "🌸 Lᴀꜱᴛ Pʟᴀʏᴇʀ Aʟɪᴠᴇ Wɪɴꜱ Tʜᴇ Pᴏᴛ 🤩\n\n"
        "🐺 <b>Aᴅᴍɪɴ Pᴏᴡᴇʀ:</b>\n"
        "• Aᴅᴍɪɴꜱ Cᴀɴ Cᴀɴᴄᴇʟ Gᴀᴍᴇ Uꜱɪɴɢ /bombcancel ❌\n\n"
        f"Type <code>/joinbomb</code> to join with ${amount}!",
        parse_mode="HTML",
    )


async def cmd_joinbomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BOMB_GAMES:
        await update.message.reply_text("⚠️ No active Bomb Game lobby in this group.")
        return

    game = BOMB_GAMES[chat_id]
    if game["status"] != "lobby":
        await update.message.reply_text("⚠️ The Bomb Game has already started!")
        return

    user = update.effective_user
    if user.id in game["players"]:
        await update.message.reply_text("⚠️ You are already in this Bomb Game!")
        return

    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    fee = game["entry_fee"]

    if ud["balance"] < fee:
        await update.message.reply_text(f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nNeed: ${fee} | You have: ${ud['balance']}")
        return

    update_user(user.id, balance=ud["balance"] - fee)
    game["players"].append(user.id)
    game["player_names"][user.id] = user.first_name or "Player"
    game["total_pool"] += fee

    count = len(game["players"])
    await update.message.reply_text(
        f"💣 <b>{html.escape(user.first_name or 'Player')}</b> entered the Bomb Game! ({count} players)\n"
        f"Type <code>/startbomb</code> when ready!",
        parse_mode="HTML",
    )


async def cmd_startbomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BOMB_GAMES:
        return

    game = BOMB_GAMES[chat_id]
    if game["status"] != "lobby":
        return

    if len(game["players"]) < 2:
        await update.message.reply_text("⚠️ Need at least 2 players to start Bomb Game!")
        return

    game["status"] = "playing"
    game["holder"] = random.choice(game["players"])
    game["ticks_to_explode"] = random.randint(2, len(game["players"]) * 2)

    holder_name = game["player_names"][game["holder"]]
    await update.message.reply_text(
        f"💣💥 <b>BOMB GAME STARTED!</b> 💥💣\n\n"
        f"🔥 The live bomb is handed to: <a href=\"tg://user?id={game['holder']}\">{html.escape(holder_name)}</a>!\n\n"
        f"🏃‍♂️ Quick! Type <code>/pass</code> before it explodes in your hands!",
        parse_mode="HTML",
    )


async def cmd_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BOMB_GAMES or BOMB_GAMES[chat_id]["status"] != "playing":
        await update.message.reply_text("⚠️ No active Bomb Game in progress.")
        return

    game = BOMB_GAMES[chat_id]
    user = update.effective_user

    if user.id != game["holder"]:
        await update.message.reply_text("✋ You don't have the bomb! Only the bomb holder can /pass.")
        return

    game["ticks_to_explode"] -= 1

    if game["ticks_to_explode"] <= 0:
        # BOMB EXPLODES ON CURRENT HOLDER!
        exploded_id = user.id
        exploded_name = game["player_names"][exploded_id]
        game["players"].remove(exploded_id)

        if len(game["players"]) == 1:
            winner_id = game["players"][0]
            winner_name = game["player_names"][winner_id]
            prize = game["total_pool"]
            w_ud = get_user(winner_id)
            update_user(winner_id, balance=w_ud["balance"] + prize, bomb_wins=w_ud.get("bomb_wins", 0) + 1)
            add_xp(winner_id, 50)
            del BOMB_GAMES[chat_id]

            await update.message.reply_text(
                f"💥💥💥 <b>BOOOOOM!</b> 💥💥💥\n\n"
                f"💀 The bomb exploded in <b>{html.escape(exploded_name)}</b>'s hands!\n\n"
                f"🏆 <b>LAST SURVIVOR & WINNER!</b> 👑\n"
                f"🎉 <a href=\"tg://user?id={winner_id}\">{html.escape(winner_name)}</a> won the grand pot of <b>${prize}</b>! 🌸",
                parse_mode="HTML",
            )
        else:
            # Continue next round
            game["holder"] = random.choice(game["players"])
            game["ticks_to_explode"] = random.randint(2, len(game["players"]) * 2)
            next_name = game["player_names"][game["holder"]]

            await update.message.reply_text(
                f"💥💥💥 <b>BOOOOOM!</b> 💥💥💥\n\n"
                f"💀 <b>{html.escape(exploded_name)}</b> is ELIMINATED!\n\n"
                f"💣 A new live bomb is spawned and passed to: <a href=\"tg://user?id={game['holder']}\">{html.escape(next_name)}</a>!\n"
                f"Quick! Type <code>/pass</code>!",
                parse_mode="HTML",
            )
    else:
        # Pass to another random alive player
        other_players = [p for p in game["players"] if p != user.id]
        new_holder = random.choice(other_players)
        game["holder"] = new_holder
        new_name = game["player_names"][new_holder]

        await update.message.reply_text(
            f"⚡ <b>{html.escape(user.first_name)}</b> tossed the bomb to <a href=\"tg://user?id={new_holder}\">{html.escape(new_name)}</a>! 💣\n"
            f"🏃‍♂️ Quick {html.escape(new_name)}, type <code>/pass</code>!",
            parse_mode="HTML",
        )


async def cmd_bombcancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BOMB_GAMES:
        await update.message.reply_text("⚠️ No active Bomb Game to cancel.")
        return

    user = update.effective_user
    game = BOMB_GAMES[chat_id]
    is_admin = await _is_admin(chat, user.id, context)

    if not (is_admin or user.id == game["host_id"]):
        await update.message.reply_text("❌ Only group admins or the game host can cancel the game.")
        return

    # Refund all players
    fee = game["entry_fee"]
    for p_id in game["players"]:
        p_ud = get_user(p_id)
        update_user(p_id, balance=p_ud["balance"] + fee)

    del BOMB_GAMES[chat_id]
    await update.message.reply_text(
        "🛑 <b>Bomb Game Cancelled!</b>\n"
        "💵 All entry fees have been fully refunded.",
        parse_mode="HTML",
    )


async def cmd_leaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.utils.storage import get_all_users
    data = get_all_users()
    sorted_users = sorted(
        data.items(),
        key=lambda x: x[1].get("bomb_wins", 0),
        reverse=True
    )[:10]

    lines = ["💣 <b>Bᴏᴍʙ Gᴀᴍᴇ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b>\n"]
    for idx, (uid, info) in enumerate(sorted_users, 1):
        name = info.get("display_name") or info.get("first_name") or info.get("username") or "User"
        wins = info.get("bomb_wins", 0)
        lines.append(f"{idx}. {html.escape(name)} — <b>{wins} Wins</b> 💥")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


GAME_RANK_CONFIG: Dict[str, Dict[str, str]] = {
    "card": {"name": "Cᴀʀᴅ", "emoji": "🃏", "btn": "🃏 Card", "key": "card"},
    "bomb": {"name": "Bᴏᴍʙ", "emoji": "💣", "btn": "💣 Bomb", "key": "bomb"},
    "hack": {"name": "Hᴀᴄᴋ", "emoji": "💻", "btn": "💻 Hack", "key": "hack"},
    "bluff": {"name": "Bʟᴜꜰꜰ", "emoji": "🎭", "btn": "🎭 Bluff", "key": "bluff"},
    "roulette": {"name": "Rᴏᴜʟᴇᴛᴛᴇ", "emoji": "🎯", "btn": "🎯 Roulette", "key": "roulette"},
}


def render_rank_message(game_key: str, target_id: int, ud: Dict[str, Any], name: str):
    info = GAME_RANK_CONFIG.get(game_key, GAME_RANK_CONFIG["card"])
    stats = ud.get(f"{game_key}_stats") or {}

    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    won = stats.get("won", 0)
    lost = stats.get("lost", 0)
    streak = stats.get("streak", 0)
    max_streak = stats.get("max_streak", 0)
    rank = stats.get("rank", 261)

    mention = f'<a href="tg://user?id={target_id}">{html.escape(name)}</a>'
    header = f"{info['emoji']} {info['name']} Rᴀɴᴋ⠀⠀⠀⠀⠀⠀⠀"

    text = (
        f"{header}\n\n"
        f"👤 {mention}\n"
        f"👉 Wɪɴꜱ: {wins} || Lᴏꜱꜱᴇꜱ: {losses}\n"
        f"💰 Aᴍᴏᴜɴᴛ Wᴏɴ: ${won}\n"
        f"💸 Aᴍᴏᴜɴᴛ Lᴏꜱᴛ: ${lost}\n"
        f"🔥 Sᴛʀᴇᴀᴋ: {streak} / {max_streak}\n"
        f"🎖️ Rᴀɴᴋ: {rank}"
    )

    all_keys = ["bomb", "hack", "bluff", "roulette", "card"]
    other_keys = [k for k in all_keys if k != game_key]

    b1 = GAME_RANK_CONFIG[other_keys[0]]
    b2 = GAME_RANK_CONFIG[other_keys[1]]
    b3 = GAME_RANK_CONFIG[other_keys[2]]
    b4 = GAME_RANK_CONFIG[other_keys[3]]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(b1["btn"], callback_data=f"grank_{b1['key']}_{target_id}"),
            InlineKeyboardButton(b2["btn"], callback_data=f"grank_{b2['key']}_{target_id}"),
        ],
        [
            InlineKeyboardButton(b3["btn"], callback_data=f"grank_{b3['key']}_{target_id}"),
            InlineKeyboardButton(b4["btn"], callback_data=f"grank_{b4['key']}_{target_id}"),
        ]
    ])

    return text, keyboard


async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = None
    if update.message and update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = update.effective_user

    ud = get_user(target.id, target.username or target.first_name or "User", target.first_name)
    name = ud.get("display_name") or getattr(target, "full_name", None) or target.first_name or "User"

    text, keyboard = render_rank_message("card", target.id, ud, name)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
