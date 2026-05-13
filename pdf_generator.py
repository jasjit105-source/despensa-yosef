import os
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, PageBreak, Frame, PageTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import config

DARK_GREEN = HexColor(config.DARK_GREEN)
GOLD = HexColor(config.GOLD)
BLACK = HexColor(config.BLACK)
WHITE = HexColor(config.WHITE)
LIGHT_GREEN = HexColor(config.LIGHT_GREEN)
MEDIUM_GREEN = HexColor(config.MEDIUM_GREEN)
OFF_WHITE = HexColor("#F8F8F8")


class CatalogPDF:
    def __init__(self, output_path: str, business_name: str = "Despensa Yosef",
                 whatsapp: str = ""):
        self.output_path = output_path
        self.business_name = business_name
        self.whatsapp = whatsapp
        self.width, self.height = letter
        self.margin = 36
        self.page_num = 0

    def generate(self, products_by_category: dict):
        c = canvas.Canvas(self.output_path, pagesize=letter)
        self._draw_cover(c)
        c.showPage()

        self._draw_toc(c, list(products_by_category.keys()))
        c.showPage()

        for category, products in products_by_category.items():
            self._draw_category_pages(c, category, products)

        self._draw_back_cover(c)
        c.showPage()
        c.save()
        print(f"  PDF saved: {self.output_path}")

    def _draw_cover(self, c):
        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        c.setFillColor(GOLD)
        c.rect(40, self.height - 60, self.width - 80, 3, fill=1, stroke=0)
        c.rect(40, 57, self.width - 80, 3, fill=1, stroke=0)

        y = self.height - 200
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 52)
        c.drawCentredString(self.width / 2, y, "DESPENSA")
        y -= 60
        c.setFont("Helvetica-Bold", 52)
        c.drawCentredString(self.width / 2, y, "YOSEF")

        y -= 40
        c.setFillColor(GOLD)
        c.rect(self.width / 2 - 80, y, 160, 2, fill=1, stroke=0)

        y -= 50
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 16)
        c.drawCentredString(self.width / 2, y, "Premium Kosher Grocery Catalog")

        y -= 30
        c.setFont("Helvetica", 12)
        c.drawCentredString(self.width / 2, y, "Quality Products for Your Home")

        star_y = 180
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 28)
        c.drawCentredString(self.width / 2, star_y, "✡")

        if self.whatsapp:
            c.setFillColor(WHITE)
            c.setFont("Helvetica", 11)
            c.drawCentredString(self.width / 2, 80, f"WhatsApp: {self.whatsapp}")

    def _draw_toc(self, c, categories: list):
        c.setFillColor(WHITE)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        c.setFillColor(DARK_GREEN)
        c.rect(0, self.height - 80, self.width, 80, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(self.width / 2, self.height - 55, "CATALOG INDEX")

        y = self.height - 130
        c.setFillColor(DARK_GREEN)
        c.setFont("Helvetica-Bold", 14)

        for i, cat in enumerate(categories):
            if y < 80:
                break
            c.setFillColor(BLACK)
            c.setFont("Helvetica", 13)
            c.drawString(60, y, f"{i + 1}.")
            c.drawString(90, y, cat)

            c.setFillColor(GOLD)
            c.rect(90, y - 4, self.width - 180, 0.5, fill=1, stroke=0)
            y -= 32

    def _draw_category_pages(self, c, category: str, products: list):
        cols = 3
        rows = 2
        per_page = cols * rows

        for page_start in range(0, len(products), per_page):
            page_products = products[page_start:page_start + per_page]
            self._draw_product_page(c, category, page_products, cols, rows)
            c.showPage()

    def _draw_product_page(self, c, category: str, products: list, cols: int, rows: int):
        c.setFillColor(WHITE)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        c.setFillColor(DARK_GREEN)
        c.rect(0, self.height - 50, self.width, 50, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(self.width / 2, self.height - 35, category.upper())

        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.width, 30, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica", 8)
        c.drawCentredString(self.width / 2, 10, f"{self.business_name}  |  Premium Kosher Grocery")

        usable_w = self.width - 2 * self.margin
        usable_h = self.height - 50 - 30 - 20
        card_w = usable_w / cols
        card_h = usable_h / rows
        top_y = self.height - 60

        for idx, product in enumerate(products):
            col = idx % cols
            row = idx // cols
            x = self.margin + col * card_w
            y = top_y - row * card_h

            self._draw_product_card(c, product, x, y, card_w, card_h)

    def _draw_product_card(self, c, product: dict, x: float, y: float,
                           w: float, h: float):
        pad = 6
        cx = x + pad
        cy = y - h + pad
        cw = w - 2 * pad
        ch = h - 2 * pad

        c.setFillColor(OFF_WHITE)
        c.roundRect(cx, cy, cw, ch, 6, fill=1, stroke=0)

        c.setStrokeColor(HexColor("#E0E0E0"))
        c.setLineWidth(0.5)
        c.roundRect(cx, cy, cw, ch, 6, fill=0, stroke=1)

        img_path = product.get("image_path", "")
        img_size = min(cw - 20, ch * 0.45)
        img_x = cx + (cw - img_size) / 2
        img_y = cy + ch - img_size - 10

        if img_path and os.path.exists(img_path):
            try:
                c.drawImage(img_path, img_x, img_y, img_size, img_size,
                           preserveAspectRatio=True, anchor="c")
            except Exception:
                self._draw_placeholder(c, img_x, img_y, img_size)
        else:
            self._draw_placeholder(c, img_x, img_y, img_size)

        text_y = img_y - 8

        hebrew_name = product.get("hebrew_name", "")
        if hebrew_name:
            c.setFillColor(DARK_GREEN)
            c.setFont("Helvetica-Bold", 8)
            display_hebrew = hebrew_name[:30]
            c.drawCentredString(cx + cw / 2, text_y, display_hebrew)
            text_y -= 12

        name = product.get("name", "Unknown")
        c.setFillColor(BLACK)
        c.setFont("Helvetica-Bold", 7)
        display_name = name[:35] + ("..." if len(name) > 35 else "")
        c.drawCentredString(cx + cw / 2, text_y, display_name)
        text_y -= 11

        size = product.get("size", "")
        if size:
            c.setFillColor(HexColor("#666666"))
            c.setFont("Helvetica", 6)
            c.drawCentredString(cx + cw / 2, text_y, str(size))
            text_y -= 10

        price = product.get("retail_price", 0)
        if price:
            badge_w = 50
            badge_h = 16
            badge_x = cx + (cw - badge_w) / 2
            badge_y = text_y - 4
            c.setFillColor(DARK_GREEN)
            c.roundRect(badge_x, badge_y, badge_w, badge_h, 3, fill=1, stroke=0)
            c.setFillColor(GOLD)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(cx + cw / 2, badge_y + 4, f"${price:.2f}")

    def _draw_placeholder(self, c, x, y, size):
        c.setFillColor(HexColor("#E8E8E8"))
        c.roundRect(x, y, size, size, 4, fill=1, stroke=0)
        c.setFillColor(HexColor("#CCCCCC"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + size / 2, y + size / 2, "No Image")

    def _draw_back_cover(self, c):
        c.setFillColor(DARK_GREEN)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        y = self.height / 2 + 60
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(self.width / 2, y, self.business_name.upper())

        y -= 40
        c.rect(self.width / 2 - 60, y, 120, 2, fill=1, stroke=0)

        y -= 40
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 14)
        c.drawCentredString(self.width / 2, y, "Thank You for Choosing Us")

        y -= 30
        c.setFont("Helvetica", 12)
        c.drawCentredString(self.width / 2, y, "Quality Kosher Products, Always Fresh")

        if self.whatsapp:
            y -= 50
            c.setFillColor(GOLD)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(self.width / 2, y, f"Order on WhatsApp: {self.whatsapp}")

        c.setFillColor(GOLD)
        c.setFont("Helvetica", 28)
        c.drawCentredString(self.width / 2, 100, "✡")
