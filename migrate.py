#!/usr/bin/env python3
"""Migrate existing products + images from local cache into Neon PostgreSQL"""

import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from database import init_db, upsert_product

MARKUP = float(os.getenv("MARKUP_PERCENT", "37"))
EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE", "18"))

OUTPUT_DIR = Path(__file__).parent / "output"
IMAGE_CACHE = OUTPUT_DIR / "image_cache.json"
TRANSLATION_CACHE = OUTPUT_DIR / "translation_cache.json"
IMAGE_MAPPING = OUTPUT_DIR / "image_mapping.json"


def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    print("Initializing database...")
    init_db()

    import pandas as pd
    from category_detector import detect_category

    excel_path = "/Users/mac/Dropbox/My Mac (MacBook-Pro.local)/Downloads/Grocery List .xlsx"
    df = pd.read_excel(excel_path)
    print(f"Read {len(df)} rows from Excel")

    translations = load_json(TRANSLATION_CACHE)
    image_cache = load_json(IMAGE_CACHE)

    migrated = 0
    for _, row in df.iterrows():
        name = str(row.get("Item Description", "")).strip()
        if not name or name == "nan":
            continue

        upc_raw = row.get("UPC", "")
        try:
            upc = str(int(float(upc_raw))) if pd.notna(upc_raw) else ""
        except (ValueError, TypeError):
            upc = ""

        price_raw = row.get("PRICE", 0)
        try:
            price = float(price_raw) if pd.notna(price_raw) else 0
        except (ValueError, TypeError):
            price = 0

        size = str(row.get("Size", "")).strip()
        if size == "nan":
            size = ""

        pack_raw = row.get("Pack", 1)
        try:
            pack = float(pack_raw) if pd.notna(pack_raw) else 1
        except (ValueError, TypeError):
            pack = 1
        if pack == 0:
            pack = 1

        brand = name.split()[0] if name else ""
        category = detect_category(name)
        unit_cost = round(price / pack, 2)
        retail_usd = math.ceil(unit_cost * (1 + MARKUP / 100) * 100) / 100
        retail_mxn = round(retail_usd * EXCHANGE_RATE, 2)

        hebrew = translations.get(name, "")

        product = {
            "name": name, "hebrew_name": hebrew, "spanish_name": "",
            "upc": upc, "brand": brand, "category": category, "size": size,
            "case_price": price, "pack_qty": int(pack), "unit_cost": unit_cost,
            "retail_price_usd": retail_usd, "retail_price_mxn": retail_mxn,
        }

        cache_key = name.strip().lower()
        img_info = image_cache.get(cache_key, {})
        if img_info.get("status") == "found" and img_info.get("local_path"):
            img_path = img_info["local_path"]
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    product["image_data"] = f.read()
                product["image_source"] = img_info.get("source_url", "")

        upsert_product(product)
        migrated += 1
        if migrated % 50 == 0:
            print(f"  Migrated {migrated} products...")

    print(f"\nMigration complete: {migrated} products loaded into Neon")


if __name__ == "__main__":
    main()
