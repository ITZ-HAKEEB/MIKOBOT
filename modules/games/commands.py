import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from modules.games.hack_game import cmd_hack, cmd_register, cmd_guess, cmd_end
from modules.games.bluff_game import cmd_bluff, cmd_enter, cmd_startbluff, cmd_drop, cmd_judge, cmd_mycards
from modules.games.roulette_game import cmd_roulette, cmd_join as cmd_roulette_join, cmd_bid
from modules.games.card_game import cmd_card, cmd_bet, cmd_flip
from modules.games.bomb_game import cmd_bomb, cmd_joinbomb, cmd_startbomb, cmd_pass, cmd_bombcancel, cmd_leaders, cmd_rank


async def ludo(update, context):
    await update.message.reply_text("🎲 <b>Ludo Game</b> — Coming soon in the next update!", parse_mode="HTML")


TRUTHS = [
    "What is your biggest fear?",
    "What is the most embarrassing thing that happened to you?",
    "Tell one secret you kept from your parents.",
    "What is your most awkward romantic moment?",
    "If you could change one thing about yourself, what?",
]
DARES = [
    "Do your best impression of the last person who texted you.",
    "Sing a 10-second jingle about the group.",
    "Post an unfiltered selfie to the group.",
    "Let someone in the group edit your Telegram name for 1 hour.",
    "Say 5 nice things about the person to your right (or next message).",
]
PUZZLES = [
    ("Subah uthta h par kabhi sota nahi. Kaun?", "Sooraj (Sun)"),
    ("Ek aisi cheez jo subah 4 taang par, dopahar 2 taang par aur shaam ko 3 taang par chalti hai?", "Insaan (Human)"),
    ("Aisi kaun si cheez hai jo paani peete hi mar jaati hai?", "Pyaas ya Aag (Thirst / Fire)"),
    ("Aisi kaun si cheez hai jise hum khate bhi hain aur peete bhi hain aur jalate bhi hain?", "Nariyal (Coconut)"),
    ("Katori pe katora, beta baap se bhi gora. Kaun?", "Nariyal (Coconut)"),
    ("Chhoti si chhori, laal gulabi gori, pahan ke nikli chunri mori. Kaun?", "Laal Mirch (Red Chilli)"),
    ("I speak without a mouth and hear without ears. What am I?", "Echo"),
    ("I have keys but no locks. I have space but no room. You can enter, but you can’t go outside. What am I?", "Keyboard"),
    ("The more you take, the more you leave behind. What am I?", "Footsteps"),
    ("What has to be broken before you can use it?", "An Egg"),
    ("I’m tall when I’m young, and I’m short when I’m old. What am I?", "A Candle"),
    ("What comes once in a minute, twice in a moment, but never in a thousand years?", "The letter M"),
]


async def truth(update, context):
    await update.message.reply_text(f"🎯 <b>ᴛʀᴜᴛʜ</b>\n{random.choice(TRUTHS)}", parse_mode="HTML")


async def dare(update, context):
    await update.message.reply_text(f"🔥 <b>ᴅᴀʀᴇ</b>\n{random.choice(DARES)}", parse_mode="HTML")


async def puzzle(update, context):
    q, a = random.choice(PUZZLES)
    text = (
        "🧠 <b>Puzzle:</b>\n\n"
        f"{q}\n\n"
        f"<tg-spoiler>{a}</tg-spoiler>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def game_menu(update, context):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧚 Open Baka Mini Games", url="https://t.me/i_mikoo/3")]
    ])
    await update.message.reply_text(
        "🎮 Cʟɪᴄᴋ Tʜᴇ Bᴜᴛᴛᴏɴ Bᴇʟᴏᴡ Tᴏ Kɴᴏᴡ Aʙᴏᴜᴛ Bᴀᴋᴀ Mɪɴɪ Gᴀᴍᴇꜱ.",
        reply_markup=kb,
    )


async def economy_menu(update, context):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧚 Oᴘᴇɴ Eᴄᴏɴᴏᴍʏ Gᴜɪᴅᴇ", url="https://t.me/i_mikoo/2")]
    ])
    await update.message.reply_text(
        "🎮 Cʟɪᴄᴋ Tʜᴇ Bᴜᴛᴛᴏɴ Bᴇʟᴏᴡ Tᴏ Kɴᴏᴡ Aʙᴏᴜᴛ Mɪᴋᴏ Eᴄᴏɴᴏᴍʏ Gᴀᴍᴇ.",
        reply_markup=kb,
    )


# Unified join handler to support `/join` in Roulette and Bomb games
async def cmd_unified_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.games.roulette_game import ROULETTE_GAMES
    from modules.games.bomb_game import BOMB_GAMES

    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id in ROULETTE_GAMES:
        await cmd_roulette_join(update, context)
    elif chat_id in BOMB_GAMES:
        await cmd_joinbomb(update, context)
    else:
        await update.message.reply_text("⚠️ No active Roulette or Bomb game lobby to join.")


HANDLERS = {
    # Menu & Guides
    "game": game_menu,
    "economy": economy_menu,

    # Hack Game
    "hack": cmd_hack,
    "register": cmd_register,
    "guess": cmd_guess,
    "end": cmd_end,

    # Bluff Game
    "bluff": cmd_bluff,
    "enter": cmd_enter,
    "startbluff": cmd_startbluff,
    "drop": cmd_drop,
    "judge": cmd_judge,
    "mycards": cmd_mycards,

    # Roulette Game
    "roulette": cmd_roulette,
    "bid": cmd_bid,

    # Card Game
    "card": cmd_card,
    "bet": cmd_bet,
    "flip": cmd_flip,

    # Bomb Game
    "bomb": cmd_bomb,
    "joinbomb": cmd_joinbomb,
    "startbomb": cmd_startbomb,
    "pass": cmd_pass,
    "bombcancel": cmd_bombcancel,
    "leaders": cmd_leaders,
    "rank": cmd_rank,

    # Unified Join
    "join": cmd_unified_join,

    # Fun Minis
    "ludo": ludo,
    "truth": truth,
    "dare": dare,
    "puzzle": puzzle,
}
