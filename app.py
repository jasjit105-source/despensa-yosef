#!/usr/bin/env python3
"""Despensa Yosef - Premium Kosher Grocery Catalog Generator"""

import argparse
import json
import math
import sys
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from category_detector import detect_category
from translator import translate_to_hebrew
from price_calculator import calculate_unit_price
from image_search import search_batch
from pdf_generator import CatalogPDF
from web_generator import generate_web_catalog

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Despensa Yosef")
WHATSAPP = os.getenv("WHATSAPP_NUMBER", "")
MARKUP = float(os.getenv("MARKUP_PERCENT", "37"))


def read_excel(filepath: str) -> pd.DataFrame:
    print(f"\n{'='*60}")
    print(f"  DESPENSA YOSEF - Catalog Generator")
    print(f"{'='*60}")
    print(f"\n[1/6] Reading Excel file: {filepath}")

    df = pd.read_excel(filepath)

    col_map = {}
    for col in df.columns:
        cl = col.lower().strip()
        if cl.startswith("unnamed"):
            continue
        if ("item" in cl or "description" in cl or "product" in cl) and "name" not in col_map:
            col_map["name"] = col
        elif ("upc" in cl or "barcode" in cl or "ean" in cl) and "upc" not in col_map:
            col_map["upc"] = col
        elif ("price" in cl and "unit" not in cl) and "price" not in col_map:
            col_map["price"] = col
        elif ("size" in cl or "weight" in cl) and "size" not in col_map:
            col_map["size"] = col
        elif ("pack" in cl or "qty" in cl or "quantity" in cl) and "pack" not in col_map:
            col_map["pack"] = col
        elif "brand" in cl and "brand" not in col_map:
            col_map["brand"] = col
        elif ("category" == cl) and "category" not in col_map:
            col_map["category"] = col

    if "name" not in col_map:
        col_map["name"] = df.columns[0]

    products = []
    for _, row in df.iterrows():
        name = str(row.get(col_map.get("name", ""), "")).strip()
        if not name or name == "nan":
            continue

        upc_raw = row.get(col_map.get("upc", ""), "")
        try:
            upc = str(int(float(upc_raw))) if pd.notna(upc_raw) else ""
        except (ValueError, TypeError):
            upc = str(upc_raw).strip() if pd.notna(upc_raw) else ""

        price_raw = row.get(col_map.get("price", ""), 0)
        try:
            price = float(price_raw) if pd.notna(price_raw) else 0
        except (ValueError, TypeError):
            price = 0

        size = str(row.get(col_map.get("size", ""), "")).strip()
        if size == "nan":
            size = ""

        pack_raw = row.get(col_map.get("pack", ""), 1)
        try:
            pack = float(pack_raw) if pd.notna(pack_raw) else 1
        except (ValueError, TypeError):
            pack = 1
        if pack == 0:
            pack = 1

        brand_raw = row.get(col_map.get("brand", ""), "")
        if pd.notna(brand_raw) and str(brand_raw).strip() and str(brand_raw).strip() != "nan":
            brand = str(brand_raw).strip()
        else:
            brand = name.split()[0] if name else ""

        if col_map.get("category") and pd.notna(row.get(col_map["category"], "")):
            category = str(row[col_map["category"]]).strip()
        else:
            category = detect_category(name)

        products.append({
            "name": name,
            "upc": upc,
            "brand": brand,
            "case_price": price,
            "pack": pack,
            "size": size,
            "category": category,
        })

    print(f"  Found {len(products)} products")
    return products


def calculate_prices(products: list[dict]) -> list[dict]:
    print(f"\n[2/6] Calculating retail prices ({MARKUP}% markup)")
    for p in products:
        pricing = calculate_unit_price(p["case_price"], p["pack"], MARKUP)
        p["unit_cost"] = pricing["unit_cost"]
        p["retail_price"] = pricing["retail_price"]
    return products


def categorize_products(products: list[dict]) -> tuple[list[dict], list[str]]:
    print(f"\n[3/6] Categorizing products")
    categories = set()
    for p in products:
        categories.add(p["category"])
    cat_list = sorted(categories)
    print(f"  Found {len(cat_list)} categories: {', '.join(cat_list)}")
    return products, cat_list


def translate_names(products: list[dict]) -> list[dict]:
    print(f"\n[4/6] Translating product names to Hebrew")
    names = [p["name"] for p in products]
    translations = translate_to_hebrew(names)
    for p in products:
        p["hebrew_name"] = translations.get(p["name"], p["name"])
    print(f"  Translated {len(translations)} names")
    return products


def search_images(products: list[dict], skip_images: bool = False) -> tuple[list[dict], list[dict]]:
    print(f"\n[5/6] Searching and downloading product images")

    if skip_images:
        print("  [SKIPPED] Image search disabled")
        for p in products:
            p["image_path"] = ""
            p["image_status"] = "skipped"
        return products, []

    search_input = [{"name": p["name"], "upc": p["upc"]} for p in products]
    results = search_batch(search_input)

    errors = []
    for p, r in zip(products, results):
        p["image_path"] = r.get("local_path", "")
        p["image_status"] = r.get("status", "not_found")
        p["image_source"] = r.get("source_url", "")
        if r.get("status") != "found":
            errors.append({"product": p["name"], "upc": p["upc"], "reason": "Image not found"})

    found = sum(1 for p in products if p["image_status"] == "found")
    print(f"  Found images: {found}/{len(products)}")
    return products, errors


def generate_outputs(products: list[dict], categories: list[str], errors: list[dict]):
    print(f"\n[6/6] Generating catalog outputs")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    products_by_cat = defaultdict(list)
    for p in products:
        products_by_cat[p["category"]].append(p)
    products_by_cat = dict(sorted(products_by_cat.items()))

    pdf_path = str(OUTPUT_DIR / "catalog.pdf")
    pdf = CatalogPDF(pdf_path, BUSINESS_NAME, WHATSAPP)
    pdf.generate(products_by_cat)

    generate_web_catalog(products, categories, BUSINESS_NAME, WHATSAPP)

    mapping = {}
    for p in products:
        mapping[p["name"]] = {
            "upc": p["upc"],
            "image_path": p.get("image_path", ""),
            "image_source": p.get("image_source", ""),
            "status": p.get("image_status", ""),
        }
    mapping_path = OUTPUT_DIR / "image_mapping.json"
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"  Image mapping: {mapping_path}")

    error_path = OUTPUT_DIR / "error_report.json"
    report = {
        "total_products": len(products),
        "images_found": sum(1 for p in products if p.get("image_status") == "found"),
        "images_missing": sum(1 for p in products if p.get("image_status") != "found"),
        "missing_products": errors,
    }
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  Error report: {error_path}")


def main():
    parser = argparse.ArgumentParser(description="Despensa Yosef Catalog Generator")
    parser.add_argument("--input", "-i", required=True, help="Path to Excel grocery file")
    parser.add_argument("--skip-images", action="store_true", help="Skip image search (for testing)")
    parser.add_argument("--skip-translate", action="store_true", help="Skip Hebrew translation")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    products = read_excel(args.input)
    products = calculate_prices(products)
    products, categories = categorize_products(products)

    if not args.skip_translate:
        products = translate_names(products)
    else:
        for p in products:
            p["hebrew_name"] = ""
        print("\n[4/6] Hebrew translation [SKIPPED]")

    products, errors = search_images(products, skip_images=args.skip_images)
    generate_outputs(products, categories, errors)

    print(f"\n{'='*60}")
    print(f"  CATALOG GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Products: {len(products)}")
    print(f"  Categories: {len(categories)}")
    print(f"  PDF: output/catalog.pdf")
    print(f"  Web: output/web/index.html")
    print(f"  Images: output/images/")
    print(f"  Mapping: output/image_mapping.json")
    print(f"  Errors: output/error_report.json")
    print(f"\n  Deploy to Netlify:")
    print(f"    cd output/web && npx netlify-cli deploy --prod --dir=.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
