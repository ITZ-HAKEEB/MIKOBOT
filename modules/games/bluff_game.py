import random
import html
import asyncio
from typing import Dict, Any, List, Optional
from telegram import Update
from telegram.ext import ContextTypes
from modules.utils.storage import get_user, update_user, add_xp

# In-memory bluff games: Dict[chat_id, GameState]
BLUFF_GAMES: Dict[int, Dict[str, Any]] = {}


def _format_hand(hand: Dict[str, int]) -> str:
    # hand is {'A': 2, 'B': 1, 'C': 4, 'D': 2, ...}
    return " ".join([f"[{k}: {v}]" for k, v in hand.items()])


def _reindex_hand(hand_values: List[int]) -> Dict[str, int]:
    # Assign labels A, B, C, D, E, F, ...
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    res = {}
    for i, val in enumerate(hand_values):
        lbl = labels[i] if i < len(labels) else f"X{i}"
        res[lbl] = val
    return res


async def cmd_bluff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        await update.message.reply_text("🎮 You can only start Bluff game in a group!")
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("💡 Uꜱᴀɢᴇ: /bluff amount players_count/all")
        return

    try:
        amount = int(args[0])
    except ValueError:
        await update.message.reply_text("💡 Uꜱᴀɢᴇ: /bluff amount players_count/all")
        return

    if amount <= 500:
        await update.message.reply_text("⚠️ Aᴍᴏᴜɴᴛ ᴍᴜꜱᴛ ʙᴇ ɢʀᴇᴀᴛᴇʀ ᴛʜᴀɴ 500.")
        return

    p_count_str = args[1].strip().lower()
    if p_count_str == "all":
        max_players = 999
        disp_players = "Aʟʟ Pʟᴀʏᴇʀꜱ"
    else:
        try:
            max_players = int(p_count_str)
            if max_players < 2:
                await update.message.reply_text("❗️ Pʟᴀʏᴇʀꜱ ᴄᴏᴜɴᴛ ᴍᴜꜱᴛ ʙᴇ 'all' ᴏʀ ᴀ ɴᴜᴍʙᴇʀ (ᴍɪɴ 2).")
                return
            disp_players = f"Mᴀx {max_players} Pʟᴀʏᴇʀꜱ"
        except ValueError:
            await update.message.reply_text("❗️ Pʟᴀʏᴇʀꜱ ᴄᴏᴜɴᴛ ᴍᴜꜱᴛ ʙᴇ 'all' ᴏʀ ᴀ ɴᴜᴍʙᴇʀ (ᴍɪɴ 2).")
            return

    chat_id = chat.id
    if chat_id in BLUFF_GAMES:
        await update.message.reply_text("⚠️ A Bluff game is already running in this group!")
        return

    user = update.effective_user
    BLUFF_GAMES[chat_id] = {
        "status": "lobby",
        "host_id": user.id,
        "entry_fee": amount,
        "max_players": max_players,
        "players": [],
        "player_names": {},
        "hands": {},  # user_id -> {'A': 1, 'B': 2, ...}
        "turn_idx": 0,
        "current_target": 1,
        "pile": [],  # List of actual int values in pile
        "last_drop": None,  # {player_id, cards_dropped: [int], claimed_val: int, count: int}
    }

    text = (
        "🎭 <b>Bᴀᴋᴀ Bʟᴜꜰꜰ Gᴀᴍᴇ Sᴛᴀʀᴛᴇᴅ.</b>\n\n"
        f"💰 <b>Eɴᴛʀʏ Fᴇᴇ:</b> {amount}\n"
        f"👥 <b>Pʟᴀʏᴇʀꜱ:</b> {disp_players}\n"
        f"👉 Uꜱᴇ <code>/enter {amount} gems/coins</code>\n"
        "⏳ Gᴀᴍᴇ Sᴛᴀʀᴛꜱ Iɴ 2 Mɪɴᴜᴛᴇꜱ."
    )
    await update.message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(_bluff_lobby_timer(context.bot, chat_id, amount))


async def _bluff_lobby_timer(bot, chat_id: int, amount: int):
    await asyncio.sleep(60)
    if chat_id in BLUFF_GAMES and BLUFF_GAMES[chat_id].get("status") == "lobby":
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⏳ 60 ꜱᴇᴄ Lᴇꜰᴛ. Uꜱᴇ /enter {amount} ɢᴇᴍꜱ/ᴄᴏɪɴꜱ"
            )
        except Exception:
            pass

    await asyncio.sleep(30)
    if chat_id in BLUFF_GAMES and BLUFF_GAMES[chat_id].get("status") == "lobby":
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⏳ 30 ꜱᴇᴄ Lᴇꜰᴛ. Uꜱᴇ /enter {amount} ɢᴇᴍꜱ/ᴄᴏɪɴꜱ"
            )
        except Exception:
            pass

    await asyncio.sleep(30)
    if chat_id in BLUFF_GAMES and BLUFF_GAMES[chat_id].get("status") == "lobby":
        game = BLUFF_GAMES[chat_id]
        if len(game["players"]) < 2:
            for p_id in game["players"]:
                ud = get_user(p_id)
                update_user(p_id, balance=ud.get("balance", 0) + amount)
            del BLUFF_GAMES[chat_id]
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="👥 Nᴏᴛ ᴇɴᴏᴜɢʜ ᴘʟᴀʏᴇʀꜱ ᴊᴏɪɴᴇᴅ. Gᴀᴍᴇ Cᴀɴᴄᴇʟʟᴇᴅ ᴀɴᴅ ꜰᴜɴᴅꜱ ʀᴇꜰᴜɴᴅᴇᴅ."
                )
            except Exception:
                pass


async def cmd_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BLUFF_GAMES:
        await update.message.reply_text("⚠️ No active Bluff lobby. Start one with /bluff!")
        return

    game = BLUFF_GAMES[chat_id]
    if game["status"] != "lobby":
        await update.message.reply_text("⚠️ The game has already started!")
        return

    user = update.effective_user
    if user.id in game["players"]:
        await update.message.reply_text("⚠️ You have already entered the game!")
        return

    game["players"].append(user.id)
    game["player_names"][user.id] = user.first_name or "Player"

    count = len(game["players"])
    await update.message.reply_text(
        f"✅ <b>{html.escape(user.first_name or 'Player')}</b> entered the Bluff game! ({count} players)\n"
        f"Type <code>/startbluff</code> when all players have joined!",
        parse_mode="HTML",
    )


async def cmd_startbluff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BLUFF_GAMES:
        return

    game = BLUFF_GAMES[chat_id]
    if game["status"] != "lobby":
        return

    if len(game["players"]) < 2:
        await update.message.reply_text("⚠️ Need at least 2 players to start Bluff game!")
        return

    game["status"] = "playing"
    n_players = len(game["players"])

    # Create deck of 4 * n_players cards (values 1 to 4 repeated n_players times)
    deck = [val for val in [1, 2, 3, 4] for _ in range(n_players)]
    random.shuffle(deck)

    # Deal 4 cards to each player
    for i, p_id in enumerate(game["players"]):
        player_cards = deck[i * 4 : (i + 1) * 4]
        game["hands"][p_id] = _reindex_hand(player_cards)
        # Try sending DM with their cards
        try:
            hand_str = _format_hand(game["hands"][p_id])
            await context.bot.send_message(
                chat_id=p_id,
                text=f"🃏 <b>Your Bluff Hand:</b>\n{hand_str}\n(You can also use /mycards in group to check)",
                parse_mode="HTML",
            )
        except Exception:
            pass

    game["current_target"] = random.randint(1, 4)
    current_p_id = game["players"][0]
    p_name = game["player_names"][current_p_id]

    await update.message.reply_text(
        "🃏 <b>BLUFF GAME STARTED!</b>\n\n"
        "Cards have been distributed (4 cards each)!\n"
        "Use /mycards to view your hand at any time.\n\n"
        f"🎯 <b>Current Target:</b> DROP <b>{game['current_target']}</b>!\n"
        f"👉 <b>Turn:</b> <a href=\"tg://user?id={current_p_id}\">{html.escape(p_name)}</a>\n"
        f"Play your cards: <code>/drop a</code> or <code>/drop a b</code>",
        parse_mode="HTML",
    )


async def cmd_mycards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    chat_id = chat.id if chat else None

    # Check if user is in any active game in this chat
    if chat_id and chat_id in BLUFF_GAMES:
        game = BLUFF_GAMES[chat_id]
        if user.id in game["hands"]:
            hand_str = _format_hand(game["hands"][user.id])
            await update.message.reply_text(
                f"🃏 <b>Your Hand:</b> {hand_str}", parse_mode="HTML"
            )
            return

    await update.message.reply_text("ℹ️ You are not currently in an active Bluff game.")


async def cmd_drop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BLUFF_GAMES or BLUFF_GAMES[chat_id]["status"] != "playing":
        await update.message.reply_text("⚠️ No Bluff game in progress.")
        return

    game = BLUFF_GAMES[chat_id]
    current_p_id = game["players"][game["turn_idx"]]
    user = update.effective_user

    if user.id != current_p_id:
        await update.message.reply_text(f"⏳ It is not your turn! Waiting for {game['player_names'][current_p_id]}.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("⚠️ Usage: <code>/drop &lt;card_labels&gt;</code>\nExample: <code>/drop a</code> or <code>/drop a b</code>", parse_mode="HTML")
        return

    chosen_labels = [arg.upper().strip() for arg in args]
    user_hand = game["hands"][user.id]

    # Validate all labels exist in hand
    for lbl in chosen_labels:
        if lbl not in user_hand:
            await update.message.reply_text(f"❌ Card '{lbl}' is not in your hand! Use /mycards to view.")
            return

    # Extract actual card values and remove from hand
    dropped_values = []
    for lbl in chosen_labels:
        dropped_values.append(user_hand[lbl])
        del user_hand[lbl]

    # Reindex remaining hand
    game["hands"][user.id] = _reindex_hand(list(user_hand.values()))
    game["pile"].extend(dropped_values)

    target_val = game["current_target"]
    game["last_drop"] = {
        "player_id": user.id,
        "player_name": game["player_names"][user.id],
        "claimed_val": target_val,
        "count": len(dropped_values),
        "actual_values": dropped_values,
    }

    # Check if player has 0 cards left
    if len(game["hands"][user.id]) == 0:
        winner_name = game["player_names"][user.id]
        add_xp(user.id, 50)
        del BLUFF_GAMES[chat_id]
        await update.message.reply_text(
            f"👑 <b>WE HAVE A WINNER!</b> 🏆\n\n"
            f"🎉 <a href=\"tg://user?id={user.id}\">{html.escape(winner_name)}</a> dropped all their cards and won the Bluff game!",
            parse_mode="HTML",
        )
        return

    # Move to next player
    game["turn_idx"] = (game["turn_idx"] + 1) % len(game["players"])
    next_p_id = game["players"][game["turn_idx"]]
    next_p_name = game["player_names"][next_p_id]

    # Target changes for next turn (e.g. 1->2->3->4->1 or random)
    game["current_target"] = (game["current_target"] % 4) + 1

    await update.message.reply_text(
        f"🃏 <b>{html.escape(user.first_name)}</b> dropped <b>{len(dropped_values)} card(s)</b> claiming to be <b>{target_val}</b>!\n"
        f"📦 Total cards on table: <b>{len(game['pile'])}</b>\n\n"
        f"👉 <a href=\"tg://user?id={next_p_id}\">{html.escape(next_p_name)}</a>, you can either:\n"
        f"• <code>/judge</code> (call bluff on previous drop)\n"
        f"• Or drop your turn: <code>/drop &lt;cards&gt;</code> for target <b>{game['current_target']}</b>!",
        parse_mode="HTML",
    )


async def cmd_judge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id not in BLUFF_GAMES or BLUFF_GAMES[chat_id]["status"] != "playing":
        await update.message.reply_text("⚠️ No Bluff game in progress.")
        return

    game = BLUFF_GAMES[chat_id]
    current_p_id = game["players"][game["turn_idx"]]
    judge_user = update.effective_user

    if judge_user.id != current_p_id:
        await update.message.reply_text(f"⏳ Only the current player can judge!")
        return

    last = game.get("last_drop")
    if not last:
        await update.message.reply_text("⚠️ No previous drop to judge yet!")
        return

    claimed_val = last["claimed_val"]
    actual_vals = last["actual_values"]
    bluffer_id = last["player_id"]
    bluffer_name = last["player_name"]
    judge_name = game["player_names"][judge_user.id]

    # Check if previous player was bluffing (any card != claimed_val)
    is_bluffing = any(v != claimed_val for v in actual_vals)

    if is_bluffing:
        # JUDGE IS RIGHT (SUCCESS)
        # Bluffer takes all pile cards
        current_bluffer_cards = list(game["hands"][bluffer_id].values()) + game["pile"]
        game["hands"][bluffer_id] = _reindex_hand(current_bluffer_cards)

        # Judge gets 1 card removed as reward if they have cards
        judge_cards = list(game["hands"][judge_user.id].values())
        if judge_cards:
            judge_cards.pop(0)
            game["hands"][judge_user.id] = _reindex_hand(judge_cards)

        pile_count = len(game["pile"])
        game["pile"] = []
        game["last_drop"] = None

        await update.message.reply_text(
            f"⚖️ <b>JUDGE WAS RIGHT! (BLUFF CAUGHT!)</b> 🚨\n\n"
            f"🔍 <b>{html.escape(bluffer_name)}</b> bluffed! Dropped cards were: {actual_vals}\n"
            f"📥 {html.escape(bluffer_name)} takes all {pile_count} pile cards!\n"
            f"⭐ {html.escape(judge_name)} receives 1 card removal reward!\n\n"
            f"🎯 Next target: DROP <b>{game['current_target']}</b>!\n"
            f"👉 {html.escape(judge_name)}, play your turn now: <code>/drop &lt;cards&gt;</code>",
            parse_mode="HTML",
        )
    else:
        # JUDGE IS WRONG (FAILED)
        # Judge takes all pile cards
        current_judge_cards = list(game["hands"][judge_user.id].values()) + game["pile"]
        game["hands"][judge_user.id] = _reindex_hand(current_judge_cards)

        pile_count = len(game["pile"])
        game["pile"] = []
        game["last_drop"] = None

        await update.message.reply_text(
            f"⚖️ <b>JUDGE WAS WRONG! (HONEST PLAY!)</b> 😅\n\n"
            f"✅ <b>{html.escape(bluffer_name)}</b> was telling the truth! Cards were: {actual_vals}\n"
            f"📥 <b>{html.escape(judge_name)}</b> takes all {pile_count} pile cards!\n\n"
            f"🎯 Next target: DROP <b>{game['current_target']}</b>!\n"
            f"👉 {html.escape(judge_name)}, play your turn now: <code>/drop &lt;cards&gt;</code>",
            parse_mode="HTML",
        )
