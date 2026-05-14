#!/usr/bin/env python3
"""Batch image search v2 — uses web scraping + multiple sources, no API quota limits."""

import os
import re
import sys
import time
import json
import requests
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
load_dotenv()

from database import get_conn
import psycopg2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
MIN_SIZE = 80

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CX = os.getenv("GOOGLE_CX", "")
google_available = True


def get_missing_products():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, upc FROM products WHERE image_data IS NULL ORDER BY id")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def save_image_to_db(product_id, image_data, source_url=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE products SET image_data=%s, image_source=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
        (psycopg2.Binary(image_data), source_url, product_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def pad_upc(upc):
    if not upc:
        return []
    variants = [upc]
    if len(upc) < 12:
        variants.append(upc.zfill(12))
    if len(upc) < 13:
        variants.append(upc.zfill(13))
    return list(set(variants))


def download_and_validate(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        ct = resp.headers.get("content-type", "")
        if "image" not in ct and "octet" not in ct:
            return None
        data = resp.content
        if len(data) < 1000:
            return None
        from PIL import Image
        img = Image.open(BytesIO(data))
        w, h = img.size
        if w < MIN_SIZE or h < MIN_SIZE:
            return None
        img = img.convert("RGB")
        img.thumbnail((400, 400), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return None


# ── Source 1: UPCitemdb ──
def search_upcitemdb(upc):
    for variant in pad_upc(upc):
        try:
            resp = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={variant}",
                                headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    for img_url in item.get("images", []):
                        if img_url:
                            data = download_and_validate(img_url)
                            if data:
                                return data, img_url
            time.sleep(0.5)
        except Exception:
            pass
    return None, None


# ── Source 2: Open Food Facts ──
def search_openfoodfacts(upc):
    for variant in pad_upc(upc):
        try:
            resp = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{variant}.json",
                                headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 1:
                    product = data.get("product", {})
                    for key in ["image_front_url", "image_url", "image_front_small_url"]:
                        img_url = product.get(key, "")
                        if img_url:
                            img_data = download_and_validate(img_url)
                            if img_data:
                                return img_data, img_url
            time.sleep(0.3)
        except Exception:
            pass
    return None, None


# ── Source 3: Walmart search scrape ──
def search_walmart(name):
    try:
        query = re.sub(r'[^a-zA-Z0-9 ]', '', name).strip()[:60]
        url = f"https://www.walmart.com/search?q={quote_plus(query)}"
        resp = requests.get(url, headers={
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml",
        }, timeout=15)
        if resp.status_code != 200:
            return None, None
        # Look for product image URLs in the page
        img_patterns = re.findall(r'(https://i5\.walmartimages\.com/[^"\']+(?:\.jpeg|\.jpg|\.png))', resp.text)
        for img_url in img_patterns[:5]:
            # Skip tiny thumbnails
            if "odnHeight=80" in img_url or "odnWidth=80" in img_url:
                continue
            # Try to get a good size
            clean_url = re.sub(r'\?.*', '', img_url)
            data = download_and_validate(clean_url + "?odnHeight=400&odnWidth=400&odnBg=ffffff")
            if data:
                return data, clean_url
            data = download_and_validate(img_url)
            if data:
                return data, img_url
        time.sleep(1)
    except Exception:
        pass
    return None, None


# ── Source 4: Google Custom Search (if available) ──
def search_google(name):
    global google_available
    if not google_available or not GOOGLE_API_KEY or not GOOGLE_CX:
        return None, None
    try:
        query = re.sub(r'[()]', '', name).strip()[:80]
        resp = requests.get("https://www.googleapis.com/customsearch/v1", params={
            "key": GOOGLE_API_KEY, "cx": GOOGLE_CX,
            "q": query + " product", "searchType": "image",
            "num": 3, "imgSize": "medium", "safe": "active"
        }, timeout=15)
        if resp.status_code == 200:
            for item in resp.json().get("items", []):
                img_url = item.get("link", "")
                if img_url:
                    data = download_and_validate(img_url)
                    if data:
                        return data, img_url
        elif resp.status_code == 429:
            print("  [Google quota exceeded - disabling]")
            google_available = False
        time.sleep(0.3)
    except Exception:
        pass
    return None, None


# ── Source 5: Brand-specific websites ──
BRAND_URLS = {
    "GEFEN": "https://www.gefenfoods.com",
    "KEDEM": "https://www.kedemfoods.com",
    "ELITE": "https://www.elitefoods.com",
    "HADDAR": "https://www.haddarfoods.com",
    "TUSCANINI": "https://www.tuscaninifoods.com",
    "PASKESZ": "https://www.paskesz.com",
    "GLICKS": "https://www.glicks.com",
}

def search_brand_site(name):
    brand = name.split()[0].upper() if name else ""
    base_url = BRAND_URLS.get(brand)
    if not base_url:
        return None, None
    try:
        query = re.sub(r'[^a-zA-Z0-9 ]', '', name).strip()[:50]
        search_url = f"{base_url}/search?q={quote_plus(query)}"
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            img_patterns = re.findall(r'(https?://[^"\']+(?:\.jpg|\.jpeg|\.png|\.webp))', resp.text)
            for img_url in img_patterns[:5]:
                if "logo" in img_url.lower() or "icon" in img_url.lower():
                    continue
                data = download_and_validate(img_url)
                if data:
                    return data, img_url
        time.sleep(0.5)
    except Exception:
        pass
    return None, None


# ── Source 6: DuckDuckGo image search ──
def search_duckduckgo(name):
    try:
        query = re.sub(r'[^a-zA-Z0-9 ]', '', name).strip()[:60]
        # Get vqd token first
        resp = requests.get(f"https://duckduckgo.com/?q={quote_plus(query)}&iax=images&ia=images",
                            headers=HEADERS, timeout=10)
        vqd_match = re.search(r'vqd=["\']([^"\']+)', resp.text)
        if not vqd_match:
            return None, None
        vqd = vqd_match.group(1)

        img_resp = requests.get("https://duckduckgo.com/i.js", params={
            "l": "us-en", "o": "json", "q": query + " product kosher",
            "vqd": vqd, "f": ",,,,,", "p": "1"
        }, headers={**HEADERS, "Referer": "https://duckduckgo.com/"}, timeout=10)

        if img_resp.status_code == 200:
            results = img_resp.json().get("results", [])
            for r in results[:5]:
                img_url = r.get("image", "")
                if img_url:
                    data = download_and_validate(img_url)
                    if data:
                        return data, img_url
        time.sleep(1.5)
    except Exception:
        pass
    return None, None


def main():
    products = get_missing_products()
    print(f"\n{'='*50}")
    print(f"  Batch Image Search v2 — Multi-Source")
    print(f"  Products missing images: {len(products)}")
    print(f"  Google API: {'active' if GOOGLE_API_KEY else 'N/A'}")
    print(f"{'='*50}\n")

    found = 0
    not_found_list = []
    sources_used = {}

    for i, p in enumerate(products):
        pid, name, upc = p["id"], p["name"], p["upc"]
        print(f"[{i+1}/{len(products)}] {name}")

        # Try each source in order
        for source_name, search_fn, search_arg in [
            ("UPCitemdb", search_upcitemdb, upc),
            ("OpenFoodFacts", search_openfoodfacts, upc),
            ("Google", search_google, name),
            ("Walmart", search_walmart, name),
            ("BrandSite", search_brand_site, name),
            ("DuckDuckGo", search_duckduckgo, name),
        ]:
            img_data, source_url = search_fn(search_arg)
            if img_data and img_data != "QUOTA":
                save_image_to_db(pid, img_data, source_url or "")
                found += 1
                sources_used[source_name] = sources_used.get(source_name, 0) + 1
                print(f"  -> FOUND via {source_name}")
                break
        else:
            not_found_list.append(name)
            print(f"  -> NOT FOUND")

    print(f"\n{'='*50}")
    print(f"  RESULTS")
    print(f"  Found: {found}")
    print(f"  Not found: {len(not_found_list)}")
    print(f"  Total with images: {122 + found}/228")
    print(f"\n  Sources breakdown:")
    for src, cnt in sorted(sources_used.items(), key=lambda x: -x[1]):
        print(f"    {src}: {cnt}")
    if not_found_list:
        print(f"\n  Still missing:")
        for n in not_found_list:
            print(f"    - {n}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
