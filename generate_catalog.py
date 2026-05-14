#!/usr/bin/env python3
"""Generate premium PDF catalog from Neon database with product images."""

import os
import sys
import tempfile
from pathlib import Path
from io import BytesIO
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from database import get_conn
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

DARK_GREEN = HexColor("#1B4332")
GREEN_MID = HexColor("#2D6A4F")
GREEN_LIGHT = HexColor("#40916C")
GOLD = HexColor("#D4AF37")
GOLD_LIGHT = HexColor("#F5E6A3")
BLACK = HexColor("#1A1A1A")
WHITE = HexColor("#FFFFFF")
OFF_WHITE = HexColor("#F8F8F8")
GRAY = HexColor("#666666")
GRAY_LIGHT = HexColor("#E0E0E0")

EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE", "18"))
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Despensa Yosef")
WHATSAPP = os.getenv("WHATSAPP_NUMBER", "")

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def get_products_with_images():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, hebrew_name, upc, brand, category, size,
               unit_cost, retail_price_usd, retail_price_mxn,
               image_data, (image_data IS NOT NULL) as has_image
        FROM products ORDER BY category, name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    for r in rows:
        r["unit_cost"] = float(r["unit_cost"]) if r["unit_cost"] else 0
        r["retail_price_usd"] = float(r["retail_price_usd"]) if r["retail_price_usd"] else 0
        r["retail_price_mxn"] = float(r["retail_price_mxn"]) if r["retail_price_mxn"] else 0
    return rows


def save_temp_image(image_data):
    if not image_data:
        return None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(bytes(image_data))
        tmp.close()
        return tmp.name
    except Exception:
        return None


class CatalogPDF:
    def __init__(self, output_path):
        self.output_path = output_path
        self.w, self.h = letter  # 612 x 792
        self.margin = 36
        self.page_count = 0
        self.temp_files = []

    def cleanup(self):
        for f in self.temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass

    def generate(self, products):
        by_cat = defaultdict(list)
        for p in products:
            by_cat[p["category"]].append(p)

        categories = sorted(by_cat.keys())
        c = canvas.Canvas(self.output_path, pagesize=letter)

        # Cover
        self._cover(c)
        c.showPage()

        # Table of Contents
        self._toc(c, categories, by_cat)
        c.showPage()

        # Product pages
        for cat in categories:
            prods = by_cat[cat]
            self._category_pages(c, cat, prods)

        # Back cover
        self._back_cover(c)
        c.showPage()

        c.save()
        self.cleanup()
        print(f"\nPDF saved: {self.output_path}")

    def _cover(self, c):
        # Full dark green background
        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.w, self.h, fill=1, stroke=0)

        # Gold border lines
        c.setFillColor(GOLD)
        c.rect(30, self.h - 50, self.w - 60, 2, fill=1, stroke=0)
        c.rect(30, 48, self.w - 60, 2, fill=1, stroke=0)
        # Corner accents
        for x in [30, self.w - 42]:
            for y in [48, self.h - 52]:
                c.rect(x, y, 12, 12, fill=0, stroke=1)
                c.setStrokeColor(GOLD)
                c.setLineWidth(1)

        # Star of David
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 40)
        c.drawCentredString(self.w / 2, self.h - 160, "✡")

        # Title
        y = self.h - 240
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 56)
        c.drawCentredString(self.w / 2, y, "DESPENSA")
        y -= 65
        c.drawCentredString(self.w / 2, y, "YOSEF")

        # Decorative line
        y -= 30
        c.setFillColor(GOLD)
        c.rect(self.w / 2 - 100, y, 200, 1.5, fill=1, stroke=0)

        # Subtitle
        y -= 40
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 18)
        c.drawCentredString(self.w / 2, y, "Premium Kosher Grocery Catalog")

        y -= 28
        c.setFont("Helvetica", 13)
        c.drawCentredString(self.w / 2, y, "Quality Products for Your Home")

        # Price info
        y -= 50
        c.setFillColor(GOLD_LIGHT)
        c.setFont("Helvetica", 11)
        c.drawCentredString(self.w / 2, y, f"All prices in MXN (USD x {int(EXCHANGE_RATE)})")

        # Bottom star
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 32)
        c.drawCentredString(self.w / 2, 120, "✡")

        # WhatsApp
        if WHATSAPP:
            c.setFillColor(WHITE)
            c.setFont("Helvetica", 11)
            c.drawCentredString(self.w / 2, 75, f"Orders: WhatsApp {WHATSAPP}")

    def _toc(self, c, categories, by_cat):
        c.setFillColor(WHITE)
        c.rect(0, 0, self.w, self.h, fill=1, stroke=0)

        # Header bar
        c.setFillColor(DARK_GREEN)
        c.rect(0, self.h - 80, self.w, 80, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(self.w / 2, self.h - 55, "CATALOG INDEX")

        # Categories list
        y = self.h - 130
        total_products = sum(len(by_cat[cat]) for cat in categories)
        total_images = sum(1 for cat in categories for p in by_cat[cat] if p.get("has_image"))

        c.setFillColor(DARK_GREEN)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, f"{total_products} Products  |  {len(categories)} Categories  |  {total_images} Product Photos")
        y -= 10
        c.setFillColor(GOLD)
        c.rect(60, y, self.w - 120, 1, fill=1, stroke=0)
        y -= 30

        for i, cat in enumerate(categories):
            cnt = len(by_cat[cat])
            img_cnt = sum(1 for p in by_cat[cat] if p.get("has_image"))

            c.setFillColor(DARK_GREEN)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(60, y, f"{i + 1}.")
            c.setFont("Helvetica", 14)
            c.drawString(90, y, cat)

            c.setFillColor(GRAY)
            c.setFont("Helvetica", 11)
            c.drawRightString(self.w - 60, y, f"{cnt} products")

            c.setFillColor(GOLD)
            c.rect(90, y - 6, self.w - 150, 0.5, fill=1, stroke=0)
            y -= 35

            if y < 80:
                break

        # Footer
        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.w, 30, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 8)
        c.drawCentredString(self.w / 2, 10, f"{BUSINESS_NAME}  |  Premium Kosher Grocery")

    def _category_pages(self, c, category, products):
        cols, rows = 3, 2
        per_page = cols * rows

        for start in range(0, len(products), per_page):
            page_prods = products[start:start + per_page]
            self._product_page(c, category, page_prods, cols, rows,
                               start + 1, min(start + per_page, len(products)), len(products))
            c.showPage()

    def _product_page(self, c, category, products, cols, rows, start_num, end_num, total):
        # White background
        c.setFillColor(WHITE)
        c.rect(0, 0, self.w, self.h, fill=1, stroke=0)

        # Header bar
        c.setFillColor(DARK_GREEN)
        c.rect(0, self.h - 50, self.w, 50, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(self.w / 2, self.h - 35, category.upper())
        c.setFont("Helvetica", 9)
        c.drawRightString(self.w - 20, self.h - 35, f"{start_num}-{end_num} of {total}")

        # Footer bar
        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.w, 28, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 7)
        c.drawCentredString(self.w / 2, 9, f"✡ {BUSINESS_NAME}  |  Premium Kosher Grocery  |  WhatsApp: {WHATSAPP} ✡")

        # Product grid
        usable_w = self.w - 2 * self.margin
        usable_h = self.h - 50 - 28 - 16
        card_w = usable_w / cols
        card_h = usable_h / rows
        top_y = self.h - 58

        for idx, product in enumerate(products):
            col = idx % cols
            row = idx // cols
            x = self.margin + col * card_w
            y = top_y - row * card_h
            self._product_card(c, product, x, y, card_w, card_h)

    def _product_card(self, c, product, x, y, w, h):
        pad = 5
        cx, cy = x + pad, y - h + pad
        cw, ch = w - 2 * pad, h - 2 * pad

        # Card background
        c.setFillColor(OFF_WHITE)
        c.roundRect(cx, cy, cw, ch, 5, fill=1, stroke=0)
        c.setStrokeColor(GRAY_LIGHT)
        c.setLineWidth(0.5)
        c.roundRect(cx, cy, cw, ch, 5, fill=0, stroke=1)

        # Product image
        img_size = min(cw - 16, ch * 0.42)
        img_x = cx + (cw - img_size) / 2
        img_y = cy + ch - img_size - 8

        img_drawn = False
        if product.get("image_data"):
            tmp_path = save_temp_image(product["image_data"])
            if tmp_path:
                self.temp_files.append(tmp_path)
                try:
                    c.drawImage(tmp_path, img_x, img_y, img_size, img_size,
                               preserveAspectRatio=True, anchor="c")
                    img_drawn = True
                except Exception:
                    pass

        if not img_drawn:
            c.setFillColor(HexColor("#EEEEEE"))
            c.roundRect(img_x, img_y, img_size, img_size, 4, fill=1, stroke=0)
            c.setFillColor(GRAY)
            c.setFont("Helvetica", 7)
            c.drawCentredString(img_x + img_size / 2, img_y + img_size / 2, "No Image")

        text_y = img_y - 6

        # Hebrew name
        hebrew = product.get("hebrew_name", "")
        if hebrew:
            c.setFillColor(DARK_GREEN)
            c.setFont("Helvetica-Bold", 7)
            display = hebrew[:35]
            c.drawCentredString(cx + cw / 2, text_y, display)
            text_y -= 10

        # English name
        name = product.get("name", "Unknown")
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 7)
        display_name = name[:38] + ("..." if len(name) > 38 else "")
        c.drawCentredString(cx + cw / 2, text_y, display_name)
        text_y -= 10

        # Size
        size = product.get("size", "")
        if size:
            c.setFillColor(GRAY)
            c.setFont("Helvetica", 6)
            c.drawCentredString(cx + cw / 2, text_y, str(size))
            text_y -= 10

        # Price badge — MXN
        price_mxn = product.get("retail_price_mxn", 0)
        price_usd = product.get("retail_price_usd", 0)
        if price_mxn:
            badge_w = 70
            badge_h = 18
            badge_x = cx + (cw - badge_w) / 2
            badge_y = text_y - 4

            # MXN price badge
            c.setFillColor(DARK_GREEN)
            c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=1, stroke=0)
            c.setFillColor(GOLD)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(cx + cw / 2, badge_y + 5, f"${price_mxn:.2f} MXN")

            # USD small text below
            if price_usd:
                c.setFillColor(GRAY)
                c.setFont("Helvetica", 5)
                c.drawCentredString(cx + cw / 2, badge_y - 8, f"(${price_usd:.2f} USD)")

    def _back_cover(self, c):
        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.w, self.h, fill=1, stroke=0)

        # Gold borders
        c.setFillColor(GOLD)
        c.rect(30, self.h - 50, self.w - 60, 2, fill=1, stroke=0)
        c.rect(30, 48, self.w - 60, 2, fill=1, stroke=0)

        y = self.h / 2 + 80
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 32)
        c.drawCentredString(self.w / 2, y, "✡")

        y -= 60
        c.setFont("Helvetica-Bold", 38)
        c.drawCentredString(self.w / 2, y, BUSINESS_NAME.upper())

        y -= 30
        c.rect(self.w / 2 - 80, y, 160, 1.5, fill=1, stroke=0)

        y -= 40
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 16)
        c.drawCentredString(self.w / 2, y, "Thank You for Choosing Us")

        y -= 30
        c.setFont("Helvetica", 13)
        c.drawCentredString(self.w / 2, y, "Quality Kosher Products, Always Fresh")

        y -= 25
        c.setFont("Helvetica", 13)
        c.drawCentredString(self.w / 2, y, "Productos Kosher de Calidad, Siempre Frescos")

        if WHATSAPP:
            y -= 50
            # Green WhatsApp-style button
            btn_w = 260
            btn_h = 36
            btn_x = (self.w - btn_w) / 2
            c.setFillColor(HexColor("#25D366"))
            c.roundRect(btn_x, y - 5, btn_w, btn_h, 18, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(self.w / 2, y + 5, f"WhatsApp: {WHATSAPP}")

        c.setFillColor(GOLD)
        c.setFont("Helvetica", 28)
        c.drawCentredString(self.w / 2, 90, "✡")


def main():
    print("Loading products from database...")
    products = get_products_with_images()
    total = len(products)
    with_images = sum(1 for p in products if p.get("has_image"))
    print(f"  {total} products loaded, {with_images} with images")

    output_path = str(OUTPUT_DIR / "Despensa_Yosef_Catalog.pdf")
    print(f"\nGenerating PDF catalog...")
    pdf = CatalogPDF(output_path)
    pdf.generate(products)
    print(f"  File size: {os.path.getsize(output_path) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
