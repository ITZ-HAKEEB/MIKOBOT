import random
import html
from typing import Dict, Any, List
from telegram import Update
from telegram.ext import ContextTypes
from modules.utils.storage import get_user, update_user, add_xp

# In-memory roulette games: Dict[chat_id, GameState]
ROULETTE_GAMES: Dict[int, Dict[str, Any]] = {}
# Mapping user_id -> active game chat_id for DM bids
USER_ROULETTE_MAP: Dict[int, int] = {}


async def cmd_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🎰 You can only start Roulette in a group chat!")
        return

    chat_id = chat.id
    if chat_id in ROULETTE_GAMES:
        await update.message.reply_text("⚠️ A Roulette game is already active in this group!")
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "🎰 <b>ᴍɪᴋᴏ ʀᴏᴜʟᴇᴛᴛᴇ ɢᴀᴍᴇ</b>\n\n"
            "⚠️ Uꜱᴀɢᴇ: <code>/roulette &lt;amount&gt; &lt;players_count&gt;</code>\n"
            "Example: <code>/roulette 1000 4</code>",
            parse_mode="HTML",
        )
        return

    try:
        amount = int(float(str(args[0]).replace("$", "").replace(",", "")))
        players_count = int(args[1])
    except Exception:
        await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/roulette &lt;amount&gt; &lt;players_count&gt;</code>", parse_mode="HTML")
        return

    if amount < 50:
        await update.message.reply_text("❌ Minimum game amount is $50.")
        return

    if players_count < 2 or players_count > 10:
        await update.message.reply_text("❌ Players count must be between 2 and 10.")
        return

    user = update.effective_user
    ud = get_user(user.id, user.username or user.first_name or "User", user.first_name)
    if ud["balance"] < amount:
        await update.message.reply_text(f"💸 ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ!\nNeed: ${amount} | You have: ${ud['balance']}")
        return

    update_user(user.id, balance=ud["balance"] - amount)

    ROULETTE_GAMES[chat_id] = {
        "status": "lobby",
        "host_id": user.id,
        "entry_fee": amount,
        "max_players": players_count,
        "players": [user.id],
        "player_names": {user.id: user.first_name or "Host"},
        "total_pool": amount,
        "current_round": 1,
        "total_rounds": players_count - 1,
        "bids": {},  # user_id -> bid_amount
    }
    USER_ROULETTE_MAP[user.id] = chat_id

    await update.message.reply_text(
        "🎰 <b>ɪɴᴛʀᴏᴅᴜᴄɪɴɢ ᴍɪᴋᴏ ʀᴏᴜʟᴇᴛᴛᴇ ɢᴀᴍᴇ</b> 🎰\n\n"
        f"💰 <b>Entry Fee:</b> ${amount}\n"
        f"👥 <b>Max Players:</b> {players_count}\n"
        f"👑 <b>Host:</b> {html.escape(user.first_name or 'User')}\n\n"
        f"🔹 /join {amount} - Join the Roulette game\n"
        f"🔹 /bid &lt;amount&gt; - Place your bid during rounds in Miko's DM or here\n\n"
        f"Type <code>/join {amount}</code> to enter!",
        parse_mode="HTML",
    )


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in ROULETTE_GAMES:
        # If no roulette game, could be bomb game or card game join
        return

    game = ROULETTE_GAMES[chat_id]
    if game["status"] != "lobby":
        await update.message.reply_text("⚠️ The Roulette game has already started!")
        return

    user = update.effective_user
    if user.id in game["players"]:
        await update.message.reply_text("⚠️ You are already in this Roulette game!")
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
    USER_ROULETTE_MAP[user.id] = chat_id

    count = len(game["players"])
    await update.message.reply_text(
        f"✅ <b>{html.escape(user.first_name or 'Player')}</b> joined Roulette! ({count}/{game['max_players']})",
        parse_mode="HTML",
    )

    # Check if full, start game
    if count >= game["max_players"]:
        game["status"] = "bidding"
        game["bids"] = {}
        await update.message.reply_text(
            f"🎉 <b>Lobby Full! Starting Round 1/{game['total_rounds']}!</b>\n\n"
            f"🎯 <b>Rule:</b> Lowest bidder in this round will be ELIMINATED!\n"
            f"💬 Send your secret bid now via: <code>/bid &lt;amount&gt;</code> (DM Miko or in group)!",
            parse_mode="HTML",
        )


async def cmd_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # Locate active roulette game
    chat_id = None
    if chat and chat.type != "private" and chat.id in ROULETTE_GAMES:
        chat_id = chat.id
    elif user.id in USER_ROULETTE_MAP:
        chat_id = USER_ROULETTE_MAP[user.id]

    if not chat_id or chat_id not in ROULETTE_GAMES:
        await update.message.reply_text("⚠️ You are not in an active Roulette bidding round.")
        return

    game = ROULETTE_GAMES[chat_id]
    if game["status"] != "bidding" or user.id not in game["players"]:
        await update.message.reply_text("⚠️ No bidding is active right now.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("⚠️ Usage: <code>/bid &lt;amount&gt;</code>", parse_mode="HTML")
        return

    try:
        bid_amt = int(float(str(args[0]).replace("$", "").replace(",", "")))
    except Exception:
        await update.message.reply_text("⚠️ Usage: <code>/bid &lt;amount&gt;</code>", parse_mode="HTML")
        return

    if bid_amt <= 0:
        await update.message.reply_text("❌ Bid amount must be greater than 0.")
        return

    game["bids"][user.id] = bid_amt
    await update.message.reply_text(f"✅ Bid of ${bid_amt} registered for Round {game['current_round']}!")

    # Check if all alive players have bid
    if len(game["bids"]) >= len(game["players"]):
        # Evaluate round
        bids = game["bids"]
        # Find lowest bid
        sorted_bids = sorted(bids.items(), key=lambda x: x[1])
        eliminated_id, lowest_val = sorted_bids[0]
        eliminated_name = game["player_names"][eliminated_id]

        game["players"].remove(eliminated_id)
        del USER_ROULETTE_MAP[eliminated_id]

        # Check if winner found
        if len(game["players"]) == 1:
            winner_id = game["players"][0]
            winner_name = game["player_names"][winner_id]
            prize = game["total_pool"]
            w_ud = get_user(winner_id)
            update_user(winner_id, balance=w_ud["balance"] + prize)
            add_xp(winner_id, 50)
            del USER_ROULETTE_MAP[winner_id]
            del ROULETTE_GAMES[chat_id]

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"💀 <b>{html.escape(eliminated_name)}</b> had the lowest bid (${lowest_val}) and was eliminated!\n\n"
                    f"🏆 <b>ROULETTE CHAMPION!</b> 👑\n\n"
                    f"🎉 <a href=\"tg://user?id={winner_id}\">{html.escape(winner_name)}</a> survived all rounds and won the grand pot of <b>${prize}</b>! 💙"
                ),
                parse_mode="HTML",
            )
        else:
            game["current_round"] += 1
            game["bids"] = {}
            survivors = ", ".join([f"{html.escape(game['player_names'][pid])}" for pid in game["players"]])

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"💀 <b>{html.escape(eliminated_name)}</b> had the lowest bid (${lowest_val}) and was ELIMINATED!\n\n"
                    f"🎯 <b>Round {game['current_round']}/{game['total_rounds']} Starts!</b>\n"
                    f"👥 Survivors: {survivors}\n"
                    f"💬 Place your bids now: <code>/bid &lt;amount&gt;</code>"
                ),
                parse_mode="HTML",
            )
