from __future__ import annotations

import os
import json
import asyncio
import urllib.request
from typing import Tuple
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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",
)

FREE_AI_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "poolside/laguna-s-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
]

LANG_MAP = {
    "hindi": "hi",
    "english": "en",
    "hinglish": "hinglish",
    "urdu": "ur",
    "bengali": "bn",
    "marathi": "mr",
    "telugu": "te",
    "tamil": "ta",
    "gujarati": "gu",
    "punjabi": "pa",
    "kannada": "kn",
    "malayalam": "ml",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "russian": "ru",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh-CN",
    "arabic": "ar",
    "turkish": "tr",
    "italian": "it",
    "portuguese": "pt",
}


def detect_source_language(text: str) -> str:
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "Hindi"
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        return "Urdu"
    if any("\u0400" <= ch <= "\u04ff" for ch in text):
        return "Russian"
    if any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in text):
        return "Japanese"
    if any("\uac00" <= ch <= "\ud7af" for ch in text):
        return "Korean"
    if any("\u0980" <= ch <= "\u09ff" for ch in text):
        return "Bengali"
    if any("\u0a80" <= ch <= "\u0aff" for ch in text):
        return "Gujarati"
    if any("\u0a00" <= ch <= "\u0a7f" for ch in text):
        return "Punjabi"
    if any("\u0b80" <= ch <= "\u0bff" for ch in text):
        return "Tamil"
    if any("\u0c00" <= ch <= "\u0c7f" for ch in text):
        return "Telugu"
    if any("\u0621" <= ch <= "\u064a" for ch in text):
        return "Arabic"
    return "English"


def normalize_target_lang(lang_str: str) -> str:
    cleaned = lang_str.strip().lower()
    return LANG_MAP.get(cleaned, cleaned)


async def ai_translate(text: str, target_lang: str) -> Tuple[str, str, str]:
    target_clean = target_lang.strip()
    src_lang = detect_source_language(text)
    tgt_lang = target_clean.title()

    target_code = normalize_target_lang(target_clean)

    # 1. Try OpenRouter AI translation
    if OPENROUTER_API_KEY:
        prompt = (
            f"You are a professional translator. Translate the following text into {target_clean}. "
            "Keep the original tone, meaning, emojis, and formatting. "
            "Output ONLY the translated sentence without quotes, notes, or explanations.\n\n"
            f"Text to translate:\n{text}"
        )

        for model in FREE_AI_MODELS:
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional multilingual translator. Output only the pure translation.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1000,
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=data,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://telegram.org",
                        "X-Title": "Miko Bot",
                        "User-Agent": "MikoBot/1.0",
                    },
                )
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None, lambda: urllib.request.urlopen(req, timeout=5)
                )
                res_json = json.loads(response.read().decode("utf-8"))
                reply = res_json["choices"][0]["message"]["content"].strip()
                if reply and len(reply) > 0:
                    return reply, src_lang, tgt_lang
            except Exception:
                continue

    # 2. Fallback to GoogleTranslator
    try:
        translated = GoogleTranslator(source="auto", target=target_code).translate(text[:1000])
        return translated, src_lang, tgt_lang
    except Exception:
        return text, src_lang, tgt_lang
