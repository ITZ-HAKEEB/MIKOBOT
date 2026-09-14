from __future__ import annotations

import random
import html
import time
from typing import Dict, Any, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from modules.utils.storage import get_user, update_user, add_xp
from modules.ai.chatbot import generate_miko_sticker
from modules.management.commands import _is_admin
from modules.utils.db import get_owner_id, is_sudo_user

# In-memory active secret games: {chat_id: GameData}
SECRET_GAMES: Dict[int, Dict[str, Any]] = {}

SECRET_WORD_BANK: List[Dict[str, str]] = [
    # 🐾 Animals
    {"word": "TIGER", "cat": "🐾 Animals"},
    {"word": "LION", "cat": "🐾 Animals"},
    {"word": "GORILLA", "cat": "🐾 Animals"},
    {"word": "PANDA", "cat": "🐾 Animals"},
    {"word": "KANGAROO", "cat": "🐾 Animals"},
    {"word": "EAGLE", "cat": "🐾 Animals"},
    {"word": "SHARK", "cat": "🐾 Animals"},
    {"word": "WOLF", "cat": "🐾 Animals"},
    {"word": "OCTOPUS", "cat": "🐾 Animals"},
    {"word": "CAMEL", "cat": "🐾 Animals"},
    {"word": "HORSE", "cat": "🐾 Animals"},
    {"word": "CHAMELEON", "cat": "🐾 Animals"},
    {"word": "CROCODILE", "cat": "🐾 Animals"},
    {"word": "ZEBRA", "cat": "🐾 Animals"},

    # 🍕 Food & Drinks
    {"word": "PIZZA", "cat": "🍕 Food & Drinks"},
    {"word": "BURGER", "cat": "🍕 Food & Drinks"},
    {"word": "CHOCOLATE", "cat": "🍕 Food & Drinks"},
    {"word": "ICE CREAM", "cat": "🍕 Food & Drinks"},
    {"word": "BIRYANI", "cat": "🍕 Food & Drinks"},
    {"word": "SAMOSA", "cat": "🍕 Food & Drinks"},
    {"word": "PANCAKE", "cat": "🍕 Food & Drinks"},
    {"word": "NOODLES", "cat": "🍕 Food & Drinks"},
    {"word": "SUSHI", "cat": "🍕 Food & Drinks"},
    {"word": "COFFEE", "cat": "🍕 Food & Drinks"},
    {"word": "MANGO", "cat": "🍕 Food & Drinks"},
    {"word": "POPCORN", "cat": "🍕 Food & Drinks"},
    {"word": "SANDWICH", "cat": "🍕 Food & Drinks"},

    # 🌍 Objects & Items
    {"word": "GUITAR", "cat": "🌍 Objects & Items"},
    {"word": "CAMERA", "cat": "🌍 Objects & Items"},
    {"word": "UMBRELLA", "cat": "🌍 Objects & Items"},
    {"word": "HEADPHONES", "cat": "🌍 Objects & Items"},
    {"word": "WATCH", "cat": "🌍 Objects & Items"},
    {"word": "BICYCLE", "cat": "🌍 Objects & Items"},
    {"word": "SUNGLASSES", "cat": "🌍 Objects & Items"},
    {"word": "BACKPACK", "cat": "🌍 Objects & Items"},
    {"word": "MIRROR", "cat": "🌍 Objects & Items"},
    {"word": "BALLOON", "cat": "🌍 Objects & Items"},
    {"word": "DIAMOND", "cat": "🌍 Objects & Items"},
    {"word": "TELESCOPE", "cat": "🌍 Objects & Items"},

    # 💻 Tech & Media
    {"word": "YOUTUBE", "cat": "💻 Tech & Media"},
    {"word": "NETFLIX", "cat": "💻 Tech & Media"},
    {"word": "TELEGRAM", "cat": "💻 Tech & Media"},
    {"word": "INSTAGRAM", "cat": "💻 Tech & Media"},
    {"word": "ROBOT", "cat": "💻 Tech & Media"},
    {"word": "SATELLITE", "cat": "💻 Tech & Media"},
    {"word": "SMARTPHONE", "cat": "💻 Tech & Media"},
    {"word": "LAPTOP", "cat": "💻 Tech & Media"},
    {"word": "DRONE", "cat": "💻 Tech & Media"},
    {"word": "KEYBOARD", "cat": "💻 Tech & Media"},

    # 🎬 Movies, Games & Anime
    {"word": "AVENGERS", "cat": "🎬 Movies, Games & Anime"},
    {"word": "BATMAN", "cat": "🎬 Movies, Games & Anime"},
    {"word": "SPIDERMAN", "cat": "🎬 Movies, Games & Anime"},
    {"word": "IRON MAN", "cat": "🎬 Movies, Games & Anime"},
    {"word": "POKEMON", "cat": "🎬 Movies, Games & Anime"},
    {"word": "NARUTO", "cat": "🎬 Movies, Games & Anime"},
    {"word": "MINECRAFT", "cat": "🎬 Movies, Games & Anime"},
    {"word": "TITANIC", "cat": "🎬 Movies, Games & Anime"},
    {"word": "HARRY POTTER", "cat": "🎬 Movies, Games & Anime"},
    {"word": "DRAGON BALL", "cat": "🎬 Movies, Games & Anime"},
    {"word": "GTA", "cat": "🎬 Movies, Games & Anime"},

    # 🏛️ Places & Nature
    {"word": "PYRAMIDS", "cat": "🏛️ Places & Nature"},
    {"word": "TAJ MAHAL", "cat": "🏛️ Places & Nature"},
    {"word": "EIFFEL TOWER", "cat": "🏛️ Places & Nature"},
    {"word": "VOLCANO", "cat": "🏛️ Places & Nature"},
    {"word": "WATERFALL", "cat": "🏛️ Places & Nature"},
    {"word": "ISLAND", "cat": "🏛️ Places & Nature"},
    {"word": "DESERT", "cat": "🏛️ Places & Nature"},
    {"word": "GLACIER", "cat": "🏛️ Places & Nature"},
    {"word": "FOREST", "cat": "🏛️ Places & Nature"},
]


def _format_secret_mask(word: str) -> str:
    tokens = word.split()
    masked_tokens = []
    for token in tokens:
        masked_tokens.append(" ".join(["•"] * len(token)))
    return "   ".join(masked_tokens)


def _build_secret_game_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👁️ View Secret Word (Leader Only)", callback_data=f"sg_view:{chat_id}"),
        ],
        [
            InlineKeyboardButton("💡 View Hint", callback_data=f"sg_hint:{chat_id}"),
            InlineKeyboardButton("🔄 Change Word", callback_data=f"sg_pass:{chat_id}"),
        ],
        [
            InlineKeyboardButton("🛑 Stop Game", callback_data=f"sg_stop:{chat_id}"),
        ],
    ])


def _build_game_message_text(game: Dict[str, Any]) -> str:
    leader_name = game["leader_name"]
    leader_id = game["leader_id"]
    cat = game["cat"]
    word = game["word"]
    round_num = game.get("round", 1)
    description = game.get("description")

    leader_mention = f'<a href="tg://user?id={leader_id}">{html.escape(leader_name)}</a>'
    masked = _format_secret_mask(word)
    letter_count = len(word.replace(" ", ""))

    desc_display = (
        f"<i>\"{html.escape(description)}\"</i>"
        if description
        else "<i>(None yet! Leader: use <code>/describe &lt;clue&gt;</code> to set a hint!)</i>"
    )

    return (
        "🤫 <b>Mɪᴋᴏ Sᴇᴄʀᴇᴛ Wᴏʀᴅ Gᴀᴍᴇ</b> 🎭\n\n"
        f"👑 <b>Current Leader:</b> {leader_mention} (Round {round_num})\n"
        f"📂 <b>Category:</b> {cat}\n"
        f"🔤 <b>Word Pattern:</b> <code>{masked}</code> ({letter_count} letters)\n\n"
        f"💡 <b>Leader's Hint / Clue:</b>\n{desc_display}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 <b>How To Play:</b>\n"
        "• <b>Leader:</b> Tap <i>'View Secret Word'</i> below, then give a clue using <code>/describe &lt;clue&gt;</code>!\n"
        "• <b>Players:</b> Guess the word by <b>typing directly in chat</b>! First to guess wins the crown!\n"
        "💰 <b>Guesser Reward:</b> +$800 Coins • ⭐ +35 XP\n"
        "👑 <b>Leader Bonus:</b> +$400 Coins when solved!"
    )


async def cmd_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    chat_id = chat.id

    if chat_id in SECRET_GAMES:
        game = SECRET_GAMES[chat_id]
        await update.message.reply_text(
            _build_game_message_text(game),
            parse_mode="HTML",
            reply_markup=_build_secret_game_keyboard(chat_id),
        )
        return

    # Select random secret word
    item = random.choice(SECRET_WORD_BANK)
    word = item["word"].upper()
    cat = item["cat"]

    leader_name = user.first_name or user.username or "Leader"

    game_data = {
        "leader_id": user.id,
        "leader_name": leader_name,
        "word": word,
        "cat": cat,
        "description": None,
        "round": 1,
        "start_time": time.time(),
        "guesses": 0,
        "message_id": None,
    }
    SECRET_GAMES[chat_id] = game_data

    sent = await update.message.reply_text(
        _build_game_message_text(game_data),
        parse_mode="HTML",
        reply_markup=_build_secret_game_keyboard(chat_id),
    )
    game_data["message_id"] = sent.message_id

    # Attempt to send private DM to leader with the secret word
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "🤫 <b>Your Secret Word is:</b> <code>" + word + "</code>\n"
                f"📂 <b>Category:</b> {cat}\n\n"
                "✨ <b>Instructions:</b>\n"
                "1. Go back to the group chat.\n"
                f"2. Send <code>/describe &lt;your clue&gt;</code> (do NOT say the word itself!).\n"
                "3. Watch players guess in the group! 🌸"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def cmd_describe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not chat or not user or not msg:
        return

    chat_id = chat.id
    if chat_id not in SECRET_GAMES:
        await msg.reply_text("⚠️ No active Secret Word game in this chat! Start one with <code>/secret</code>.", parse_mode="HTML")
        return

    game = SECRET_GAMES[chat_id]
    if user.id != game["leader_id"]:
        leader_name = game["leader_name"]
        await msg.reply_text(f"⚠️ Only the current Leader (<b>{html.escape(leader_name)}</b>) can set the hint description!", parse_mode="HTML")
        return

    args = context.args or []
    if not args:
        await msg.reply_text(
            "💡 <b>Usage:</b> <code>/describe &lt;your clue&gt;</code>\n"
            "Example: <code>/describe It is yellow and loved by monkeys</code>",
            parse_mode="HTML",
        )
        return

    description = " ".join(args).strip()

    # Disallow putting the secret word in the description
    target_word = game["word"].upper()
    if target_word in description.upper():
        await msg.reply_text("🚫 <b>You cannot include the secret word itself in your description!</b> Be creative!", parse_mode="HTML")
        return

    game["description"] = description

    await msg.reply_text(
        f"✅ <b>Leader's Hint Updated!</b>\n\n"
        f"💡 <i>\"{html.escape(description)}\"</i>\n\n"
        "<i>Players: Type your guess directly in the chat!</i> 🌸",
        parse_mode="HTML",
    )

    # Also attempt to update the main game message if available
    msg_id = game.get("message_id")
    if msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=_build_game_message_text(game),
                parse_mode="HTML",
                reply_markup=_build_secret_game_keyboard(chat_id),
            )
        except Exception:
            pass


async def cmd_secret_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id
    if chat_id not in SECRET_GAMES:
        await update.message.reply_text("⚠️ No active Secret Word game! Start one with <code>/secret</code>.", parse_mode="HTML")
        return

    game = SECRET_GAMES[chat_id]
    masked = _format_secret_mask(game["word"])
    desc = game.get("description") or "(No clue provided yet by the leader!)"

    await update.message.reply_text(
        "💡 <b>Sᴇᴄʀᴇᴛ Wᴏʀᴅ Hɪɴᴛ</b>\n\n"
        f"📂 <b>Category:</b> {game['cat']}\n"
        f"🔤 <b>Pattern:</b> <code>{masked}</code> ({len(game['word'].replace(' ', ''))} letters)\n"
        f"📜 <b>Leader's Clue:</b> <i>\"{html.escape(desc)}\"</i>\n\n"
        "<i>Type your guess directly in chat!</i> ✨",
        parse_mode="HTML",
    )


async def check_secret_game_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Inspects chat messages. Returns True if this message was a winning secret word guess."""
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    if not chat or not msg or not msg.text or not user:
        return False

    chat_id = chat.id
    if chat_id not in SECRET_GAMES:
        return False

    raw = msg.text.strip()
    if raw.startswith(("/", ".", "!", "?")):
        return False

    game = SECRET_GAMES[chat_id]

    # Leader cannot guess their own secret word
    if user.id == game["leader_id"]:
        return False

    target_word = game["word"].upper().strip()
    user_guess = raw.upper().strip()

    # Exact match check
    matched = False
    if user_guess == target_word:
        matched = True
    else:
        # Check single word tokens
        tokens = [t.strip(",.!?\"'") for t in user_guess.split()]
        if len(tokens) == 1 and tokens[0] == target_word:
            matched = True
        elif " " in target_word and target_word in user_guess:
            matched = True

    if not matched:
        return False

    # Winner found!
    leader_id = game["leader_id"]
    leader_name = game["leader_name"]
    round_num = game.get("round", 1)

    winner_name = user.first_name or user.username or "Champion"
    winner_mention = f'<a href="tg://user?id={user.id}">{html.escape(winner_name)}</a>'
    old_leader_mention = f'<a href="tg://user?id={leader_id}">{html.escape(leader_name)}</a>'

    # Reward Guesser
    guesser_coins = 800
    guesser_xp = 35
    w_ud = get_user(user.id, user.username or winner_name, winner_name)
    w_wins = w_ud.get("secret_wins", 0) + 1
    w_earnings = w_ud.get("secret_earnings", 0) + guesser_coins
    update_user(user.id, balance=w_ud["balance"] + guesser_coins, secret_wins=w_wins, secret_earnings=w_earnings)
    add_xp(user.id, guesser_xp)

    # Reward Leader for a successful round
    leader_coins = 400
    leader_xp = 20
    l_ud = get_user(leader_id)
    update_user(leader_id, balance=l_ud["balance"] + leader_coins)
    add_xp(leader_id, leader_xp)

    win_text = (
        "🎉 <b>BINGO! Sᴇᴄʀᴇᴛ Wᴏʀᴅ Sᴏʟᴠᴇᴅ!</b> 🏆\n\n"
        f"👑 <b>Winner & New Leader:</b> {winner_mention}\n"
        f"✨ <b>Secret Word:</b> <code>{target_word}</code>\n"
        f"📂 <b>Category:</b> {game['cat']}\n\n"
        f"💰 <b>Guesser Reward:</b> +${guesser_coins:,} Coins • ⭐ +{guesser_xp} XP\n"
        f"🤝 <b>Leader Reward ({old_leader_mention}):</b> +${leader_coins:,} Coins • ⭐ +{leader_xp} XP\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>CROWN HANDOFF:</b> {winner_mention} is now the <b>NEW LEADER</b>!\n"
        "<i>Assigning a brand new secret word for Round {round_num + 1}...</i> 🌸"
    )

    await msg.reply_text(win_text, parse_mode="HTML")

    # Send celebration sticker
    try:
        st_buf = generate_miko_sticker(sentiment="happy", caption=f"Winner {winner_name}! 👑")
        await msg.reply_sticker(sticker=st_buf)
    except Exception:
        pass

    # Automatic Next Round with the Winner as the New Leader!
    new_item = random.choice(SECRET_WORD_BANK)
    new_word = new_item["word"].upper()
    new_cat = new_item["cat"]

    next_game = {
        "leader_id": user.id,
        "leader_name": winner_name,
        "word": new_word,
        "cat": new_cat,
        "description": None,
        "round": round_num + 1,
        "start_time": time.time(),
        "guesses": 0,
        "message_id": None,
    }
    SECRET_GAMES[chat_id] = next_game

    new_msg = await msg.reply_text(
        _build_game_message_text(next_game),
        parse_mode="HTML",
        reply_markup=_build_secret_game_keyboard(chat_id),
    )
    next_game["message_id"] = new_msg.message_id

    # DM the new leader
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "👑 <b>You are now the Secret Game Leader!</b>\n\n"
                f"🤫 <b>Your Secret Word:</b> <code>{new_word}</code>\n"
                f"📂 <b>Category:</b> {new_cat}\n\n"
                "✨ <b>Instructions:</b>\n"
                "1. Go to the group chat.\n"
                f"2. Use <code>/describe &lt;clue&gt;</code> to give hints without saying the word.\n"
                "3. Enjoy watching your friends guess! 🌸"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    return True


async def cmd_secret_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    chat_id = chat.id
    if chat_id not in SECRET_GAMES:
        await update.message.reply_text("⚠️ No active Secret Word game in this chat!", parse_mode="HTML")
        return

    game = SECRET_GAMES[chat_id]
    is_leader = user.id == game["leader_id"]
    is_adm = (
        user.id == get_owner_id()
        or is_sudo_user(user.id)
        or (await _is_admin(chat.id, user.id, context))
    )

    if not (is_leader or is_adm):
        await update.message.reply_text("⚠️ Only the Leader or a group Admin can change the secret word!", parse_mode="HTML")
        return

    old_word = game["word"]
    new_item = random.choice(SECRET_WORD_BANK)
    game["word"] = new_item["word"].upper()
    game["cat"] = new_item["cat"]
    game["description"] = None

    await update.message.reply_text(
        f"🔄 <b>Secret Word Changed!</b>\n\nThe previous word was: <code>{old_word}</code>.\n"
        "A new secret word has been assigned to the Leader!\n"
        f"Leader: tap <i>'View Secret Word'</i> and use <code>/describe &lt;clue&gt;</code>! ✨",
        parse_mode="HTML",
        reply_markup=_build_secret_game_keyboard(chat_id),
    )


async def cmd_secret_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    chat_id = chat.id
    if chat_id not in SECRET_GAMES:
        await update.message.reply_text("⚠️ No active Secret Word game to stop!", parse_mode="HTML")
        return

    game = SECRET_GAMES[chat_id]
    is_leader = user.id == game["leader_id"]
    is_adm = (
        user.id == get_owner_id()
        or is_sudo_user(user.id)
        or (await _is_admin(chat.id, user.id, context))
    )

    if not (is_leader or is_adm):
        await update.message.reply_text("⚠️ Only the Leader or an Admin can stop the Secret Game!", parse_mode="HTML")
        return

    word = game["word"]
    del SECRET_GAMES[chat_id]

    await update.message.reply_text(
        f"🛑 <b>Secret Game Ended!</b>\n\nThe secret word was: <code>{word}</code>.\n"
        "Thanks for playing! Start again anytime with <code>/secret</code>! 🌸",
        parse_mode="HTML",
    )


async def cmd_secret_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.utils.storage import get_all_users

    all_users = get_all_users()
    secret_players = []
    for uid, data in all_users.items():
        wins = data.get("secret_wins", 0)
        if wins > 0:
            secret_players.append((data.get("display_name") or data.get("username") or f"User_{uid}", wins, data.get("secret_earnings", 0)))

    secret_players.sort(key=lambda x: (x[1], x[2]), reverse=True)
    top_10 = secret_players[:10]

    if not top_10:
        await update.message.reply_text(
            "🏆 <b>Mɪᴋᴏ Sᴇᴄʀᴇᴛ Wᴏʀᴅ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b>\n\n"
            "<i>No players have won any Secret Game rounds yet! Start one with <code>/secret</code>!</i> 🌸",
            parse_mode="HTML",
        )
        return

    lines = ["🏆 <b>Mɪᴋᴏ Sᴇᴄʀᴇᴛ Wᴏʀᴅ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> 🏆\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, (name, wins, earned) in enumerate(top_10):
        badge = medals[idx] if idx < len(medals) else f"{idx+1}."
        lines.append(f"{badge} <b>{html.escape(name)}</b> — <b>{wins}</b> round wins • <code>${earned:,}</code> earned")

    lines.append("\n<i>Play with your friends using <code>/secret</code>!</i> ✨")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def secret_game_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    caller = query.from_user

    if not data.startswith("sg_"):
        return

    parts = data.split(":")
    action = parts[0]
    try:
        target_cid = int(parts[1]) if len(parts) > 1 else query.message.chat.id
    except Exception:
        target_cid = query.message.chat.id if query.message else 0

    if target_cid not in SECRET_GAMES:
        await query.answer("⚠️ This Secret Game session has already ended!", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    game = SECRET_GAMES[target_cid]
    leader_id = game["leader_id"]

    if action == "sg_view":
        if caller.id == leader_id:
            word = game["word"]
            cat = game["cat"]
            alert_text = (
                f"🤫 YOUR SECRET WORD:\n\n"
                f"👉 {word} 👈\n\n"
                f"📂 Category: {cat}\n\n"
                "Go to the chat and send:\n"
                "/describe <clue>\n"
                "(Do NOT reveal the word!)"
            )
            await query.answer(alert_text, show_alert=True)
        else:
            leader_name = game["leader_name"]
            await query.answer(f"🚫 ONLY the Leader ({leader_name}) can view the secret word!", show_alert=True)

    elif action == "sg_hint":
        desc = game.get("description")
        if desc:
            await query.answer(f"💡 Leader's Clue:\n\"{desc}\"", show_alert=True)
        else:
            await query.answer("💡 The Leader hasn't set a clue yet!\nLeader can use /describe <clue>.", show_alert=True)

    elif action == "sg_pass":
        is_leader = caller.id == leader_id
        is_adm = (
            caller.id == get_owner_id()
            or is_sudo_user(caller.id)
            or (await _is_admin(target_cid, caller.id, context))
        )
        if not (is_leader or is_adm):
            await query.answer("⚠️ Only the Leader or an Admin can change the word!", show_alert=True)
            return

        old_word = game["word"]
        new_item = random.choice(SECRET_WORD_BANK)
        game["word"] = new_item["word"].upper()
        game["cat"] = new_item["cat"]
        game["description"] = None

        await query.answer("🔄 New secret word assigned!")
        try:
            await context.bot.send_message(
                chat_id=target_cid,
                text=(
                    f"🔄 <b>Secret Word Changed!</b>\n\nThe previous word was: <code>{old_word}</code>.\n"
                    "Leader: Tap <i>'View Secret Word'</i> and use <code>/describe &lt;clue&gt;</code>! ✨"
                ),
                parse_mode="HTML",
                reply_markup=_build_secret_game_keyboard(target_cid),
            )
        except Exception:
            pass

    elif action == "sg_stop":
        is_leader = caller.id == leader_id
        is_adm = (
            caller.id == get_owner_id()
            or is_sudo_user(caller.id)
            or (await _is_admin(target_cid, caller.id, context))
        )
        if not (is_leader or is_adm):
            await query.answer("⚠️ Only the Leader or an Admin can stop the game!", show_alert=True)
            return

        word = game["word"]
        del SECRET_GAMES[target_cid]

        await query.answer("🛑 Game ended!")
        try:
            await query.edit_message_text(
                f"🛑 <b>Secret Game Ended!</b>\n\nThe word was: <code>{word}</code>.\nUse <code>/secret</code> to start again anytime! 🌸",
                parse_mode="HTML",
            )
        except Exception:
            pass
