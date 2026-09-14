import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from modules.games.hack_game import cmd_hack, cmd_register, cmd_guess, cmd_end
from modules.games.bluff_game import cmd_bluff, cmd_enter, cmd_startbluff, cmd_drop, cmd_judge, cmd_mycards
from modules.games.roulette_game import cmd_roulette, cmd_join as cmd_roulette_join, cmd_bid
from modules.games.card_game import cmd_card, cmd_bet, cmd_flip
from modules.games.bomb_game import cmd_bomb, cmd_joinbomb, cmd_startbomb, cmd_pass, cmd_bombcancel, cmd_leaders, cmd_rank
from modules.games.poker_game import cmd_poker, cmd_join_poker, cmd_pick_card, cmd_poker_rank
from modules.games.word_quiz import (
    cmd_word_quiz,
    cmd_quiz_guess,
    cmd_quiz_hint,
    cmd_quiz_skip,
    cmd_quiz_stop,
    cmd_word_rank,
)
from modules.games.secret_game import (
    cmd_secret,
    cmd_describe,
    cmd_secret_hint,
    cmd_secret_pass,
    cmd_secret_stop,
    cmd_secret_rank,
)


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
        [InlineKeyboardButton("🧚 Open Miko Mini Games", url="https://t.me/i_mikoo/3")]
    ])
    await update.message.reply_text(
        "🎮 Cʟɪᴄᴋ Tʜᴇ Bᴜᴛᴛᴏɴ Bᴇʟᴏᴡ Tᴏ Kɴᴏᴡ Aʙᴏᴜᴛ Mɪᴋᴏ Mɪɴɪ Gᴀᴍᴇꜱ.",
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


# Unified join handler to support `/join` in Poker, Roulette and Bomb games
async def cmd_unified_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.games.poker_game import POKER_GAMES
    from modules.games.roulette_game import ROULETTE_GAMES
    from modules.games.bomb_game import BOMB_GAMES

    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    chat_id = chat.id
    if chat_id in POKER_GAMES:
        await cmd_join_poker(update, context)
    elif chat_id in ROULETTE_GAMES:
        await cmd_roulette_join(update, context)
    elif chat_id in BOMB_GAMES:
        await cmd_joinbomb(update, context)
    else:
        await update.message.reply_text("⚠️ No active Poker, Roulette or Bomb game lobby to join.")


# Unified guess handler to support `/guess` in Word Quiz, Secret Game, and Hack games
async def cmd_unified_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.games.word_quiz import WORD_QUIZ_GAMES
    from modules.games.secret_game import SECRET_GAMES, check_secret_game_chat_message
    from modules.games.hack_game import HACK_GAMES

    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id
    if chat_id in WORD_QUIZ_GAMES:
        await cmd_quiz_guess(update, context)
    elif chat_id in SECRET_GAMES:
        # Check guess for secret game
        await check_secret_game_chat_message(update, context)
    elif chat_id in HACK_GAMES:
        from modules.games.hack_game import cmd_guess as cmd_hack_guess
        await cmd_hack_guess(update, context)
    else:
        await update.message.reply_text("⚠️ No active Word Quiz, Secret Game, or Hack game in this chat!")


HANDLERS = {
    # Menu & Guides
    "game": game_menu,
    "economy": economy_menu,

    # Secret Word Leader Game
    "secret": cmd_secret,
    "secretword": cmd_secret,
    "secretgame": cmd_secret,
    "describe": cmd_describe,
    "clue": cmd_describe,
    "sethint": cmd_describe,
    "secrethint": cmd_secret_hint,
    "secretpass": cmd_secret_pass,
    "secretstop": cmd_secret_stop,
    "secretrank": cmd_secret_rank,

    # Word Quiz Game
    "wordquiz": cmd_word_quiz,
    "quiz": cmd_word_quiz,
    "word": cmd_word_quiz,
    "w": cmd_quiz_guess,
    "quizguess": cmd_quiz_guess,
    "quizhint": cmd_quiz_hint,
    "hint": cmd_quiz_hint,
    "quizskip": cmd_quiz_skip,
    "skip": cmd_quiz_skip,
    "quizstop": cmd_quiz_stop,
    "stopquiz": cmd_quiz_stop,
    "wordrank": cmd_word_rank,
    "quizrank": cmd_word_rank,

    # Poker Game
    "poker": cmd_poker,
    "pokerjoin": cmd_join_poker,
    "joinpoker": cmd_join_poker,
    "pick": cmd_pick_card,
    "pokerrank": cmd_poker_rank,
    "pokerlead": cmd_poker_rank,

    # Hack Game
    "hack": cmd_hack,
    "register": cmd_register,
    "guess": cmd_unified_guess,
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
