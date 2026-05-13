import json
import os
import time
from pathlib import Path


CACHE_FILE = Path(__file__).parent / "output" / "translation_cache.json"


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def translate_to_hebrew(texts: list) -> dict:
    cache = load_cache()
    results = {}
    to_translate = []

    for text in texts:
        if text in cache:
            results[text] = cache[text]
        else:
            to_translate.append(text)

    if to_translate:
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source="en", target="iw")
            for text in to_translate:
                try:
                    translated = translator.translate(text)
                    results[text] = translated
                    cache[text] = translated
                    time.sleep(0.3)
                except Exception:
                    results[text] = text
        except ImportError:
            for text in to_translate:
                results[text] = text

    save_cache(cache)
    return results
