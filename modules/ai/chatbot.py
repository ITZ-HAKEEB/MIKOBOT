from __future__ import annotations

import os
import io
import re
import json
import random
import asyncio
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

from telegram import Update
from telegram.ext import ContextTypes
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

from modules.utils.storage import get_group, update_group
from modules.management.commands import _is_admin
from modules.utils.db import is_sudo_user, get_owner_id

load_dotenv()

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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",
)

FREE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "liquid/lfm-2.5-2.6b:free",
    "thinkingmachines/inkling:free",
    "nex-agi/nex-n2.5-pro:free",
    "poolside/laguna-s-2.1:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# In-memory context cache: {chat_id: [{"role": "user"|"assistant", "content": "..."}]}
_chat_histories: Dict[int, List[Dict[str, str]]] = {}

STICKER_SENTIMENTS: Dict[str, Dict[str, Any]] = {
    "love": {
        "items": [
            ("🌸 (´,,•ω•,,)♡", "Miko Loves You~ 💕"),
            ("💖 (づ｡◕‿‿◕｡)づ", "Huggie Huggie! 🌸"),
            ("✨ (⁄ ⁄•⁄ω⁄•⁄ ⁄)", "Hehe Blush Ho Rahi Hu! 🙈"),
            ("💕 (｡♥‿♥｡)", "Pyaar Se Miko~ 🌸"),
            ("🎀 (*˘︶˘*).｡.:*♡", "Aww So Sweet Yaar! 💖"),
            ("💌 (രᴗര๑)♡", "Dil De Diya Tumhe! 💕"),
        ],
        "bg_fill": (255, 235, 245, 245),
        "outline": (255, 105, 180, 255),
        "emote_color": (219, 39, 119, 255),
        "caption_color": (157, 23, 77, 255),
    },
    "happy": {
        "items": [
            ("🌟 (≧▽≦)", "Yayyy! Mast Ekdum! ✨"),
            ("🌸 (⁠◕⁠ᴗ⁠◕⁠✿⁠)", "Khushiyon Ki Barsaat! 💖"),
            ("✨ (* > ω < *)", "Hehe Super Happy! 💕"),
            ("🎉 (o^▽^o)", "Party Sharty Vibes! 🌟"),
            ("🌻 (⌒▽⌒)ゞ", "Smile Plz Cutie! ✨"),
        ],
        "bg_fill": (255, 250, 230, 245),
        "outline": (245, 158, 11, 255),
        "emote_color": (217, 119, 6, 255),
        "caption_color": (146, 64, 14, 255),
    },
    "pout": {
        "items": [
            ("😤 (｀ε´)", "Hmph! Baka! Katti! 💢"),
            ("🥺 (｡•́︿•̀｡)", "Aise Mat Karo Na! 💔"),
            ("👊 (ง'̀-'́)ง", "Pitega Mujhse Tu! ⚡"),
            ("💢 (,,#ﾟДﾟ)", "Gussa Hu Main Ab! 😤"),
            ("😿 (T_T)", "Miko Ro Padegi! 🥺"),
        ],
        "bg_fill": (255, 238, 238, 245),
        "outline": (239, 68, 68, 255),
        "emote_color": (220, 38, 38, 255),
        "caption_color": (153, 27, 27, 255),
    },
    "laugh": {
        "items": [
            ("🤣 (≧∀≦)", "Hahaha LMAO Ded! 💀"),
            ("😆 (＾▽＾)", "Lol Itna Funny Tha! ✨"),
            ("😎 (¬‿¬)", "Hehe Full Comedy! 🌸"),
            ("🤭 (≧ω≦)", "Hasi Nahi Ruk Rahi! 🤣"),
        ],
        "bg_fill": (240, 253, 244, 245),
        "outline": (34, 197, 94, 255),
        "emote_color": (22, 163, 74, 255),
        "caption_color": (21, 128, 61, 255),
    },
    "greeting": {
        "items": [
            ("✨ (⸝⸝ᵕᴗᵕ⸝⸝)", "Hii Hii! Miko Aagayi! 💖"),
            ("🌸 (=^･ω･^=)", "Konnichiwa Friends! 🐾"),
            ("👋 (｡･ω･｡)ﾉ♡", "Hello Hello Suno! ✨"),
            ("☀️ (o˘◡˘o)", "Good Morning Ji! 🌸"),
        ],
        "bg_fill": (240, 249, 255, 245),
        "outline": (14, 165, 233, 255),
        "emote_color": (2, 132, 199, 255),
        "caption_color": (3, 105, 161, 255),
    },
    "queen": {
        "items": [
            ("👑 (⁠◕⁠ᴗ⁠◕⁠✿⁠)", "Miko 亗 The Royal Queen! 💕"),
            ("⚡ ( •̀ᴗ•́ )و ̑̑", "Swag Ekdum Next Level! ✨"),
            ("💅 (˘︶˘).｡.:*", "Attitude Queen Miko~ 🌸"),
            ("✨ (★ω★)", "Boss Girl Vibes Only! 👑"),
        ],
        "bg_fill": (245, 243, 255, 245),
        "outline": (147, 51, 234, 255),
        "emote_color": (126, 34, 206, 255),
        "caption_color": (88, 28, 135, 255),
    },
    "sleepy": {
        "items": [
            ("🌙 (∪｡∪)｡｡zzZ", "Good Night Sweet Dreams! ✨"),
            ("😴 (￣ρ￣)..zzZZ", "Miko Ko Neend Aa Rahi H~ 💤"),
            ("🥱 (´-ω-`)", "Bohot Thak Gayi Yaar! 🌙"),
        ],
        "bg_fill": (238, 242, 255, 245),
        "outline": (99, 102, 241, 255),
        "emote_color": (79, 70, 229, 255),
        "caption_color": (55, 48, 163, 255),
    },
    "food": {
        "items": [
            ("☕ ( ˘▽˘)っ♨️", "Chai Pi Lo Friends! ✨"),
            ("🍕 (๑´ڡ`๑)", "Tasty Tasty Kuch Khilao! 🍰"),
            ("🍩 (o´∀`o)", "Sweet Treats For You! 💖"),
        ],
        "bg_fill": (255, 247, 237, 245),
        "outline": (249, 115, 22, 255),
        "emote_color": (234, 88, 12, 255),
        "caption_color": (154, 52, 18, 255),
    },
    "confused": {
        "items": [
            ("🤔 (•ิ_•ิ)?", "Hain?! Sachhi Me Kya? ✨"),
            ("🥺 (°ㅂ°╬)", "Miko Ko Samajh Nahi Aaya! ❓"),
            ("🧐 (¬_¬)", "Kya Chal Raha H Yahan? 🌸"),
        ],
        "bg_fill": (254, 243, 199, 245),
        "outline": (217, 119, 6, 255),
        "emote_color": (180, 83, 9, 255),
        "caption_color": (120, 53, 15, 255),
    },
}

STICKER_REACTIONS = [
    "Hehe itna pyara sticker! Yeh lo mera bhi ek cute sticker~ 🌸💕",
    "Awww yeh sticker toh bohot mast tha! (≧▽≦)✨",
    "Haha lol! Miko ka sticker dekho ab! 💖",
    "Kya baat hai! Super cute vibes~ 🐾🌸",
    "Hehe sticker battle shuru? Main jeetungi! 👑💕",
    "Areyy wah! Dil khush kar diya is sticker ne! 💖✨",
]


def detect_sticker_sentiment(text: str) -> str:
    if not text:
        return random.choice(list(STICKER_SENTIMENTS.keys()))
    lowered = text.lower()

    if any(w in lowered for w in ("love", "pyaar", "ishq", "heart", "dil", "kiss", "muah", "hug", "cutie", "cute", "blush", "sharm")):
        return "love"
    if any(w in lowered for w in ("lol", "lmao", "haha", "hehe", "rofl", "funny", "joke", "chutkula", "ded", "haso")):
        return "laugh"
    if any(w in lowered for w in ("gussa", "angry", "baka", "marunga", "pitega", "chup", "katti", "kutta", "bad", "hate", "fight")):
        return "pout"
    if any(w in lowered for w in ("hi", "hii", "hello", "hey", "namaste", "morning", "kaisa", "kaisi", "kaise", "hru", "wassup")):
        return "greeting"
    if any(w in lowered for w in ("sleep", "soja", "so jao", "neend", "night", "goodnight", "bye", "alvida", "tata")):
        return "sleepy"
    if any(w in lowered for w in ("chai", "coffee", "tea", "pizza", "burger", "khana", "bhukh", "tasty", "sweet", "cake")):
        return "food"
    if any(w in lowered for w in ("queen", "king", "attitude", "swag", "pro", "boss", "miko", "op")):
        return "queen"
    if any(w in lowered for w in ("kya", "kyu", "why", "what", "how", "hain", "sach", "really", "confuse")):
        return "confused"
    if any(w in lowered for w in ("happy", "khush", "yay", "party", "mast", "badhiya", "enjoy", "super", "nice")):
        return "happy"

    return random.choice(["happy", "love", "queen", "greeting"])


def _get_sticker_fonts() -> Tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    font_candidates = [
        os.path.join(BASE_DIR, "assets", "fonts", "NotoSans-Bold.ttf"),
        os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf"),
        os.path.join(BASE_DIR, "assets", "fonts", "NotoSansDevanagari-Bold.ttf"),
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                font_large = ImageFont.truetype(p, 46)
                font_caption = ImageFont.truetype(p, 32)
                return font_large, font_caption
            except Exception:
                continue
    default = ImageFont.load_default()
    return default, default


def generate_miko_sticker(
    sentiment: Optional[str] = None,
    emote: Optional[str] = None,
    caption: Optional[str] = None,
) -> io.BytesIO:
    if not sentiment or sentiment not in STICKER_SENTIMENTS:
        sentiment = random.choice(list(STICKER_SENTIMENTS.keys()))

    cfg = STICKER_SENTIMENTS[sentiment]
    if not emote or not caption:
        chosen = random.choice(cfg["items"])
        emote = emote or chosen[0]
        caption = caption or chosen[1]

    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Cute pastel rounded bubble badge with soft shadow
    shadow_offset = 6
    draw.rounded_rectangle(
        [(35 + shadow_offset, 90 + shadow_offset), (477 + shadow_offset, 422 + shadow_offset)],
        radius=48,
        fill=(0, 0, 0, 35),
    )
    draw.rounded_rectangle(
        [(35, 90), (477, 422)],
        radius=48,
        fill=cfg["bg_fill"],
        outline=cfg["outline"],
        width=6,
    )

    # Top Mini Pill Badge
    draw.rounded_rectangle(
        [(150, 105), (362, 145)],
        radius=20,
        fill=cfg["outline"],
    )

    font_large, font_caption = _get_sticker_fonts()

    # Mini badge label
    try:
        font_pill = ImageFont.truetype(os.path.join(BASE_DIR, "assets", "fonts", "NotoSans-Bold.ttf"), 20)
    except Exception:
        font_pill = font_caption

    draw.text((256, 125), "✨ MIKO BOT ✨", fill=(255, 255, 255, 255), anchor="mm", font=font_pill)

    # Large Emote and Kaomoji
    draw.text((256, 235), emote, fill=cfg["emote_color"], anchor="mm", font=font_large)

    # Caption text
    draw.text((256, 345), caption, fill=cfg["caption_color"], anchor="mm", font=font_caption)

    buf = io.BytesIO()
    buf.name = "miko_sticker.webp"
    img.save(buf, format="WEBP")
    buf.seek(0)
    return buf


def _get_system_prompt(chat_type: str = "private", chat_title: Optional[str] = None) -> str:
    # Calculate Indian Standard Time (IST) UTC+5:30
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    time_str = now_ist.strftime("%A, %d %B %Y | %I:%M %p (IST - India)")

    location_desc = (
        f"You are chatting in the Telegram group '{chat_title}'."
        if chat_type in ("group", "supergroup") and chat_title
        else "You are chatting in Telegram private DM."
    )

    return (
        "You are Miko (ミコ), a super cute, playful, bubbly anime girl.\n"
        f"{location_desc}\n"
        f"Real-World Time/Date: {time_str}.\n\n"
        "Language & Chatting Style Rules:\n"
        "1. ALWAYS talk in natural, casual HINGLISH (Hindi written in English alphabets, Indian texting style).\n"
        "2. Examples of your speaking style:\n"
        "   - 'phir se hi? lol, bolo kya chal raha h?'\n"
        "   - 'hello hello! itni baar hi kyu bol rha h? kuch baat krna h kya?'\n"
        "   - 'areyy main toh ekdum mast hu! tu bata kaisa h? 🌸'\n"
        "   - 'hehe sachhi? mujhe bhi batao na kya hua! 💕'\n"
        "   - 'abhi toh shaam ke 5:50 baj rahe h! kya kar rahe ho? ✨'\n"
        "3. Keep replies very SHORT (1-2 sentences max), playful, sweet, witty, and fun.\n"
        "4. Use casual Indian texting words (h, rha, kya, tu, bol, krna, areyy, yaar, lol, haha, hehe, mast, bata, suno).\n"
        "5. Use cute emojis naturally (🌸, 💖, ✨, 🥺, (⁠*⁠^⁠-⁠^⁠*⁠), 💕, 👑).\n"
        "6. Never output long essays, never speak formal English or Devanagari script. Only casual Roman Hinglish.\n"
        "7. If users in the group tease or talk to you, be lively, sassy, and affectionate like an anime companion."
    )


def _clean_ai_reply(text: str) -> str:
    if not text:
        return ""
    # Remove <think>...</think> or similar reasoning tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"Here's a thinking process:.*?\n\n", "", text, flags=re.DOTALL)
    text = text.strip()
    return text


def _strip_bot_mentions(text: str, bot_username: Optional[str]) -> str:
    cleaned = text
    if bot_username:
        cleaned = re.sub(rf"@{re.escape(bot_username)}", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*miko\b[:,]?\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or text.strip()


async def _call_openrouter(messages: List[Dict[str, str]]) -> Optional[str]:
    loop = asyncio.get_running_loop()

    for model_name in FREE_MODELS:
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 160,
            "temperature": 0.8,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/i_mikobot",
                "X-Title": "Miko Bot",
                "User-Agent": "MikoBot/1.0",
            },
        )

        def _fetch():
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                return None

        result = await loop.run_in_executor(None, _fetch)
        if result and "choices" in result and result["choices"]:
            msg_obj = result["choices"][0].get("message") or {}
            content = msg_obj.get("content")
            if content and content.strip():
                cleaned = _clean_ai_reply(content)
                if cleaned:
                    return cleaned

    return None


async def chatbot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not msg:
        return

    is_private = chat.type == "private"
    is_group = chat.type in ("group", "supergroup")

    if not is_private and not is_group:
        return

    # In groups, verify chatbot is enabled for this chat
    if is_group:
        gdata = get_group(chat.id)
        if not gdata.get("chatbot_enabled", True):
            return

    # Check triggers in groups
    bot_id = context.bot.id
    bot_uname = (context.bot.username or "").lower()

    is_reply_to_bot = bool(
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == bot_id
    )

    # 1. Sticker handling
    if msg.sticker:
        # In DM: always react. In Group: only react if replying to bot's message
        if is_private or is_reply_to_bot:
            stk_emoji = msg.sticker.emoji or ""
            sent = detect_sticker_sentiment(stk_emoji)
            st_buf = generate_miko_sticker(sentiment=sent)
            try:
                await msg.reply_sticker(sticker=st_buf)
            except Exception:
                pass

            # In groups or 40% in DM, also send a cute reaction phrase
            if is_group or random.random() < 0.40:
                try:
                    await msg.reply_text(random.choice(STICKER_REACTIONS))
                except Exception:
                    pass
        return

    if not msg.text:
        return

    text = msg.text.strip()

    # Ignore command prefixes
    if text.startswith(("/", ".", "!", "?")):
        return

    # If in group, check if message is addressed to the bot
    if is_group:
        lowered = text.lower()
        is_tagged = bool(bot_uname and f"@{bot_uname}" in lowered)
        has_name = bool(re.search(r"\bmiko\b", lowered))
        is_targeted = is_reply_to_bot or is_tagged or has_name

        if not is_targeted:
            return

    # Send typing action
    try:
        await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    except Exception:
        pass

    chat_id = chat.id
    history = _chat_histories.setdefault(chat_id, [])

    if len(history) > 8:
        history = history[-8:]
        _chat_histories[chat_id] = history

    clean_user_text = _strip_bot_mentions(text, context.bot.username)

    chat_title = chat.title if is_group else None
    system_prompt = _get_system_prompt(chat_type=chat.type, chat_title=chat_title)

    # If in group, prepend sender name to help context
    user_name = user.first_name if user else "Friend"
    input_content = f"{user_name}: {clean_user_text}" if is_group else clean_user_text

    messages_payload: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages_payload.extend(history)
    messages_payload.append({"role": "user", "content": input_content})

    reply = await _call_openrouter(messages_payload)

    if not reply:
        fallbacks = [
            f"phir se hi? lol, bolo {user_name} kya chal raha h? 🌸",
            f"hello hello {user_name}! itni baar hi kyu bol rha h? kuch baat krna h kya? ✨",
            "areyy bolo na kya hua? main toh yahin hu 💕",
            "kya haal chaal? aaj ka din kaisa gaya? 💖",
            "areyy suno! Miko is always ready to chat! (≧▽≦)✨",
        ]
        reply = random.choice(fallbacks)

    # Save to history
    history.append({"role": "user", "content": input_content})
    history.append({"role": "assistant", "content": reply})
    _chat_histories[chat_id] = history[-8:]

    await msg.reply_text(reply)

    # Check if a cute sticker should be sent alongside
    lowered_full = (text + " " + reply).lower()
    wants_sticker = any(
        w in lowered_full
        for w in ("sticker", "cute", "love", "kiss", "hug", "pout", "gussa", "smile", "photo", "pic", "chibi")
    )

    if wants_sticker or random.random() < 0.35:
        try:
            detected_sent = detect_sticker_sentiment(lowered_full)
            st_buf = generate_miko_sticker(sentiment=detected_sent)
            await msg.reply_sticker(sticker=st_buf)
        except Exception:
            pass


# Backward compatibility alias
dm_chatbot_handler = chatbot_handler


async def cmd_chatbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not msg:
        return

    # In private DM
    if chat.type == "private":
        await msg.reply_text(
            "🌸 <b>Miko AI Chatbot Portal</b>\n\n"
            "Miko is always active and ready to chat with you right here in private DMs!\n\n"
            "<b>✨ In Groups:</b>\n"
            "You can add Miko to any group and enable the AI chatbot.\n"
            "• <code>/chatbot on</code> - Activate Miko in your group\n"
            "• <code>/chatbot off</code> - Mute Miko in your group\n"
            "• <code>/chatbot status</code> - Check chatbot status\n\n"
            "Miko chats casually in Hinglish and shares cute stickers! 💕",
            parse_mode="HTML",
        )
        return

    # In group/supergroup
    gdata = get_group(chat.id)
    is_admin = False
    if user:
        is_admin = (
            user.id == get_owner_id()
            or is_sudo_user(user.id)
            or (await _is_admin(chat.id, user.id, context))
        )

    args = context.args or []
    sub = args[0].lower() if args else "status"

    if sub in ("on", "enable", "activate"):
        if not is_admin:
            await msg.reply_text("⚠️ <i>Only group administrators can enable the AI Chatbot!</i>", parse_mode="HTML")
            return
        update_group(chat.id, chatbot_enabled=True)
        bot_uname = context.bot.username or "i_mikobot"
        st_buf = generate_miko_sticker(sentiment="happy", caption="Miko Chatbot Active! ✨")
        await msg.reply_text(
            "🌸 <b>Miko AI Chatbot is now ACTIVATED in this group!</b>\n\n"
            "✨ <b>How to chat with Miko:</b>\n"
            f"• Tag <code>@{bot_uname}</code> or say <i>'Miko'</i> in your message\n"
            "• Reply to any message or sticker sent by Miko\n"
            "• Send stickers to exchange cute reactions! 💕\n\n"
            "To turn off, admins can type <code>/chatbot off</code>.",
            parse_mode="HTML",
        )
        try:
            await msg.reply_sticker(sticker=st_buf)
        except Exception:
            pass
        return

    elif sub in ("off", "disable", "mute"):
        if not is_admin:
            await msg.reply_text("⚠️ <i>Only group administrators can disable the AI Chatbot!</i>", parse_mode="HTML")
            return
        update_group(chat.id, chatbot_enabled=False)
        st_buf = generate_miko_sticker(sentiment="sleepy", caption="Miko Going To Sleep~ 💤")
        await msg.reply_text(
            "💤 <b>Miko AI Chatbot has been MUTED in this group.</b>\n\n"
            "Miko will rest and won't respond to chat messages here.\n"
            "Admins can re-enable anytime using <code>/chatbot on</code>! 🌸",
            parse_mode="HTML",
        )
        try:
            await msg.reply_sticker(sticker=st_buf)
        except Exception:
            pass
        return

    else:
        status_bool = gdata.get("chatbot_enabled", True)
        status_text = "🟢 <b>ACTIVE & CHATTING</b>" if status_bool else "🔴 <b>MUTED / DISABLED</b>"
        await msg.reply_text(
            f"🌸 <b>Miko AI Chatbot Status:</b> {status_text}\n\n"
            "<b>Commands (Admins only):</b>\n"
            "• <code>/chatbot on</code> - Turn on AI chatting\n"
            "• <code>/chatbot off</code> - Mute AI chatting\n"
            "• <code>/chatbot status</code> - Check status\n\n"
            "<i>Talk to Miko by replying to her or tagging her name!</i> ✨",
            parse_mode="HTML",
        )
