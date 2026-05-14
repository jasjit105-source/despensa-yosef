#!/usr/bin/env python3
"""Batch image search for products missing images in the database."""

import os
import sys
import time
import hashlib
import requests
from pathlib import Path
from io import BytesIO

from dotenv import load_dotenv
load_dotenv()

from database import get_conn
import psycopg2

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CX = os.getenv("GOOGLE_CX", "")
IMG_DIR = Path(__file__).parent / "output" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
MIN_SIZE = 80


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
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and "octet" not in content_type:
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


def search_upcitemdb(upc):
    for variant in pad_upc(upc):
        try:
            url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={variant}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    for item in items:
                        images = item.get("images", [])
                        for img_url in images:
                            if img_url and ("walmart" in img_url or "amazon" in img_url or "target" in img_url or ".jpg" in img_url or ".png" in img_url):
                                img_data = download_and_validate(img_url)
                                if img_data:
                                    return img_data, img_url
            time.sleep(0.5)
        except Exception:
            pass
    return None, None


def search_openfoodfacts(upc):
    for variant in pad_upc(upc):
        try:
            url = f"https://world.openfoodfacts.org/api/v0/product/{variant}.json"
            resp = requests.get(url, headers=HEADERS, timeout=10)
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


def search_google(name):
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return None, None
    try:
        query = name.replace("(", "").replace(")", "").strip()
        if len(query) > 80:
            query = query[:80]
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY, "cx": GOOGLE_CX,
            "q": query + " product", "searchType": "image",
            "num": 3, "imgSize": "medium", "safe": "active"
        }
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                img_url = item.get("link", "")
                if img_url:
                    img_data = download_and_validate(img_url)
                    if img_data:
                        return img_data, img_url
        elif resp.status_code == 429:
            print("  [Google quota exceeded, skipping Google for remaining]")
            return "QUOTA", None
        time.sleep(0.3)
    except Exception as e:
        print(f"  [Google error: {e}]")
    return None, None


def main():
    products = get_missing_products()
    print(f"\n=== Batch Image Search ===")
    print(f"Products missing images: {len(products)}")
    print(f"Google API: {'active' if GOOGLE_API_KEY else 'not configured'}")
    print()

    found = 0
    not_found = 0
    google_available = True

    for i, p in enumerate(products):
        pid, name, upc = p["id"], p["name"], p["upc"]
        print(f"[{i+1}/{len(products)}] {name} (UPC: {upc})")

        # 1. Try UPCitemdb
        img_data, source = search_upcitemdb(upc)
        if img_data:
            save_image_to_db(pid, img_data, source)
            found += 1
            print(f"  FOUND via UPCitemdb")
            continue

        # 2. Try Open Food Facts
        img_data, source = search_openfoodfacts(upc)
        if img_data:
            save_image_to_db(pid, img_data, source)
            found += 1
            print(f"  FOUND via OpenFoodFacts")
            continue

        # 3. Try Google Custom Search
        if google_available:
            result, source = search_google(name)
            if result == "QUOTA":
                google_available = False
            elif result:
                save_image_to_db(pid, result, source)
                found += 1
                print(f"  FOUND via Google")
                continue

        not_found += 1
        print(f"  NOT FOUND")

    print(f"\n=== Results ===")
    print(f"Found: {found}")
    print(f"Not found: {not_found}")
    print(f"Total with images now: {122 + found}/228")


if __name__ == "__main__":
    main()
