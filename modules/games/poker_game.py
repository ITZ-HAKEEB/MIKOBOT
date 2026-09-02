import random
import html
import asyncio
import time
from typing import Dict, Any, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from modules.utils.storage import get_user, update_user, add_xp

# In-memory active poker games: Dict[chat_id, Dict[str, Any]]
POKER_GAMES: Dict[int, Dict[str, Any]] = {}

SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14,
}

SPECIALS = ["joker", "double", "shield"]


def _generate_player_cards() -> Dict[str, Dict[str, Any]]:
    """Generates 5 secret cards (A, B, C, D, E) for a player with potential special power cards."""
    cards: Dict[str, Dict[str, Any]] = {}
    labels = ["A", "B", "C", "D", "E"]
    
    # Decide if player gets 1 or 2 special cards (approx 60% chance 1 special, 25% chance 2 specials)
    special_slots = []
    r_val = random.random()
    if r_val < 0.25:
        special_slots = random.sample(labels, 2)
    elif r_val < 0.85:
        special_slots = random.sample(labels, 1)

    used_cards = set()

    for lbl in labels:
        if lbl in special_slots:
            spec_type = random.choice(SPECIALS)
            if spec_type == "joker":
                cards[lbl] = {
                    "id": lbl,
                    "suit": "🃏",
                    "rank": "Joker",
                    "value": 15,
                    "special_type": "joker",
                    "special_name": "Jᴏᴋᴇʀ",
                    "desc": "Vᴀʟᴜᴇ 15",
                    "display": "🃏 Jᴏᴋᴇʀ (Vᴀʟᴜᴇ: 15) ✨",
                    "played": False,
                }
                continue
            elif spec_type == "double":
                suit = random.choice(SUITS)
                rank, val = random.choice(list(RANKS.items()))
                cards[lbl] = {
                    "id": lbl,
                    "suit": suit,
                    "rank": rank,
                    "value": val,
                    "special_type": "double",
                    "special_name": "Dᴏᴜʙʟᴇ",
                    "desc": "2× Dᴏᴜʙʟᴇ Pᴏɪɴᴛꜱ",
                    "display": f"{suit} {rank} ⚡️ Dᴏᴜʙʟᴇ (Vᴀʟᴜᴇ: {val})",
                    "played": False,
                }
                continue
            elif spec_type == "shield":
                suit = random.choice(SUITS)
                rank, val = random.choice(list(RANKS.items()))
                cards[lbl] = {
                    "id": lbl,
                    "suit": suit,
                    "rank": rank,
                    "value": val,
                    "special_type": "shield",
                    "special_name": "Sʜɪᴇʟᴅ",
                    "desc": "Cᴀɴᴄᴇʟꜱ Tᴏᴘ Rɪᴠᴀʟ'ꜱ Cᴀʀᴅ",
                    "display": f"{suit} {rank} 🛡 Sʜɪᴇʟᴅ (Vᴀʟᴜᴇ: {val})",
                    "played": False,
                }
                continue

        # Regular card
        while True:
            suit = random.choice(SUITS)
            rank, val = random.choice(list(RANKS.items()))
            card_key = (suit, rank)
            if card_key not in used_cards:
                used_cards.add(card_key)
                break

        cards[lbl] = {
            "id": lbl,
            "suit": suit,
            "rank": rank,
            "value": val,
            "special_type": None,
            "special_name": None,
            "desc": None,
            "display": f"{suit} {rank} (Vᴀʟᴜᴇ: {val})",
            "played": False,
        }

    return cards


def _is_user_premium(user_id: int) -> bool:
    """Check if player has VIP or Premium status."""
    try:
        from modules.utils.storage import get_user
        ud = get_user(user_id, "User")
        return bool(ud.get("premium", False) or (ud.get("prem_wallet", 0) > 0))
    except Exception:
        return False


async def cmd_poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new Poker game in the group."""
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("♠️ <b>You can only start Poker Game in a group!</b>", parse_mode="HTML")
        return

    chat_id = chat.id
    if chat_id in POKER_GAMES:
        await update.message.reply_text("⚠️ <b>A Poker game is already running in this group!</b>\nUse /join to join or /pick to play.", parse_mode="HTML")
        return

    args = context.args or []
    amount = 500
    if args:
        try:
            amount = int(float(str(args[0]).replace("$", "").replace(",", "")))
        except Exception:
            amount = 500

    if amount < 50:
        await update.message.reply_text("❌ <b>Minimum bet amount for Poker is $50.</b>", parse_mode="HTML")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if ud.get("balance", 0) < amount:
        await update.message.reply_text(
            f"💸 <b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!</b>\nNeed: <code>${amount}</code> | You have: <code>${ud.get('balance', 0)}</code>",
            parse_mode="HTML",
        )
        return

    # Deduct creator bet
    update_user(user.id, balance=ud.get("balance", 0) - amount)

    game_state = {
        "chat_id": chat_id,
        "creator_id": user.id,
        "creator_name": user.first_name,
        "amount": amount,
        "state": "lobby",  # lobby, playing, ended
        "players": [user.id],
        "player_names": {user.id: user.first_name},
        "player_cards": {},
        "scores": {user.id: 0},
        "current_round": 1,
        "multiplier_round": random.randint(1, 5),
        "round_picks": {},  # user_id: card_obj
        "lobby_msg_id": None,
        "game_msg_id": None,
        "round_task": None,
        "lobby_timeout_task": None,
        "all_picked_event": asyncio.Event(),
    }
    POKER_GAMES[chat_id] = game_state

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("♠️ Jᴏɪɴ Gᴀᴍᴇ", callback_data=f"poker_join:{chat_id}"),
            InlineKeyboardButton("🚀 Sᴛᴀʀᴛ Gᴀᴍᴇ", callback_data=f"poker_start:{chat_id}"),
        ],
        [
            InlineKeyboardButton("❌ Cᴀɴᴄᴇʟ", callback_data=f"poker_cancel:{chat_id}"),
        ]
    ])

    text = (
        "♠️ <b>Pᴏᴋᴇʀ Bᴀᴛᴛʟᴇ Cʀᴇᴀᴛᴇᴅ!</b> ✨\n\n"
        f"👑 <b>Hᴏꜱᴛ:</b> {user.mention_html()}\n"
        f"💰 <b>Bᴇᴛ Aᴍᴏᴜɴᴛ:</b> <code>${amount:,}</code>\n"
        f"👥 <b>Pʟᴀʏᴇʀꜱ Jᴏɪɴᴇᴅ (1/10):</b>\n"
        f"• 1. {user.mention_html()}\n\n"
        "🃏 <i>5 rounds of strategic card battle with secret cards in DM!</i>\n"
        "⚡ <i>Join using button or type <code>/join</code>. Game starts in 60s!</i>"
    )

    msg = await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    game_state["lobby_msg_id"] = msg.message_id

    # Auto start / lobby timeout background task
    async def lobby_timer():
        await asyncio.sleep(60)
        g = POKER_GAMES.get(chat_id)
        if g and g["state"] == "lobby":
            if len(g["players"]) >= 2:
                await start_poker_game(chat_id, context)
            else:
                # Refund single player
                c_ud = get_user(g["creator_id"])
                update_user(g["creator_id"], balance=c_ud.get("balance", 0) + g["amount"])
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=g["lobby_msg_id"],
                        text="⏰ <b>Poker Game cancelled: Not enough players joined (minimum 2 needed). Bet refunded!</b>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                POKER_GAMES.pop(chat_id, None)

    game_state["lobby_timeout_task"] = asyncio.create_task(lobby_timer())


async def cmd_join_poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an active Poker game via command."""
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    game = POKER_GAMES.get(chat_id)
    if not game or game["state"] != "lobby":
        await update.message.reply_text("⚠️ No active Poker game lobby in this group to join.")
        return

    user = update.effective_user
    if user.id in game["players"]:
        await update.message.reply_text("⚠️ You have already joined this Poker game lobby.")
        return

    if len(game["players"]) >= 10:
        await update.message.reply_text("⚠️ This Poker lobby is already full (max 10 players).")
        return

    amount = game["amount"]
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if ud.get("balance", 0) < amount:
        await update.message.reply_text(
            f"💸 <b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!</b>\nNeed: <code>${amount}</code> | You have: <code>${ud.get('balance', 0)}</code>",
            parse_mode="HTML",
        )
        return

    update_user(user.id, balance=ud.get("balance", 0) - amount)
    game["players"].append(user.id)
    game["player_names"][user.id] = user.first_name
    game["scores"][user.id] = 0

    p_list = "\n".join([f"• {i+1}. {html.escape(game['player_names'][uid])}" for i, uid in enumerate(game["players"])])
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("♠️ Jᴏɪɴ Gᴀᴍᴇ", callback_data=f"poker_join:{chat_id}"),
            InlineKeyboardButton("🚀 Sᴛᴀʀᴛ Gᴀᴍᴇ", callback_data=f"poker_start:{chat_id}"),
        ],
        [
            InlineKeyboardButton("❌ Cᴀɴᴄᴇʟ", callback_data=f"poker_cancel:{chat_id}"),
        ]
    ])
    text = (
        "♠️ <b>Pᴏᴋᴇʀ Bᴀᴛᴛʟᴇ Cʀᴇᴀᴛᴇᴅ!</b> ✨\n\n"
        f"👑 <b>Hᴏꜱᴛ:</b> {html.escape(game['creator_name'])}\n"
        f"💰 <b>Bᴇᴛ Aᴍᴏᴜɴᴛ:</b> <code>${amount:,}</code>\n"
        f"👥 <b>Pʟᴀʏᴇʀꜱ Jᴏɪɴᴇᴅ ({len(game['players'])}/10):</b>\n"
        f"{p_list}\n\n"
        "🃏 <i>5 rounds of strategic card battle with secret cards in DM!</i>\n"
        "⚡ <i>Join using button or type <code>/join</code>.</i>"
    )

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["lobby_msg_id"],
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        pass


async def start_poker_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Transition from lobby to Round 1 and deal cards to players in DM."""
    game = POKER_GAMES.get(chat_id)
    if not game or game["state"] != "lobby":
        return

    if len(game["players"]) < 2:
        return

    game["state"] = "playing"
    if game.get("lobby_timeout_task"):
        game["lobby_timeout_task"].cancel()

    bot = context.bot
    bot_info = await bot.get_me()

    # Deal 5 secret cards to each player
    dm_failed_users = []
    for uid in game["players"]:
        cards = _generate_player_cards()
        game["player_cards"][uid] = cards

        # Build secret cards message
        card_lines = []
        for cid in ["A", "B", "C", "D", "E"]:
            c = cards[cid]
            spec_badge = f" 🌟 <b>[{c['special_name']}: {c['desc']}]</b>" if c["special_type"] else ""
            card_lines.append(f"• <b>Card {cid}:</b> {c['display']}{spec_badge}")

        cards_text = "\n".join(card_lines)
        dm_text = (
            "♠️ <b>ʏᴏᴜʀ 5 sᴇᴄʀᴇᴛ ᴘᴏᴋᴇʀ ᴄᴀʀᴅs:</b>\n\n"
            f"{cards_text}\n\n"
            "───────────────\n"
            "🃏 <b>Sᴘᴇᴄɪᴀʟ Pᴏᴡᴇʀꜱ:</b>\n"
            "• 🃏 <b>Joker</b> → Base Value 15\n"
            "• ⚡️ <b>Double</b> → Doubles Points in that round\n"
            "• 🛡 <b>Shield</b> → Cancels the Top Rival's card\n"
            "───────────────\n"
            "👉 <i>Play one card per round in the group with <b>/pick a/b/c/d/e</b> or use the buttons below!</i>"
        )

        dm_buttons = [
            [
                InlineKeyboardButton(f"🅰️ {cards['A']['rank']}{cards['A']['suit']}", callback_data=f"poker_pick:{chat_id}:A"),
                InlineKeyboardButton(f"🅱️ {cards['B']['rank']}{cards['B']['suit']}", callback_data=f"poker_pick:{chat_id}:B"),
                InlineKeyboardButton(f"🅲 {cards['C']['rank']}{cards['C']['suit']}", callback_data=f"poker_pick:{chat_id}:C"),
                InlineKeyboardButton(f"🅳 {cards['D']['rank']}{cards['D']['suit']}", callback_data=f"poker_pick:{chat_id}:D"),
                InlineKeyboardButton(f"🅴 {cards['E']['rank']}{cards['E']['suit']}", callback_data=f"poker_pick:{chat_id}:E"),
            ]
        ]
        dm_kb = InlineKeyboardMarkup(dm_buttons)

        try:
            await bot.send_message(
                chat_id=uid,
                text=dm_text,
                parse_mode="HTML",
                reply_markup=dm_kb,
            )
        except Exception:
            dm_failed_users.append(uid)

    if dm_failed_users:
        failed_names = ", ".join([html.escape(game["player_names"].get(u, "Player")) for u in dm_failed_users])
        kb_pm = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Start Miko In PM", url=f"https://t.me/{bot_info.username}?start=start")]
        ])
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ <b>{failed_names}</b>, please start Miko in private PM to view your secret cards!",
            parse_mode="HTML",
            reply_markup=kb_pm,
        )

    # Announce game start and enter Round 1
    total_pool = game["amount"] * len(game["players"])
    start_announcement = (
        "♠️ <b>Pᴏᴋᴇʀ Bᴀᴛᴛʟᴇ Sᴛᴀʀᴛᴇᴅ!</b> 🏆\n\n"
        f"💰 <b>Tᴏᴛᴀʟ Pʀɪᴢᴇ Pᴏᴏʟ:</b> <code>${total_pool:,}</code>\n"
        f"👥 <b>Pʟᴀʏᴇʀꜱ:</b> {len(game['players'])}\n"
        f"🔥 <b>2× Mᴜʟᴛɪᴘʟɪᴇʀ Rᴏᴜɴᴅ:</b> <i>Round {game['multiplier_round']}</i>\n\n"
        "📩 <i>Check your secret 5 cards in your private DM!</i>\n"
        "🚀 <i>Beginning Round 1 in 3 seconds...</i>"
    )
    g_msg = await bot.send_message(chat_id=chat_id, text=start_announcement, parse_mode="HTML")
    game["game_msg_id"] = g_msg.message_id

    await asyncio.sleep(3)
    await run_round(chat_id, context, 1)


async def run_round(chat_id: int, context: ContextTypes.DEFAULT_TYPE, round_num: int):
    """Executes a specific round (1 to 5) with a 60s pick timer."""
    game = POKER_GAMES.get(chat_id)
    if not game or game["state"] != "playing":
        return

    game["current_round"] = round_num
    game["round_picks"] = {}
    game["all_picked_event"] = asyncio.Event()

    bot = context.bot
    is_mult = (round_num == game["multiplier_round"])
    mult_badge = " 🔥 <b>(2× Mᴜʟᴛɪᴘʟɪᴇʀ Rᴏᴜɴᴅ!)</b>" if is_mult else ""

    p_status = "\n".join([f"• {html.escape(game['player_names'][uid])}: ⏳ <i>Picking...</i>" for uid in game["players"]])

    round_text = (
        f"♠️ <b>Pᴏᴋᴇʀ Bᴀᴛᴛʟᴇ — Rᴏᴜɴᴅ {round_num}/5</b>{mult_badge}\n\n"
        f"👥 <b>Pʟᴀʏᴇʀꜱ Sᴛᴀᴛᴜꜱ:</b>\n"
        f"{p_status}\n\n"
        "⏰ <b>Tɪᴍᴇ Rᴇᴍᴀɪɴɪɴɢ:</b> <code>60 seconds</code>\n"
        "👉 <i>Play your card using <b>/pick a/b/c/d/e</b> or tap the button in your DM!</i>"
    )

    try:
        if game.get("game_msg_id"):
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["game_msg_id"],
                text=round_text,
                parse_mode="HTML",
            )
        else:
            msg = await bot.send_message(chat_id=chat_id, text=round_text, parse_mode="HTML")
            game["game_msg_id"] = msg.message_id
    except Exception:
        msg = await bot.send_message(chat_id=chat_id, text=round_text, parse_mode="HTML")
        game["game_msg_id"] = msg.message_id

    # Wait for all players to pick or 60s timeout
    async def timer_task():
        try:
            await asyncio.wait_for(game["all_picked_event"].wait(), timeout=60.0)
        except asyncio.TimeoutError:
            pass

        # Auto-pick for any remaining player
        for uid in game["players"]:
            if uid not in game["round_picks"]:
                cards = game["player_cards"].get(uid, {})
                unplayed = [c for c in cards.values() if not c["played"]]
                if unplayed:
                    chosen = random.choice(unplayed)
                    chosen["played"] = True
                    game["round_picks"][uid] = chosen

        await evaluate_round(chat_id, context, round_num)

    game["round_task"] = asyncio.create_task(timer_task())


async def cmd_pick_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pick <a/b/c/d/e> command."""
    user = update.effective_user
    chat = update.effective_chat
    if not chat:
        return

    # If used in private chat, find active game for this user
    chat_id = chat.id
    if chat.type == "private":
        target_chat_id = None
        for cid, g in POKER_GAMES.items():
            if g["state"] == "playing" and user.id in g["players"]:
                target_chat_id = cid
                break
        if not target_chat_id:
            await update.message.reply_text("⚠️ You have no active Poker game in progress.")
            return
        chat_id = target_chat_id

    game = POKER_GAMES.get(chat_id)
    if not game or game["state"] != "playing":
        await update.message.reply_text("⚠️ No active Poker round in progress.")
        return

    if user.id not in game["players"]:
        await update.message.reply_text("⚠️ You are not part of this Poker game.")
        return

    if user.id in game["round_picks"]:
        await update.message.reply_text("✅ You have already picked your card for this round!")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("💡 <b>Usage:</b> <code>/pick a</code>, <code>/pick b</code>, <code>/pick c</code>, <code>/pick d</code>, <code>/pick e</code>", parse_mode="HTML")
        return

    card_letter = args[0].strip().upper()
    if card_letter not in ["A", "B", "C", "D", "E"]:
        await update.message.reply_text("❌ Invalid card letter! Choose from A, B, C, D, E.", parse_mode="HTML")
        return

    player_cards = game["player_cards"].get(user.id, {})
    card_obj = player_cards.get(card_letter)
    if not card_obj:
        await update.message.reply_text("❌ Card not found.")
        return

    if card_obj["played"]:
        await update.message.reply_text("⚠️ You have already played this card in a previous round! Pick another one.")
        return

    # Mark card as played
    card_obj["played"] = True
    game["round_picks"][user.id] = card_obj

    await update.message.reply_text(f"✅ <b>{user.first_name} picked Card {card_letter}!</b>", parse_mode="HTML")

    # Update group scoreboard
    await update_round_status_ui(chat_id, context)

    # Check if all picked
    if len(game["round_picks"]) >= len(game["players"]):
        game["all_picked_event"].set()


async def update_round_status_ui(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Updates the group message to show which players have picked."""
    game = POKER_GAMES.get(chat_id)
    if not game or game["state"] != "playing":
        return

    round_num = game["current_round"]
    is_mult = (round_num == game["multiplier_round"])
    mult_badge = " 🔥 <b>(2× Mᴜʟᴛɪᴘʟɪᴇʀ Rᴏᴜɴᴅ!)</b>" if is_mult else ""

    p_lines = []
    for uid in game["players"]:
        name = html.escape(game["player_names"][uid])
        if uid in game["round_picks"]:
            p_lines.append(f"• {name}: ✅ <b>Rᴇᴀᴅʏ</b>")
        else:
            p_lines.append(f"• {name}: ⏳ <i>Picking...</i>")

    p_status = "\n".join(p_lines)
    round_text = (
        f"♠️ <b>Pᴏᴋᴇʀ Bᴀᴛᴛʟᴇ — Rᴏᴜɴᴅ {round_num}/5</b>{mult_badge}\n\n"
        f"👥 <b>Pʟᴀʏᴇʀꜱ Sᴛᴀᴛᴜꜱ:</b>\n"
        f"{p_status}\n\n"
        "⏰ <b>Tɪᴍᴇ Rᴇᴍᴀɪɴɪɴɢ:</b> <code>60 seconds</code>\n"
        "👉 <i>Play your card using <b>/pick a/b/c/d/e</b> or tap the button in your DM!</i>"
    )

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["game_msg_id"],
            text=round_text,
            parse_mode="HTML",
        )
    except Exception:
        pass


async def evaluate_round(chat_id: int, context: ContextTypes.DEFAULT_TYPE, round_num: int):
    """Calculates the winner of the round, applies special powers, suit bonuses, and updates scores."""
    game = POKER_GAMES.get(chat_id)
    if not game:
        return

    bot = context.bot
    picks = game["round_picks"]
    is_mult = (round_num == game["multiplier_round"])

    # Reveal all cards
    reveals = []
    for uid in game["players"]:
        c = picks.get(uid)
        name = html.escape(game["player_names"][uid])
        if c:
            reveals.append((uid, name, c))

    # Check for 🛡 Shield power
    shield_users = [uid for uid, name, c in reveals if c.get("special_type") == "shield"]
    cancelled_users = set()

    if shield_users:
        for s_uid in shield_users:
            # Find the highest rival card among other players
            rivals = [r for r in reveals if r[0] != s_uid and r[0] not in cancelled_users]
            if rivals:
                top_rival = max(rivals, key=lambda x: x[2]["value"])
                cancelled_users.add(top_rival[0])

    # Find winning card among non-cancelled cards
    valid_reveals = [r for r in reveals if r[0] not in cancelled_users]
    if not valid_reveals:
        valid_reveals = reveals  # fallback if all cancelled

    # Find highest card
    max_val = max(r[2]["value"] for r in valid_reveals)
    tied_winners = [r for r in valid_reveals if r[2]["value"] == max_val]
    winner_uid, winner_name, winner_card = random.choice(tied_winners)

    # Base points
    base_points = winner_card["value"]

    # Suit Match Bonus (+5 points for each other player with matching suit)
    suit_bonus = 0
    winner_suit = winner_card["suit"]
    for uid, name, c in reveals:
        if uid != winner_uid and c["suit"] == winner_suit and winner_suit != "🃏":
            suit_bonus += 5

    total_round_pts = base_points + suit_bonus

    # ⚡️ Double Power
    if winner_card.get("special_type") == "double":
        total_round_pts *= 2

    # 2× Multiplier Round
    if is_mult:
        total_round_pts *= 2

    # Update score
    game["scores"][winner_uid] = game["scores"].get(winner_uid, 0) + total_round_pts

    # Format reveal card lines
    lines = []
    for uid, name, c in reveals:
        status_note = ""
        if uid in cancelled_users:
            status_note = " ❌ <i>(Cancelled by Shield)</i>"
        elif uid == winner_uid:
            status_note = f" 👑 <b>(+{total_round_pts} pts)</b>"

        card_str = f"{c['suit']} {c['rank']}"
        if c.get("special_name"):
            card_str += f" [{c['special_name']}]"
        lines.append(f"• <b>{name}:</b> {card_str}{status_note}")

    reveals_text = "\n".join(lines)

    # Scoreboard
    sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
    score_lines = [f"{i+1}. {html.escape(game['player_names'][uid])}: <b>{pts} pts</b>" for i, (uid, pts) in enumerate(sorted_scores)]
    scoreboard_text = "\n".join(score_lines)

    bonus_msg = f"\n✨ <b>Suit Match Bonus:</b> +{suit_bonus} pts" if suit_bonus > 0 else ""
    double_msg = "\n⚡️ <b>Double Power:</b> 2× Points Activated!" if winner_card.get("special_type") == "double" else ""
    mult_msg = "\n🔥 <b>2× Multiplier Round:</b> Points Doubled!" if is_mult else ""

    summary_text = (
        f"♠️ <b>Rᴏᴜɴᴅ {round_num}/5 Rᴇꜱᴜʟᴛꜱ!</b>\n\n"
        f"👑 <b>Rᴏᴜɴᴅ Wɪɴɴᴇʀ:</b> <b>{winner_name}</b>\n"
        f"🃏 <b>Wɪɴɴɪɴɢ Cᴀʀᴅ:</b> {winner_card['display']}\n"
        f"{bonus_msg}{double_msg}{mult_msg}\n\n"
        f"📋 <b>Cᴀʀᴅꜱ Pʟᴀʏᴇᴅ:</b>\n"
        f"{reveals_text}\n\n"
        f"🏆 <b>Cᴜʀʀᴇɴᴛ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ:</b>\n"
        f"{scoreboard_text}\n\n"
        f"⏳ <i>Next round starting in 4 seconds...</i>" if round_num < 5 else "🎉 <i>Calculating Final Champion...</i>"
    )

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["game_msg_id"],
            text=summary_text,
            parse_mode="HTML",
        )
    except Exception:
        await bot.send_message(chat_id=chat_id, text=summary_text, parse_mode="HTML")

    await asyncio.sleep(4)

    if round_num < 5:
        await run_round(chat_id, context, round_num + 1)
    else:
        await finish_poker_game(chat_id, context)


async def finish_poker_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Concludes the poker game, breaks ties (premium priority), applies fee, and distributes payout & XP."""
    game = POKER_GAMES.pop(chat_id, None)
    if not game:
        return

    bot = context.bot
    scores = game["scores"]
    total_pool = game["amount"] * len(game["players"])

    # Sort players by score
    sorted_players = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_score = sorted_players[0][1]
    tied_top = [uid for uid, sc in sorted_players if sc == top_score]

    winner_uid = None
    if len(tied_top) == 1:
        winner_uid = tied_top[0]
    else:
        # Tie-breaker: Check if someone is Premium
        prem_tied = [uid for uid in tied_top if _is_user_premium(uid)]
        if prem_tied:
            winner_uid = prem_tied[0]
        else:
            winner_uid = random.choice(tied_top)

    winner_name = html.escape(game["player_names"][winner_uid])
    is_prem = _is_user_premium(winner_uid)

    # Fee: 5% for premium, 10% for regular
    fee_pct = 5 if is_prem else 10
    fee_amount = int(total_pool * (fee_pct / 100))
    net_payout = total_pool - fee_amount

    # Credit winner
    w_ud = get_user(winner_uid)
    new_bal = w_ud.get("balance", 0) + net_payout
    poker_wins = w_ud.get("poker_wins", 0) + 1
    update_user(winner_uid, balance=new_bal, poker_wins=poker_wins)
    add_xp(winner_uid, 50)

    # Give participants +15 XP
    for uid in game["players"]:
        if uid != winner_uid:
            add_xp(uid, 15)

    # Build final scoreboard
    sb_lines = []
    medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, (uid, sc) in enumerate(sorted_players):
        medal = medals[idx] if idx < len(medals) else "🔹"
        name = html.escape(game["player_names"][uid])
        payout_tag = f" <b>(+${net_payout:,})</b>" if uid == winner_uid else ""
        sb_lines.append(f"{medal} {name} — <b>{sc} pts</b>{payout_tag}")

    sb_text = "\n".join(sb_lines)
    prem_tag = " 💗 <b>(Premium 5% Fee)</b>" if is_prem else " 👤 <b>(10% Fee)</b>"

    final_text = (
        "♠️ <b>Pᴏᴋᴇʀ Gᴀᴍᴇ Cᴏɴᴄʟᴜᴅᴇᴅ!</b> 🏆\n\n"
        f"👑 <b>Cʜᴀᴍᴘɪᴏɴ:</b> <b>{winner_name}</b>\n"
        f"💰 <b>Pʀɪᴢᴇ Pᴏᴏʟ:</b> <code>${net_payout:,}</code>{prem_tag}\n"
        f"⚡️ <b>XP Rᴇᴡᴀʀᴅ:</b> <code>+50 XP</code>\n"
        f"📊 <b>Wɪɴɴɪɴɢ Sᴄᴏʀᴇ:</b> <code>{top_score} Points</code>\n\n"
        f"📋 <b>Fɪɴᴀʟ Sᴄᴏʀᴇʙᴏᴀʀᴅ:</b>\n"
        f"{sb_text}\n\n"
        "✨ <i>Thank you for playing Poker! Start a new game with <b>/poker &lt;amount&gt;</b></i>"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=final_text, parse_mode="HTML")
    except Exception:
        pass


async def cmd_poker_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View top Poker players by wins."""
    from modules.utils.storage import get_all_users

    users_data = get_all_users()
    sorted_poker = sorted(
        users_data.items(),
        key=lambda x: x[1].get("poker_wins", 0),
        reverse=True,
    )

    top_10 = sorted_poker[:10]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    lines = []
    for idx, (uid, ud) in enumerate(top_10):
        wins = ud.get("poker_wins", 0)
        if wins == 0 and idx >= 3:
            continue
        medal = medals[idx] if idx < len(medals) else "🔹"
        name = html.escape(ud.get("display_name") or ud.get("username") or f"User {uid}")
        lines.append(f"{medal} <b>{name}</b> — <code>{wins} wins</code>")

    if not lines:
        lines = ["<i>No poker records yet. Be the first to win with /poker!</i>"]

    board_text = "\n".join(lines)
    text = (
        "♠️ <b>Pᴏᴋᴇʀ Gᴀᴍᴇ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> 🏆\n\n"
        f"{board_text}\n\n"
        "👉 <i>Challenge others using <b>/poker &lt;amount&gt;</b>!</i>"
    )

    await update.message.reply_text(text, parse_mode="HTML")


async def poker_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles poker inline button callbacks (join, start, cancel, pick)."""
    query = update.callback_query
    data = query.data or ""
    user = query.from_user

    if data.startswith("poker_join:"):
        chat_id = int(data.split(":")[1])
        game = POKER_GAMES.get(chat_id)
        if not game or game["state"] != "lobby":
            await query.answer("⚠️ This Poker lobby is no longer active.", show_alert=True)
            return

        if user.id in game["players"]:
            await query.answer("⚠️ You have already joined this lobby.", show_alert=True)
            return

        if len(game["players"]) >= 10:
            await query.answer("⚠️ Lobby is full (max 10 players).", show_alert=True)
            return

        amount = game["amount"]
        ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
        if ud.get("balance", 0) < amount:
            await query.answer(f"💸 Insufficient Balance! Need: ${amount}", show_alert=True)
            return

        update_user(user.id, balance=ud.get("balance", 0) - amount)
        game["players"].append(user.id)
        game["player_names"][user.id] = user.first_name
        game["scores"][user.id] = 0

        await query.answer("♠️ You joined the Poker Game!")

        # Update lobby message
        p_list = "\n".join([f"• {i+1}. {html.escape(game['player_names'][uid])}" for i, uid in enumerate(game["players"])])
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("♠️ Jᴏɪɴ Gᴀᴍᴇ", callback_data=f"poker_join:{chat_id}"),
                InlineKeyboardButton("🚀 Sᴛᴀʀᴛ Gᴀᴍᴇ", callback_data=f"poker_start:{chat_id}"),
            ],
            [
                InlineKeyboardButton("❌ Cᴀɴᴄᴇʟ", callback_data=f"poker_cancel:{chat_id}"),
            ]
        ])
        text = (
            "♠️ <b>Pᴏᴋᴇʀ Bᴀᴛᴛʟᴇ Cʀᴇᴀᴛᴇᴅ!</b> ✨\n\n"
            f"👑 <b>Hᴏꜱᴛ:</b> {html.escape(game['creator_name'])}\n"
            f"💰 <b>Bᴇᴛ Aᴍᴏᴜɴᴛ:</b> <code>${amount:,}</code>\n"
            f"👥 <b>Pʟᴀʏᴇʀꜱ Jᴏɪɴᴇᴅ ({len(game['players'])}/10):</b>\n"
            f"{p_list}\n\n"
            "🃏 <i>5 rounds of strategic card battle with secret cards in DM!</i>\n"
            "⚡ <i>Join using button or type <code>/join</code>.</i>"
        )
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass

    elif data.startswith("poker_start:"):
        chat_id = int(data.split(":")[1])
        game = POKER_GAMES.get(chat_id)
        if not game or game["state"] != "lobby":
            await query.answer("⚠️ This Poker lobby is no longer active.", show_alert=True)
            return

        if user.id != game["creator_id"]:
            await query.answer("🛡️ Only the game creator can start the game early.", show_alert=True)
            return

        if len(game["players"]) < 2:
            await query.answer("⚠️ At least 2 players are needed to start!", show_alert=True)
            return

        await query.answer("🚀 Starting Poker Game!")
        await start_poker_game(chat_id, context)

    elif data.startswith("poker_cancel:"):
        chat_id = int(data.split(":")[1])
        game = POKER_GAMES.get(chat_id)
        if not game or game["state"] != "lobby":
            await query.answer("⚠️ This Poker lobby is no longer active.", show_alert=True)
            return

        if user.id != game["creator_id"]:
            await query.answer("🛡️ Only the game creator can cancel the game.", show_alert=True)
            return

        # Refund all players
        for uid in game["players"]:
            p_ud = get_user(uid)
            update_user(uid, balance=p_ud.get("balance", 0) + game["amount"])

        if game.get("lobby_timeout_task"):
            game["lobby_timeout_task"].cancel()

        POKER_GAMES.pop(chat_id, None)
        await query.answer("❌ Game cancelled and bets refunded!")
        try:
            await query.edit_message_text("❌ <b>Poker Game has been cancelled by host. All bets refunded!</b>", parse_mode="HTML")
        except Exception:
            pass

    elif data.startswith("poker_pick:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        card_letter = parts[2].upper()

        game = POKER_GAMES.get(chat_id)
        if not game or game["state"] != "playing":
            await query.answer("⚠️ No active round in progress.", show_alert=True)
            return

        if user.id not in game["players"]:
            await query.answer("⚠️ You are not part of this game.", show_alert=True)
            return

        if user.id in game["round_picks"]:
            await query.answer("✅ You have already picked your card for this round!", show_alert=True)
            return

        player_cards = game["player_cards"].get(user.id, {})
        card_obj = player_cards.get(card_letter)
        if not card_obj:
            await query.answer("❌ Card not found.", show_alert=True)
            return

        if card_obj["played"]:
            await query.answer("⚠️ You already played this card! Choose another.", show_alert=True)
            return

        card_obj["played"] = True
        game["round_picks"][user.id] = card_obj

        await query.answer(f"✅ Picked Card {card_letter} ({card_obj['display']})!")

        # Update DM message to disable chosen button
        dm_buttons = []
        row = []
        for cid in ["A", "B", "C", "D", "E"]:
            c = player_cards[cid]
            lbl = f"✅ {cid}" if c["played"] else f"{cid} ({c['rank']}{c['suit']})"
            row.append(InlineKeyboardButton(lbl, callback_data=f"poker_pick:{chat_id}:{cid}"))
        dm_buttons.append(row)
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(dm_buttons))
        except Exception:
            pass

        # Update group UI
        await update_round_status_ui(chat_id, context)

        # Check if all picked
        if len(game["round_picks"]) >= len(game["players"]):
            game["all_picked_event"].set()
