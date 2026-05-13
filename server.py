#!/usr/bin/env python3
"""Despensa Yosef - Dynamic Catalog Platform"""

import io
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv

from database import (
    init_db, get_all_products, get_product_image, upsert_product,
    update_product_price, delete_product, get_categories, get_stats,
    create_order, get_orders, update_order_status,
    save_invoice, get_invoices, delete_invoice, get_invoice_file,
    get_inventory, update_inventory, get_financial_summary
)
from category_detector import detect_category
from translator import translate_to_hebrew
from image_search import search_product_image

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__,
            static_folder=str(BASE_DIR / "static"),
            template_folder=str(BASE_DIR / "templates"))
CORS(app)

MARKUP = float(os.getenv("MARKUP_PERCENT", "37"))
EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE", "18"))
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Despensa Yosef")
WHATSAPP = os.getenv("WHATSAPP_NUMBER", "")


@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR / "templates"), "index.html")


@app.route("/api/products")
def api_products():
    products = get_all_products()
    for p in products:
        p["created_at"] = str(p["created_at"]) if p.get("created_at") else ""
        p["updated_at"] = str(p["updated_at"]) if p.get("updated_at") else ""
        p["case_price"] = float(p["case_price"]) if p["case_price"] else 0
        p["unit_cost"] = float(p["unit_cost"]) if p["unit_cost"] else 0
        p["retail_price_usd"] = float(p["retail_price_usd"]) if p["retail_price_usd"] else 0
        p["retail_price_mxn"] = float(p["retail_price_mxn"]) if p["retail_price_mxn"] else 0
    return jsonify(products)


@app.route("/api/products/<int:pid>", methods=["PUT"])
def api_update_product(pid):
    data = request.json
    if "retail_price_usd" in data:
        price = float(data["retail_price_usd"])
        update_product_price(pid, price)
        return jsonify({"ok": True, "retail_price_usd": price,
                        "retail_price_mxn": round(price * EXCHANGE_RATE, 2)})
    return jsonify({"error": "No price provided"}), 400


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def api_delete_product(pid):
    delete_product(pid)
    return jsonify({"ok": True})


@app.route("/api/images/<int:pid>")
def api_image(pid):
    data = get_product_image(pid)
    if data:
        return Response(data, mimetype="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    return Response(status=404)


@app.route("/api/categories")
def api_categories():
    return jsonify(get_categories())


@app.route("/api/stats")
def api_stats():
    stats = get_stats()
    stats["exchange_rate"] = EXCHANGE_RATE
    stats["business_name"] = BUSINESS_NAME
    stats["whatsapp"] = WHATSAPP
    return jsonify(stats)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        return jsonify({"error": "Only Excel/CSV files accepted"}), 400

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file.read()))
        else:
            df = pd.read_excel(io.BytesIO(file.read()))
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {str(e)}"}), 400

    col_map = _detect_columns(df)
    added = 0
    errors = []

    for _, row in df.iterrows():
        try:
            product = _parse_row(row, col_map)
            if not product:
                continue

            hebrew = translate_to_hebrew([product["name"]])
            product["hebrew_name"] = hebrew.get(product["name"], "")

            img_result = search_product_image(product["name"], product.get("upc", ""))
            if img_result.get("status") == "found" and img_result.get("local_path"):
                img_path = img_result["local_path"]
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        product["image_data"] = f.read()
                    product["image_source"] = img_result.get("source_url", "")

            upsert_product(product)
            added += 1
        except Exception as e:
            errors.append({"row": str(row.get(col_map.get("name", ""), "?")), "error": str(e)})

    return jsonify({"added": added, "errors": errors, "total_rows": len(df)})


# ── Orders ──

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data = request.json
    if not data.get("customer_name") or not data.get("phone"):
        return jsonify({"error": "Name and phone required"}), 400
    if not data.get("items"):
        return jsonify({"error": "Cart is empty"}), 400

    items = []
    total_usd = 0
    total_mxn = 0
    for item in data["items"]:
        price_usd = float(item["price_usd"])
        price_mxn = float(item["price_mxn"])
        qty = int(item["quantity"])
        items.append({
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "quantity": qty,
            "price_usd": price_usd,
            "price_mxn": price_mxn,
        })
        total_usd += price_usd * qty
        total_mxn += price_mxn * qty

    order_data = {
        "customer_name": data["customer_name"],
        "phone": data["phone"],
        "address": data.get("address", ""),
        "notes": data.get("notes", ""),
        "payment_method": data.get("payment_method", "pay_on_delivery"),
        "total_usd": round(total_usd, 2),
        "total_mxn": round(total_mxn, 2),
    }
    order_id = create_order(order_data, items)
    return jsonify({"ok": True, "order_id": order_id,
                    "total_usd": order_data["total_usd"],
                    "total_mxn": order_data["total_mxn"]})


@app.route("/api/orders")
def api_get_orders():
    status = request.args.get("status")
    return jsonify(get_orders(status))


@app.route("/api/orders/<int:oid>", methods=["PUT"])
def api_update_order(oid):
    data = request.json
    if "status" in data:
        update_order_status(oid, data["status"])
        return jsonify({"ok": True})
    return jsonify({"error": "No status provided"}), 400


# ── Invoices ──

@app.route("/api/invoices", methods=["POST"])
def api_upload_invoice():
    vendor = request.form.get("vendor", "")
    if not vendor:
        return jsonify({"error": "Vendor name required"}), 400

    file_data = None
    file_name = ""
    if "file" in request.files:
        f = request.files["file"]
        file_data = f.read()
        file_name = f.filename

    inv_data = {
        "vendor": vendor,
        "invoice_number": request.form.get("invoice_number", ""),
        "invoice_date": request.form.get("invoice_date") or None,
        "total_amount": float(request.form.get("total_amount", 0)),
        "currency": request.form.get("currency", "USD"),
        "notes": request.form.get("notes", ""),
    }
    inv_id = save_invoice(inv_data, file_data, file_name)
    return jsonify({"ok": True, "id": inv_id})


@app.route("/api/invoices")
def api_get_invoices():
    return jsonify(get_invoices())


@app.route("/api/invoices/<int:iid>", methods=["DELETE"])
def api_delete_invoice(iid):
    delete_invoice(iid)
    return jsonify({"ok": True})


@app.route("/api/invoices/<int:iid>/file")
def api_invoice_file(iid):
    data, name = get_invoice_file(iid)
    if data:
        mime = "application/pdf" if name.endswith(".pdf") else "application/octet-stream"
        return Response(data, mimetype=mime,
                        headers={"Content-Disposition": f'inline; filename="{name}"'})
    return Response(status=404)


# ── Inventory ──

@app.route("/api/inventory")
def api_inventory():
    return jsonify(get_inventory())


@app.route("/api/inventory/<int:pid>", methods=["PUT"])
def api_update_inventory(pid):
    data = request.json
    update_inventory(pid, int(data.get("qty_on_hand", 0)),
                     int(data.get("reorder_point", 5)))
    return jsonify({"ok": True})


# ── Financial ──

@app.route("/api/financial")
def api_financial():
    return jsonify(get_financial_summary())


def _detect_columns(df):
    col_map = {}
    for col in df.columns:
        cl = col.lower().strip()
        if cl.startswith("unnamed"):
            continue
        if ("item" in cl or "description" in cl or "product" in cl) and "name" not in col_map:
            col_map["name"] = col
        elif ("upc" in cl or "barcode" in cl) and "upc" not in col_map:
            col_map["upc"] = col
        elif ("price" in cl and "unit" not in cl) and "price" not in col_map:
            col_map["price"] = col
        elif ("size" in cl or "weight" in cl) and "size" not in col_map:
            col_map["size"] = col
        elif ("pack" in cl or "qty" in cl) and "pack" not in col_map:
            col_map["pack"] = col
        elif "brand" in cl and "brand" not in col_map:
            col_map["brand"] = col
    if "name" not in col_map:
        col_map["name"] = df.columns[0]
    return col_map


def _parse_row(row, col_map):
    name = str(row.get(col_map.get("name", ""), "")).strip()
    if not name or name == "nan":
        return None

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
    if pd.notna(brand_raw) and str(brand_raw).strip() not in ("", "nan"):
        brand = str(brand_raw).strip()
    else:
        brand = name.split()[0] if name else ""

    category = detect_category(name)
    unit_cost = round(price / pack, 2) if pack else 0
    retail_usd = math.ceil(unit_cost * (1 + MARKUP / 100) * 100) / 100
    retail_mxn = round(retail_usd * EXCHANGE_RATE, 2)

    return {
        "name": name, "upc": upc, "brand": brand, "category": category,
        "size": size, "case_price": price, "pack_qty": int(pack),
        "unit_cost": unit_cost, "retail_price_usd": retail_usd,
        "retail_price_mxn": retail_mxn,
    }


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
