from typing import Optional

import hashlib
import json
import os
import time
from pathlib import Path
from io import BytesIO

import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
CX = os.getenv("GOOGLE_CX")
OUTPUT_DIR = Path(__file__).parent / "output" / "images"
CACHE_FILE = Path(__file__).parent / "output" / "image_cache.json"
SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
OFF_API = "https://world.openfoodfacts.org/api/v0/product/{}.json"
UPCITEMDB_API = "https://api.upcitemdb.com/prod/trial/lookup"

MIN_WIDTH = 80
MIN_HEIGHT = 80
TARGET_SIZE = (400, 400)
DELAY_BETWEEN_REQUESTS = 0.8


def load_image_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_image_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def safe_filename(name: str) -> str:
    h = hashlib.md5(name.encode()).hexdigest()[:8]
    clean = "".join(c if c.isalnum() or c in " -_" else "" for c in name)
    clean = clean.strip().replace(" ", "_")[:60]
    return f"{clean}_{h}"


def search_product_image(product_name: str, upc: str = None) -> dict:
    cache = load_image_cache()
    cache_key = product_name.strip().lower()

    if cache_key in cache:
        cached = cache[cache_key]
        if cached.get("status") == "found" and Path(cached.get("local_path", "")).exists():
            return cached

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Try UPCitemdb (best for grocery products — returns Walmart/Amazon images)
    if upc:
        result = _search_upcitemdb(upc, product_name)
        if result:
            cache[cache_key] = result
            save_image_cache(cache)
            return result
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # 2. Try Open Food Facts (free barcode database)
    if upc:
        result = _search_openfoodfacts(upc, product_name)
        if result:
            cache[cache_key] = result
            save_image_cache(cache)
            return result
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # 3. Try Google Custom Search API
    result = _search_google(product_name)
    if result:
        cache[cache_key] = result
        save_image_cache(cache)
        return result

    error_result = {
        "product": product_name,
        "status": "not_found",
        "local_path": "",
        "source_url": "",
    }
    cache[cache_key] = error_result
    save_image_cache(cache)
    return error_result


def _search_upcitemdb(upc: str, product_name: str) -> Optional[dict]:
    upc_variants = list(dict.fromkeys([upc, upc.zfill(13), upc.zfill(12)]))
    for code in upc_variants:
        try:
            resp = requests.get(UPCITEMDB_API, params={"upc": code},
                                headers={"User-Agent": "DespensaYosef/1.0"},
                                timeout=10)
            if resp.status_code == 429:
                return None
            if resp.status_code != 200:
                continue

            data = resp.json()
            items = data.get("items", [])
            if not items:
                continue

            images = items[0].get("images", [])
            for img_url in images:
                if not img_url:
                    continue
                result = _download_and_process(img_url, product_name)
                if result:
                    return result
        except Exception:
            continue
    return None


def _search_openfoodfacts(upc: str, product_name: str) -> Optional[dict]:
    upc_variants = list(dict.fromkeys([upc, upc.zfill(13), upc.zfill(12)]))
    for code in upc_variants:
        try:
            resp = requests.get(OFF_API.format(code), timeout=10, headers={
                "User-Agent": "DespensaYosef/1.0"
            })
            if resp.status_code != 200:
                continue

            data = resp.json()
            if data.get("status") != 1:
                continue

            product = data.get("product", {})
            img_url = (product.get("image_front_url")
                       or product.get("image_url")
                       or product.get("image_front_small_url", ""))
            if not img_url:
                continue

            result = _download_and_process(img_url, product_name)
            if result:
                return result
        except Exception:
            continue
    return None


def _search_google(product_name: str) -> Optional[dict]:
    if not API_KEY or not CX:
        return None
    queries = [
        f"{product_name} kosher product",
        f"{product_name} grocery",
    ]
    for query in queries:
        result = _google_image_search(query, product_name)
        if result:
            return result
        time.sleep(DELAY_BETWEEN_REQUESTS)
    return None


def _google_image_search(query: str, product_name: str) -> Optional[dict]:
    try:
        resp = requests.get(SEARCH_URL, params={
            "key": API_KEY,
            "cx": CX,
            "q": query,
            "searchType": "image",
            "num": 5,
            "imgSize": "medium",
            "safe": "active",
        }, timeout=10)

        if resp.status_code in (429, 403):
            return None
        if resp.status_code != 200:
            return None

        data = resp.json()
        if "error" in data:
            return None

        for item in data.get("items", []):
            img_url = item.get("link", "")
            if not img_url:
                continue
            downloaded = _download_and_process(img_url, product_name)
            if downloaded:
                return downloaded
    except Exception:
        pass
    return None


def _download_and_process(url: str, product_name: str) -> Optional[dict]:
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        if resp.status_code != 200:
            return None

        img = Image.open(BytesIO(resp.content))

        if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
            return None

        if img.mode in ("RGBA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail(TARGET_SIZE, Image.LANCZOS)

        filename = safe_filename(product_name) + ".jpg"
        filepath = OUTPUT_DIR / filename
        img.save(filepath, "JPEG", quality=90, optimize=True)

        return {
            "product": product_name,
            "status": "found",
            "local_path": str(filepath),
            "source_url": url,
        }
    except Exception:
        return None


def search_batch(products: list, progress_callback=None) -> list:
    results = []
    total = len(products)

    for i, product in enumerate(products):
        name = product.get("name", "")
        upc = product.get("upc", "")

        if progress_callback:
            progress_callback(i + 1, total, name)
        else:
            print(f"  [{i+1}/{total}] Searching: {name}")

        result = search_product_image(name, upc)
        results.append(result)

    return results
