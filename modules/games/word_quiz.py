from __future__ import annotations

import random
import html
import asyncio
import time
from typing import Dict, Any, List, Set, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from modules.utils.storage import get_user, update_user, add_xp
from modules.ai.chatbot import generate_miko_sticker

# In-memory active quizzes: {chat_id: GameData}
WORD_QUIZ_GAMES: Dict[int, Dict[str, Any]] = {}

# Word Database across 6 categories
WORD_BANK: List[Dict[str, Any]] = [
    # 🐾 Animals
    {"word": "ELEPHANT", "cat": "🐾 Animals", "hint": "Largest living land animal with large ears and a long trunk"},
    {"word": "GIRAFFE", "cat": "🐾 Animals", "hint": "Tallest mammal with an extremely long neck and spotted coat"},
    {"word": "PENGUIN", "cat": "🐾 Animals", "hint": "Flightless aquatic bird that thrives in icy polar regions"},
    {"word": "KANGAROO", "cat": "🐾 Animals", "hint": "Australian marsupial that hops on strong hind legs with a pouch"},
    {"word": "DOLPHIN", "cat": "🐾 Animals", "hint": "Highly intelligent marine mammal famous for clicks and acrobatics"},
    {"word": "CHEETAH", "cat": "🐾 Animals", "hint": "Fastest land animal on Earth capable of incredible sprint bursts"},
    {"word": "FLAMINGO", "cat": "🐾 Animals", "hint": "Pink wading bird known for standing on one leg"},
    {"word": "OCTOPUS", "cat": "🐾 Animals", "hint": "Eight-armed sea creature capable of camouflage and shooting ink"},
    {"word": "PLATYPUS", "cat": "🐾 Animals", "hint": "Semi-aquatic egg-laying mammal with a duck-like bill and beaver tail"},
    {"word": "HEDGEHOG", "cat": "🐾 Animals", "hint": "Spiny small mammal that curls into a prickly ball for protection"},
    {"word": "CHAMELEON", "cat": "🐾 Animals", "hint": "Lizard known for changing skin color and independently mobile eyes"},
    {"word": "BUTTERFLY", "cat": "🐾 Animals", "hint": "Beautiful insect with colorful wings that transforms from a caterpillar"},
    {"word": "CROCODILE", "cat": "🐾 Animals", "hint": "Large aquatic predatory reptile with powerful jaws"},
    {"word": "PEACOCK", "cat": "🐾 Animals", "hint": "Bird famous for displaying iridescent fan-shaped tail feathers"},
    {"word": "SQUIRREL", "cat": "🐾 Animals", "hint": "Bushy-tailed rodent that loves gathering and stashing nuts"},
    {"word": "KOALA", "cat": "🐾 Animals", "hint": "Australian tree-dwelling marsupial that eats eucalyptus leaves"},

    # 🌍 Countries & Cities
    {"word": "JAPAN", "cat": "🌍 Countries & Cities", "hint": "Land of the Rising Sun famous for cherry blossoms, anime, and sushi"},
    {"word": "BRAZIL", "cat": "🌍 Countries & Cities", "hint": "Largest South American country famous for Samba and Amazon Rainforest"},
    {"word": "AUSTRALIA", "cat": "🌍 Countries & Cities", "hint": "Island continent home to the Great Barrier Reef and Outback"},
    {"word": "GERMANY", "cat": "🌍 Countries & Cities", "hint": "European nation known for precision engineering, castles, and Autobahns"},
    {"word": "EGYPT", "cat": "🌍 Countries & Cities", "hint": "Ancient civilization famous for the Great Pyramids and the Nile River"},
    {"word": "NORWAY", "cat": "🌍 Countries & Cities", "hint": "Scandinavian nation famous for deep coastal fjords and Northern Lights"},
    {"word": "SINGAPORE", "cat": "🌍 Countries & Cities", "hint": "Futuristic island city-state famous for Gardens by the Bay"},
    {"word": "SWITZERLAND", "cat": "🌍 Countries & Cities", "hint": "Alpine nation renowned for watches, chocolate, and majestic mountains"},
    {"word": "THAILAND", "cat": "🌍 Countries & Cities", "hint": "Southeast Asian kingdom known for tropical beaches and ornate temples"},
    {"word": "PORTUGAL", "cat": "🌍 Countries & Cities", "hint": "Coastal European country famous for pastel de nata and football legends"},
    {"word": "MEXICO", "cat": "🌍 Countries & Cities", "hint": "Country known for vibrant cuisine, Mariachi music, and Mayan pyramids"},
    {"word": "ICELAND", "cat": "🌍 Countries & Cities", "hint": "Land of Fire and Ice known for glaciers, geysers, and volcanoes"},
    {"word": "CANADA", "cat": "🌍 Countries & Cities", "hint": "Second largest country by area, famous for maple syrup and Niagara Falls"},
    {"word": "PARIS", "cat": "🌍 Countries & Cities", "hint": "The City of Light and home to the iconic Eiffel Tower"},
    {"word": "TOKYO", "cat": "🌍 Countries & Cities", "hint": "Bustling capital metropolis of Japan blending neon skyscrapers and shrines"},
    {"word": "LONDON", "cat": "🌍 Countries & Cities", "hint": "Historic capital on River Thames famous for Big Ben and red double-deckers"},

    # 🍕 Food & Treats
    {"word": "PIZZA", "cat": "🍕 Food & Treats", "hint": "Italian round oven-baked flatbread topped with tomato sauce and melted cheese"},
    {"word": "CHOCOLATE", "cat": "🍕 Food & Treats", "hint": "Sweet brown confection made from roasted and ground cacao beans"},
    {"word": "SPAGHETTI", "cat": "🍕 Food & Treats", "hint": "Long, thin, cylindrical pasta usually served with Bolognese sauce"},
    {"word": "PANCAKE", "cat": "🍕 Food & Treats", "hint": "Flat thin cake fried on a griddle, traditionally stacked with maple syrup"},
    {"word": "SUSHI", "cat": "🍕 Food & Treats", "hint": "Japanese dish featuring vinegared rice rolled with seafood and nori"},
    {"word": "BIRYANI", "cat": "🍕 Food & Treats", "hint": "Fragrant Indian spiced rice layered with tender meat or vegetables"},
    {"word": "SAMOSA", "cat": "🍕 Food & Treats", "hint": "Crispy triangular fried pastry filled with spiced potatoes and peas"},
    {"word": "ICECREAM", "cat": "🍕 Food & Treats", "hint": "Frozen dairy dessert available in endless sweet flavors"},
    {"word": "CROISSANT", "cat": "🍕 Food & Treats", "hint": "Flaky, buttery French crescent-shaped viennoiserie pastry"},
    {"word": "CHEESECAKE", "cat": "🍕 Food & Treats", "hint": "Rich sweet dessert with a thick layer of cream cheese on a biscuit crust"},
    {"word": "WAFFLE", "cat": "🍕 Food & Treats", "hint": "Crisp patterned batter cake cooked between two heated textured plates"},
    {"word": "BURRITO", "cat": "🍕 Food & Treats", "hint": "Mexican flour tortilla wrapped tightly around rice, beans, and meat"},

    # 💻 Tech & Science
    {"word": "PYTHON", "cat": "💻 Tech & Science", "hint": "High-level versatile programming language named after a comedy group"},
    {"word": "ALGORITHM", "cat": "💻 Tech & Science", "hint": "Step-by-step procedure or set of rules for solving a problem"},
    {"word": "DATABASE", "cat": "💻 Tech & Science", "hint": "Organized structured collection of data stored and accessed electronically"},
    {"word": "SATELLITE", "cat": "💻 Tech & Science", "hint": "Object placed in celestial orbit to relay signals or monitor planets"},
    {"word": "ROBOTICS", "cat": "💻 Tech & Science", "hint": "Branch of engineering dealing with design and operation of automated robots"},
    {"word": "TELESCOPE", "cat": "💻 Tech & Science", "hint": "Optical instrument used to observe distant planets, stars, and galaxies"},
    {"word": "GRAVITY", "cat": "💻 Tech & Science", "hint": "Universal force of attraction that pulls objects toward one another"},
    {"word": "QUANTUM", "cat": "💻 Tech & Science", "hint": "Branch of physics studying nature at microscopic subatomic scales"},
    {"word": "ASTRONOMY", "cat": "💻 Tech & Science", "hint": "Scientific study of stars, planets, galaxies, and celestial space"},
    {"word": "CYBERSECURITY", "cat": "💻 Tech & Science", "hint": "Practice of defending digital systems, servers, and data from attacks"},
    {"word": "PROCESSOR", "cat": "💻 Tech & Science", "hint": "The brain of a computer chip executing instructions and calculations"},

    # 🎮 Gaming & Anime
    {"word": "POKEMON", "cat": "🎮 Gaming & Anime", "hint": "Pocket monsters captured in spherical balls to battle in gyms"},
    {"word": "NARUTO", "cat": "🎮 Gaming & Anime", "hint": "Blonde anime ninja who dreams of becoming the respected Hokage"},
    {"word": "MINECRAFT", "cat": "🎮 Gaming & Anime", "hint": "Sandbox voxel block world game of crafting, mining, and survival"},
    {"word": "FORTNITE", "cat": "🎮 Gaming & Anime", "hint": "Battle Royale shooter where players drop from a battle bus and build"},
    {"word": "PIKACHU", "cat": "🎮 Gaming & Anime", "hint": "Electric yellow rodent creature and most famous mascot of Pokémon"},
    {"word": "VALORANT", "cat": "🎮 Gaming & Anime", "hint": "Tactical 5v5 character-based first-person hero shooter by Riot Games"},
    {"word": "METAVERSE", "cat": "🎮 Gaming & Anime", "hint": "Hypothetical collective virtual shared space across VR and internet"},
    {"word": "PLAYSTATION", "cat": "🎮 Gaming & Anime", "hint": "Iconic home video game console brand developed by Sony"},
    {"word": "NINTENDO", "cat": "🎮 Gaming & Anime", "hint": "Legendary Japanese gaming powerhouse behind Mario, Zelda, and Switch"},

    # 🧩 Word Riddles
    {"word": "ECHO", "cat": "🧩 Word Riddles", "hint": "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?"},
    {"word": "CLOCK", "cat": "🧩 Word Riddles", "hint": "What has hands and a face, but cannot smile or clap?"},
    {"word": "COIN", "cat": "🧩 Word Riddles", "hint": "What has a head and a tail, but no body?"},
    {"word": "DARKNESS", "cat": "🧩 Word Riddles", "hint": "The more of this there is in a room, the less you can see. What is it?"},
    {"word": "STAMP", "cat": "🧩 Word Riddles", "hint": "What can travel around the entire world while staying tucked in a corner?"},
    {"word": "MAP", "cat": "🧩 Word Riddles", "hint": "I have cities but no houses, mountains but no trees, and water but no fish. What am I?"},
    {"word": "PIANO", "cat": "🧩 Word Riddles", "hint": "What has dozens of black and white keys, but cannot open a single door?"},
    {"word": "RIVER", "cat": "🧩 Word Riddles", "hint": "What runs but never walks, has a bed but never sleeps, and has a mouth but never talks?"},
    {"word": "BOTTLE", "cat": "🧩 Word Riddles", "hint": "What has a neck, but no head?"},
    {"word": "CANDLE", "cat": "🧩 Word Riddles", "hint": "I am tall when I am young, and I grow short when I am old. What am I?"},
    {"word": "TOWEL", "cat": "🧩 Word Riddles", "hint": "What gets wetter and wetter the more it dries?"},
    {"word": "SPONGE", "cat": "🧩 Word Riddles", "hint": "What is full of holes but still holds plenty of water?"},
    {"word": "MIRROR", "cat": "🧩 Word Riddles", "hint": "Look at me and I will look back; smile at me and I will smile back. What am I?"},
    {"word": "SHADOW", "cat": "🧩 Word Riddles", "hint": "I follow you in sunlight, but disappear completely in the dark. What am I?"},
    {"word": "TEAPOT", "cat": "🧩 Word Riddles", "hint": "What begins with T, finishes with T, and has T inside it?"},
]


def _scramble(word: str) -> str:
    chars = list(word)
    if len(chars) <= 2:
        return word[::-1]
    for _ in range(15):
        random.shuffle(chars)
        if "".join(chars) != word:
            break
    return " ".join(chars)


def _format_masked(word: str, revealed: Set[int]) -> str:
    out = []
    for i, ch in enumerate(word):
        if i in revealed:
            out.append(ch)
        else:
            out.append("•")
    return " ".join(out)


def _build_quiz_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💡 Reveal Hint", callback_data=f"wquiz_hint:{chat_id}"),
            InlineKeyboardButton("⏭️ Skip Word", callback_data=f"wquiz_skip:{chat_id}"),
        ],
        [
            InlineKeyboardButton("❌ Stop Quiz", callback_data=f"wquiz_stop:{chat_id}"),
        ],
    ])


async def _timeout_watcher(chat_id: int, context: ContextTypes.DEFAULT_TYPE, duration: int = 75):
    try:
        await asyncio.sleep(duration)
    except asyncio.CancelledError:
        return

    game = WORD_QUIZ_GAMES.get(chat_id)
    if not game:
        return

    # Quiz timed out
    word = game["word"]
    cat = game["cat"]
    del WORD_QUIZ_GAMES[chat_id]

    text = (
        "⏰ <b>Tɪᴍᴇ'ꜱ Uᴘ! Nᴏ Oɴᴇ Sᴏʟᴠᴇᴅ Iᴛ!</b>\n\n"
        f"📂 <b>Category:</b> {cat}\n"
        f"✨ <b>Answer:</b> <code>{word}</code>\n\n"
        "<i>Better luck next time! Type <code>/wordquiz</code> to play another round!</i> 🌸"
    )
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception:
        pass


async def cmd_word_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id

    if chat_id in WORD_QUIZ_GAMES:
        game = WORD_QUIZ_GAMES[chat_id]
        masked = _format_masked(game["word"], game["revealed"])
        await update.message.reply_text(
            "⚠️ <b>A Word Quiz is already active in this chat!</b>\n\n"
            f"📂 <b>Category:</b> {game['cat']}\n"
            f"🔤 <b>Word:</b> <code>{masked}</code> ({len(game['word'])} letters)\n"
            f"💡 <b>Hint:</b> <i>{game['hint']}</i>\n\n"
            "<i>Type your guess directly in chat or use <code>/guess &lt;word&gt;</code>!</i>",
            parse_mode="HTML",
            reply_markup=_build_quiz_keyboard(chat_id),
        )
        return

    # Select word
    item = random.choice(WORD_BANK)
    word = item["word"].upper()
    cat = item["cat"]
    hint = item["hint"]

    # Choose mode: scramble vs riddle
    is_riddle = "Riddle" in cat
    scrambled = None if is_riddle else _scramble(word)

    # Initial revealed letter (first letter if word is long)
    revealed: Set[int] = set()
    if len(word) >= 7 and not is_riddle:
        revealed.add(0)

    reward_coins = random.randint(500, 1000)
    reward_xp = random.randint(25, 45)

    masked = _format_masked(word, revealed)

    game_data = {
        "word": word,
        "cat": cat,
        "hint": hint,
        "is_riddle": is_riddle,
        "scrambled": scrambled,
        "revealed": revealed,
        "reward_coins": reward_coins,
        "reward_xp": reward_xp,
        "start_time": time.time(),
        "guesses": 0,
        "timeout_task": None,
    }

    # Start 75s timeout watcher
    game_data["timeout_task"] = asyncio.create_task(_timeout_watcher(chat_id, context, duration=75))
    WORD_QUIZ_GAMES[chat_id] = game_data

    if is_riddle:
        msg_text = (
            "🧠 <b>Mɪᴋᴏ Wᴏʀᴅ Qᴜɪᴢ — Rɪᴅᴅʟᴇ Mᴏᴅᴇ!</b> 🧩\n\n"
            f"📂 <b>Category:</b> {cat}\n\n"
            f"📜 <b>Riddle Clue:</b>\n<i>\"{hint}\"</i>\n\n"
            f"🔤 <b>Word Pattern:</b> <code>{masked}</code> ({len(word)} letters)\n"
            f"💰 <b>Reward:</b> +${reward_coins:,} Coins • ⭐ +{reward_xp} XP\n\n"
            "👉 <i>Type the answer directly in chat to win!</i>"
        )
    else:
        msg_text = (
            "🔤 <b>Mɪᴋᴏ Wᴏʀᴅ Qᴜɪᴢ — Sᴄʀᴀᴍʙʟᴇ Mᴏᴅᴇ!</b> 🌟\n\n"
            f"📂 <b>Category:</b> {cat}\n"
            f"🌪️ <b>Scrambled Letters:</b> [ <code>{scrambled}</code> ]\n\n"
            f"🔤 <b>Word Pattern:</b> <code>{masked}</code> ({len(word)} letters)\n"
            f"💡 <b>Hint:</b> <i>{hint}</i>\n"
            f"💰 <b>Reward:</b> +${reward_coins:,} Coins • ⭐ +{reward_xp} XP\n\n"
            "👉 <i>Type the unscrambled word directly in chat to win!</i>"
        )

    await update.message.reply_text(
        msg_text,
        parse_mode="HTML",
        reply_markup=_build_quiz_keyboard(chat_id),
    )


async def _handle_quiz_win(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user,
    word: str,
    game: Dict[str, Any],
):
    # Cancel timeout task
    if game.get("timeout_task"):
        game["timeout_task"].cancel()

    del WORD_QUIZ_GAMES[chat_id]

    time_taken = max(1, int(time.time() - game["start_time"]))
    reward_coins = game["reward_coins"]
    reward_xp = game["reward_xp"]

    username = user.username or user.first_name or "Player"
    display_name = user.first_name or username
    ud = get_user(user.id, username, display_name)

    # Award coins & XP
    new_balance = ud["balance"] + reward_coins
    new_wins = ud.get("quiz_wins", 0) + 1
    new_earnings = ud.get("quiz_earnings", 0) + reward_coins

    update_user(
        user.id,
        balance=new_balance,
        quiz_wins=new_wins,
        quiz_earnings=new_earnings,
    )
    add_xp(user.id, reward_xp)

    user_mention = f'<a href="tg://user?id={user.id}">{html.escape(display_name)}</a>'

    win_text = (
        "🎉 <b>BINGO! Wᴇ Hᴀᴠᴇ A Wɪɴɴᴇʀ!</b> 🎉\n\n"
        f"👑 <b>Champion:</b> {user_mention}\n"
        f"✨ <b>Correct Word:</b> <code>{word}</code>\n"
        f"📂 <b>Category:</b> {game['cat']}\n"
        f"⏱️ <b>Time Taken:</b> {time_taken} seconds\n\n"
        f"💰 <b>Prize Earned:</b> +${reward_coins:,} Coins!\n"
        f"⭐ <b>Experience:</b> +{reward_xp} XP\n"
        f"🏆 <b>Total Quiz Wins:</b> {new_wins}\n\n"
        "<i>Want another challenge? Type <code>/wordquiz</code>!</i> 🌸"
    )

    await update.effective_message.reply_text(win_text, parse_mode="HTML")

    # Send cute victory sticker
    try:
        st_buf = generate_miko_sticker(sentiment="happy", caption=f"Winner {display_name}! 🌟")
        await update.effective_message.reply_sticker(sticker=st_buf)
    except Exception:
        pass


async def check_word_quiz_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Inspects non-command chat messages. Returns True if this message was a winning quiz answer."""
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    if not chat or not msg or not msg.text or not user:
        return False

    chat_id = chat.id
    if chat_id not in WORD_QUIZ_GAMES:
        return False

    raw_text = msg.text.strip()
    if raw_text.startswith(("/", ".", "!", "?")):
        return False

    game = WORD_QUIZ_GAMES[chat_id]
    target_word = game["word"].upper()

    # Normalize guess: clean punctuation and extra spaces
    guess = raw_text.upper().strip()
    tokens = [t.strip(",.!?\"'") for t in guess.split()]

    # Match exact single word or if the message equals target_word
    matched = False
    if guess == target_word:
        matched = True
    elif len(tokens) == 1 and tokens[0] == target_word:
        matched = True

    if matched:
        await _handle_quiz_win(update, context, chat_id, user, target_word, game)
        return True

    return False


async def cmd_quiz_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    chat_id = chat.id
    if chat_id not in WORD_QUIZ_GAMES:
        await update.message.reply_text("⚠️ No active Word Quiz in this chat! Start one with <code>/wordquiz</code>.", parse_mode="HTML")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("💡 <b>Usage:</b> <code>/w &lt;word&gt;</code> or just type your answer directly!", parse_mode="HTML")
        return

    guess = "".join(args).upper().strip()
    game = WORD_QUIZ_GAMES[chat_id]
    target = game["word"]

    if guess == target:
        await _handle_quiz_win(update, context, chat_id, user, target, game)
    else:
        game["guesses"] += 1
        await update.message.reply_text(f"❌ <i>\"{guess}\"</i> is not correct! Keep trying! ✨", parse_mode="HTML")


async def cmd_quiz_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id
    if chat_id not in WORD_QUIZ_GAMES:
        await update.message.reply_text("⚠️ No active Word Quiz in this chat! Start one with <code>/wordquiz</code>.", parse_mode="HTML")
        return

    game = WORD_QUIZ_GAMES[chat_id]
    word = game["word"]
    revealed = game["revealed"]

    unrevealed = [i for i in range(len(word)) if i not in revealed]
    if len(unrevealed) <= 1:
        await update.message.reply_text("💡 All available hints have already been revealed!", parse_mode="HTML")
        return

    new_idx = random.choice(unrevealed)
    revealed.add(new_idx)
    masked = _format_masked(word, revealed)

    # Slight penalty to reward for using hint
    game["reward_coins"] = max(200, game["reward_coins"] - 100)

    await update.message.reply_text(
        "💡 <b>Lᴇᴛᴛᴇʀ Hɪɴᴛ Rᴇᴠᴇᴀʟᴇᴅ!</b>\n\n"
        f"🔤 <b>Updated Pattern:</b> <code>{masked}</code>\n"
        f"💰 <b>Reward Pool:</b> ${game['reward_coins']:,} Coins\n"
        f"<i>Guess the word now!</i> ✨",
        parse_mode="HTML",
        reply_markup=_build_quiz_keyboard(chat_id),
    )


async def cmd_quiz_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id
    if chat_id not in WORD_QUIZ_GAMES:
        await update.message.reply_text("⚠️ No active Word Quiz to skip!", parse_mode="HTML")
        return

    game = WORD_QUIZ_GAMES[chat_id]
    if game.get("timeout_task"):
        game["timeout_task"].cancel()

    word = game["word"]
    cat = game["cat"]
    del WORD_QUIZ_GAMES[chat_id]

    await update.message.reply_text(
        "⏭️ <b>Qᴜɪᴢ Wᴏʀᴅ Sᴋɪᴘᴘᴇᴅ!</b>\n\n"
        f"📂 <b>Category:</b> {cat}\n"
        f"✨ <b>The Answer was:</b> <code>{word}</code>\n\n"
        "<i>Starting a new round with <code>/wordquiz</code>!</i> 🌸",
        parse_mode="HTML",
    )


async def cmd_quiz_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id
    if chat_id not in WORD_QUIZ_GAMES:
        await update.message.reply_text("⚠️ No active Word Quiz to stop!", parse_mode="HTML")
        return

    game = WORD_QUIZ_GAMES[chat_id]
    if game.get("timeout_task"):
        game["timeout_task"].cancel()

    word = game["word"]
    del WORD_QUIZ_GAMES[chat_id]

    await update.message.reply_text(
        f"🛑 <b>Word Quiz Stopped!</b>\nThe word was: <code>{word}</code>.\nUse <code>/wordquiz</code> whenever you want to play again! 🌸",
        parse_mode="HTML",
    )


async def cmd_word_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from modules.utils.storage import get_all_users

    all_users = get_all_users()
    quiz_players = []
    for uid, data in all_users.items():
        wins = data.get("quiz_wins", 0)
        if wins > 0:
            quiz_players.append((data.get("display_name") or data.get("username") or f"User_{uid}", wins, data.get("quiz_earnings", 0)))

    quiz_players.sort(key=lambda x: (x[1], x[2]), reverse=True)
    top_10 = quiz_players[:10]

    if not top_10:
        await update.message.reply_text(
            "🏆 <b>Mɪᴋᴏ Wᴏʀᴅ Qᴜɪᴢ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b>\n\n"
            "<i>No players have solved word quizzes yet! Be the first by typing <code>/wordquiz</code>!</i> 🌸",
            parse_mode="HTML",
        )
        return

    lines = ["🏆 <b>Mɪᴋᴏ Wᴏʀᴅ Qᴜɪᴢ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> 🏆\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, (name, wins, earned) in enumerate(top_10):
        badge = medals[idx] if idx < len(medals) else f"{idx+1}."
        lines.append(f"{badge} <b>{html.escape(name)}</b> — <b>{wins}</b> wins • <code>${earned:,}</code> won")

    lines.append("\n<i>Play daily with <code>/wordquiz</code> to climb the ranks!</i> ✨")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def word_quiz_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if not data.startswith("wquiz_"):
        return

    parts = data.split(":")
    action = parts[0]
    try:
        target_cid = int(parts[1]) if len(parts) > 1 else query.message.chat.id
    except Exception:
        target_cid = query.message.chat.id if query.message else 0

    if target_cid not in WORD_QUIZ_GAMES:
        await query.answer("⚠️ This Word Quiz has already ended or expired!", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    game = WORD_QUIZ_GAMES[target_cid]

    if action == "wquiz_hint":
        word = game["word"]
        revealed = game["revealed"]
        unrevealed = [i for i in range(len(word)) if i not in revealed]
        if len(unrevealed) <= 1:
            await query.answer("💡 No more letters can be revealed!", show_alert=True)
            return

        new_idx = random.choice(unrevealed)
        revealed.add(new_idx)
        game["reward_coins"] = max(200, game["reward_coins"] - 100)
        masked = _format_masked(word, revealed)

        await query.answer("💡 A letter was revealed!")
        try:
            # Update message text with new pattern
            if game["is_riddle"]:
                new_text = (
                    "🧠 <b>Mɪᴋᴏ Wᴏʀᴅ Qᴜɪᴢ — Rɪᴅᴅʟᴇ Mᴏᴅᴇ!</b> 🧩\n\n"
                    f"📂 <b>Category:</b> {game['cat']}\n\n"
                    f"📜 <b>Riddle Clue:</b>\n<i>\"{game['hint']}\"</i>\n\n"
                    f"🔤 <b>Word Pattern:</b> <code>{masked}</code> ({len(word)} letters)\n"
                    f"💰 <b>Reward:</b> +${game['reward_coins']:,} Coins • ⭐ +{game['reward_xp']} XP\n\n"
                    "👉 <i>Type the answer directly in chat to win!</i>"
                )
            else:
                new_text = (
                    "🔤 <b>Mɪᴋᴏ Wᴏʀᴅ Qᴜɪᴢ — Sᴄʀᴀᴍʙʟᴇ Mᴏᴅᴇ!</b> 🌟\n\n"
                    f"📂 <b>Category:</b> {game['cat']}\n"
                    f"🌪️ <b>Scrambled Letters:</b> [ <code>{game['scrambled']}</code> ]\n\n"
                    f"🔤 <b>Word Pattern:</b> <code>{masked}</code> ({len(word)} letters)\n"
                    f"💡 <b>Hint:</b> <i>{game['hint']}</i>\n"
                    f"💰 <b>Reward:</b> +${game['reward_coins']:,} Coins • ⭐ +{game['reward_xp']} XP\n\n"
                    "👉 <i>Type the unscrambled word directly in chat to win!</i>"
                )
            await query.edit_message_text(
                new_text,
                parse_mode="HTML",
                reply_markup=_build_quiz_keyboard(target_cid),
            )
        except Exception:
            pass

    elif action == "wquiz_skip":
        if game.get("timeout_task"):
            game["timeout_task"].cancel()
        word = game["word"]
        cat = game["cat"]
        del WORD_QUIZ_GAMES[target_cid]

        await query.answer("⏭️ Word skipped!")
        try:
            await query.edit_message_text(
                "⏭️ <b>Qᴜɪᴢ Wᴏʀᴅ Sᴋɪᴘᴘᴇᴅ!</b>\n\n"
                f"📂 <b>Category:</b> {cat}\n"
                f"✨ <b>The Answer was:</b> <code>{word}</code>\n\n"
                "<i>Use <code>/wordquiz</code> to start a new word!</i> 🌸",
                parse_mode="HTML",
            )
        except Exception:
            pass

    elif action == "wquiz_stop":
        if game.get("timeout_task"):
            game["timeout_task"].cancel()
        word = game["word"]
        del WORD_QUIZ_GAMES[target_cid]

        await query.answer("🛑 Quiz ended.")
        try:
            await query.edit_message_text(
                f"🛑 <b>Word Quiz Ended!</b>\nThe word was: <code>{word}</code>.\nUse <code>/wordquiz</code> to play again anytime! 🌸",
                parse_mode="HTML",
            )
        except Exception:
            pass
