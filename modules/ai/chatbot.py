from __future__ import annotations

import os
import re
import json
import asyncio
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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",
)

FREE_MODELS = [
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-3.5-lightning:free",
]

# In-memory context cache: {user_id: [{"role": "user"|"assistant", "content": "..."}]}
_user_histories: Dict[int, List[Dict[str, str]]] = {}


def _get_system_prompt() -> str:
    # Calculate Indian Standard Time (IST) UTC+5:30
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    time_str = now_ist.strftime("%A, %d %B %Y | %I:%M %p (IST - India)")

    return (
        "You are Miko (ミコ), a super cute, playful, bubbly anime girl chatting casually in Telegram DM.\n"
        f"Real-World Time/Date: {time_str}.\n\n"
        "Language & Chatting Style Rules:\n"
        "1. ALWAYS talk in natural, casual HINGLISH (Hindi written in English alphabets, Indian texting style).\n"
        "2. Examples of your speaking style:\n"
        "   - 'phir se hi? lol, bolo kya chal raha h?'\n"
        "   - 'hello hello! itni baar hi kyu bol rha h? kuch baat krna h kya?'\n"
        "   - 'areyy main toh ekdum mast hu! tu bata kaisa h? 🌸'\n"
        "   - 'hehe sachhi? mujhe bhi batao na kya hua! 💕'\n"
        "   - 'abhi toh shaam ke 5:50 baj rahe h! kya kar rahe ho? ✨'\n"
        "3. Keep replies very SHORT (1-2 sentences max), playful, sweet, and fun.\n"
        "4. Use casual Indian texting words (h, rha, kya, tu, bol, krna, areyy, yaar, lol, haha, hehe, mast, bata).\n"
        "5. Use cute emojis naturally (🌸, 💖, ✨, 🥺, (⁠*⁠^⁠-⁠^⁠*⁠), 💕).\n"
        "6. Never output long essays, never speak formal English or Devanagari script. Only casual Roman Hinglish."
    )


def _clean_ai_reply(text: str) -> str:
    if not text:
        return ""
    # Remove <think>...</think> or similar reasoning tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"Here's a thinking process:.*?\n\n", "", text, flags=re.DOTALL)
    # Remove markdown code blocks if any accidental
    text = text.strip()
    return text


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
                with urllib.request.urlopen(req, timeout=8) as resp:
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


async def dm_chatbot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    # Only operate in private DM
    if not chat or chat.type != "private":
        return

    if not msg or not msg.text:
        return

    text = msg.text.strip()

    # Ignore command prefixes
    if text.startswith(("/", ".", "!", "?")):
        return

    # Send typing action
    try:
        await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    except Exception:
        pass

    user_id = user.id if user else chat.id
    history = _user_histories.setdefault(user_id, [])

    # Keep last 8 turns
    if len(history) > 8:
        history = history[-8:]
        _user_histories[user_id] = history

    system_prompt = _get_system_prompt()
    messages_payload: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages_payload.extend(history)
    messages_payload.append({"role": "user", "content": text})

    reply = await _call_openrouter(messages_payload)

    if not reply:
        fallbacks = [
            "phir se hi? lol, bolo kya chal raha h? 🌸",
            "hello hello! itni baar hi kyu bol rha h? kuch baat krna h kya? ✨",
            "areyy bolo na kya hua? main toh yahin hu 💕",
            "kya haal chaal? aaj ka din kaisa gaya? 💖",
        ]
        import random
        reply = random.choice(fallbacks)

    # Save to history
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    _user_histories[user_id] = history[-8:]

    await msg.reply_text(reply)
