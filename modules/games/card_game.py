import random
import html
from typing import Dict, Any, List
from telegram import Update
from telegram.ext import ContextTypes
from modules.utils.storage import get_user, update_user, add_xp

# In-memory card games: Dict[chat_id, GameState]
CARD_GAMES: Dict[int, Dict[str, Any]] = {}


def _generate_fair_hand(target_sum: int = 22) -> Dict[str, int]:
    # Generate 4 numbers between 1 and 10 that sum to target_sum
    while True:
        c1 = random.randint(1, 10)
        c2 = random.randint(1, 10)
        c3 = random.randint(1, 10)
        c4 = target_sum - (c1 + c2 + c3)
        if 1 <= c4 <= 10:
            cards = [c1, c2, c3, c4]
            random.shuffle(cards)
            return {"A": cards[0], "B": cards[1], "C": cards[2], "D": cards[3]}


async def cmd_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🃏 You can only start the Card Game in a group!")
        return

    chat_id = chat.id
    if chat_id in CARD_GAMES:
        await update.message.reply_text("⚠️ A Card Game is already active in this group!")
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "🃏 <b>ᴍɪᴋᴏ ᴄᴀʀᴅ ɢᴀᴍᴇ</b> 🃏\n\n"
            "⚠️ Uꜱᴀɢᴇ: <code>/card &lt;amount&gt; &lt;players&gt;</code>\n"
            "Example: <code>/card 500 3</code>",
            parse_mode="HTML",
        )
        return

    try:
        amount = int(float(str(args[0]).replace("$", "").replace(",", "")))
        players_count = int(args[1])
    except Exception:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/card &lt;amount&gt; &lt;players&gt;</code>", parse_mode="HTML")
        return

    if amount < 50:
        await update.message.reply_text("❌ Minimum bet amount is $50.")
        return

    if players_count < 2 or players_count > 6:
        await update.message.reply_text("❌ Players must be between 2 and 6.")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if ud["balance"] < amount:
        await update.message.reply_text(f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nNeed: ${amount} | You have: ${ud['balance']}")
        return

    update_user(user.id, balance=ud["balance"] - amount)

    CARD_GAMES[chat_id] = {
        "status": "lobby",
        "host_id": user.id,
        "entry_fee": amount,
        "max_players": players_count,
        "players": [user.id],
        "player_names": {user.id: user.first_name or "Host"},
        "hands": {},  # user_id -> {'A': 9, 'B': 4, ...}
        "used_cards": {},  # user_id -> set of labels
        "scores": {},  # user_id -> int
        "current_round": 1,
        "round_flips": {},  # user_id -> label
        "total_pool": amount,
    }

    await update.message.reply_text(
        "🃏 <b>ᴍɪᴋᴏ ᴄᴀʀᴅ ɢᴀᴍᴇ ʟᴏʙʙʏ</b> 🃏\n\n"
        f"💰 <b>Entry Bet:</b> ${amount}\n"
        f"👥 <b>Max Players:</b> {players_count}\n"
        f"👑 <b>Host:</b> {html.escape(user.first_name or 'User')}\n\n"
        f"🔹 /bet {amount} - Join the game\n"
        f"🔹 /flip &lt;a/b/c/d&gt; - Flip a card on your turn\n\n"
        f"Type <code>/bet {amount}</code> to enter!",
        parse_mode="HTML",
    )


async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in CARD_GAMES:
        await update.message.reply_text("⚠️ No active Card Game lobby in this group.")
        return

    game = CARD_GAMES[chat_id]
    if game["status"] != "lobby":
        await update.message.reply_text("⚠️ The Card Game has already started!")
        return

    user = update.effective_user
    if user.id in game["players"]:
        await update.message.reply_text("⚠️ You are already in this Card Game!")
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
        f"✅ <b>{html.escape(user.first_name or 'Player')}</b> placed a bet and joined! ({count}/{game['max_players']})",
        parse_mode="HTML",
    )

    if count >= game["max_players"]:
        # Start game
        game["status"] = "playing"
        game["current_round"] = 1
        fair_sum = random.randint(20, 26)

        for p_id in game["players"]:
            game["hands"][p_id] = _generate_fair_hand(fair_sum)
            game["used_cards"][p_id] = set()
            game["scores"][p_id] = 0

            # Send DM with their cards
            try:
                h = game["hands"][p_id]
                h_str = f"A: {h['A']} | B: {h['B']} | C: {h['C']} | D: {h['D']} (Total: {fair_sum})"
                await context.bot.send_message(
                    chat_id=p_id,
                    text=f"🃏 <b>Your Secret Cards for Miko Card Game:</b>\n{h_str}\nChoose wisely each round with /flip!",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await update.message.reply_text(
            f"🎉 <b>Lobby Full! Game Started! (Total Fair Card Sum: {fair_sum})</b>\n\n"
            f"🃏 <b>Round 1 / 4</b>\n"
            f"Every player has 4 cards (A, B, C, D) with identical sums.\n"
            f"👉 All players: choose a card to flip using: <code>/flip a</code>, <code>/flip b</code>, <code>/flip c</code>, or <code>/flip d</code>!",
            parse_mode="HTML",
        )


async def cmd_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in CARD_GAMES or CARD_GAMES[chat_id]["status"] != "playing":
        await update.message.reply_text("⚠️ No Card Game in progress right now.")
        return

    game = CARD_GAMES[chat_id]
    user = update.effective_user

    if user.id not in game["players"]:
        await update.message.reply_text("⚠️ You are not a player in this Card Game.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("⚠️ Usage: <code>/flip &lt;a/b/c/d&gt;</code>", parse_mode="HTML")
        return

    choice = str(args[0]).upper().strip()
    if choice not in ("A", "B", "C", "D"):
        await update.message.reply_text("❌ Choice must be A, B, C, or D.")
        return

    if choice in game["used_cards"][user.id]:
        await update.message.reply_text(f"⚠️ You already used card {choice} in a previous round!")
        return

    game["round_flips"][user.id] = choice
    game["used_cards"][user.id].add(choice)

    await update.message.reply_text(f"🃏 <b>{html.escape(user.first_name)}</b> flipped card <b>{choice}</b>!", parse_mode="HTML")

    # Check if all players have flipped
    if len(game["round_flips"]) >= len(game["players"]):
        # Calculate round results
        round_sum = 0
        card_values = {}
        for p_id in game["players"]:
            c_label = game["round_flips"][p_id]
            val = game["hands"][p_id][c_label]
            card_values[p_id] = val
            round_sum += val

        max_val = max(card_values.values())
        round_winners = [p_id for p_id, v in card_values.items() if v == max_val]

        for w_id in round_winners:
            game["scores"][w_id] += round_sum

        flips_summary = "\n".join([
            f"• {html.escape(game['player_names'][p])}: Card {game['round_flips'][p]} = <b>{card_values[p]}</b>"
            for p in game["players"]
        ])

        winners_text = ", ".join([html.escape(game["player_names"][w]) for w in round_winners])

        await update.message.reply_text(
            f"📊 <b>ROUND {game['current_round']} RESULTS</b>\n\n"
            f"{flips_summary}\n\n"
            f"💥 Total Round Points: <b>{round_sum}</b>\n"
            f"🏆 Round Winner(s): <b>{winners_text}</b> (+{round_sum} pts)!\n",
            parse_mode="HTML",
        )

        game["round_flips"] = {}

        if game["current_round"] < 4:
            game["current_round"] += 1
            await update.message.reply_text(
                f"🃏 <b>Round {game['current_round']} / 4</b>\n"
                f"All players: flip your next card: <code>/flip &lt;a/b/c/d&gt;</code>",
                parse_mode="HTML",
            )
        else:
            # Game finished, find overall winner
            sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
            top_score = sorted_scores[0][1]
            grand_winners = [p_id for p_id, score in sorted_scores if score == top_score]

            prize_each = game["total_pool"] // len(grand_winners)
            for gw_id in grand_winners:
                gw_ud = get_user(gw_id)
                update_user(gw_id, balance=gw_ud["balance"] + prize_each)
                add_xp(gw_id, 50)

            score_board = "\n".join([
                f"• {html.escape(game['player_names'][p])}: <b>{s} points</b>"
                for p, s in sorted_scores
            ])

            gw_names = ", ".join([html.escape(game["player_names"][gw]) for gw in grand_winners])
            del CARD_GAMES[chat_id]

            await update.message.reply_text(
                f"🏆 <b>FINAL GAME RESULTS & WINNER!</b> 👑\n\n"
                f"{score_board}\n\n"
                f"🎉 Congratulations <b>{gw_names}</b>! Won <b>${prize_each}</b>! 🌸",
                parse_mode="HTML",
            )
