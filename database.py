import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE", "18"))


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            hebrew_name VARCHAR(255) DEFAULT '',
            spanish_name VARCHAR(255) DEFAULT '',
            upc VARCHAR(30) DEFAULT '',
            brand VARCHAR(100) DEFAULT '',
            category VARCHAR(100) DEFAULT 'General Grocery',
            size VARCHAR(50) DEFAULT '',
            case_price DECIMAL(10,2) DEFAULT 0,
            pack_qty INTEGER DEFAULT 1,
            unit_cost DECIMAL(10,2) DEFAULT 0,
            retail_price_usd DECIMAL(10,2) DEFAULT 0,
            retail_price_mxn DECIMAL(10,2) DEFAULT 0,
            image_data BYTEA,
            image_source VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_upc ON products(upc)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            address TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            payment_method VARCHAR(30) DEFAULT 'pay_on_delivery',
            total_usd DECIMAL(10,2) DEFAULT 0,
            total_mxn DECIMAL(10,2) DEFAULT 0,
            status VARCHAR(30) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name VARCHAR(255) NOT NULL,
            quantity INTEGER DEFAULT 1,
            price_usd DECIMAL(10,2) DEFAULT 0,
            price_mxn DECIMAL(10,2) DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            vendor VARCHAR(255) NOT NULL,
            invoice_number VARCHAR(100) DEFAULT '',
            invoice_date DATE,
            total_amount DECIMAL(12,2) DEFAULT 0,
            currency VARCHAR(10) DEFAULT 'USD',
            notes TEXT DEFAULT '',
            file_data BYTEA,
            file_name VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE UNIQUE,
            qty_on_hand INTEGER DEFAULT 0,
            qty_sold INTEGER DEFAULT 0,
            reorder_point INTEGER DEFAULT 5,
            last_restocked TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized")


def get_all_products():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, hebrew_name, spanish_name, upc, brand, category,
               size, case_price, pack_qty, unit_cost,
               retail_price_usd, retail_price_mxn,
               image_source, (image_data IS NOT NULL) as has_image,
               created_at, updated_at
        FROM products ORDER BY category, name
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_product_image(product_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT image_data FROM products WHERE id = %s", (product_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row["image_data"]:
        return bytes(row["image_data"])
    return None


def upsert_product(data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM products WHERE upc = %s AND upc != ''", (data.get("upc", ""),))
    existing = cur.fetchone()

    if existing:
        pid = existing["id"]
        cur.execute("""
            UPDATE products SET name=%s, hebrew_name=%s, spanish_name=%s, brand=%s,
                category=%s, size=%s, case_price=%s, pack_qty=%s, unit_cost=%s,
                retail_price_usd=%s, retail_price_mxn=%s, image_source=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            data["name"], data.get("hebrew_name", ""), data.get("spanish_name", ""),
            data.get("brand", ""), data.get("category", "General Grocery"),
            data.get("size", ""), data.get("case_price", 0), data.get("pack_qty", 1),
            data.get("unit_cost", 0), data.get("retail_price_usd", 0),
            data.get("retail_price_mxn", 0), data.get("image_source", ""),
            pid
        ))
        if data.get("image_data"):
            cur.execute("UPDATE products SET image_data=%s WHERE id=%s",
                        (psycopg2.Binary(data["image_data"]), pid))
        conn.commit()
        cur.close()
        conn.close()
        return pid

    cur.execute("""
        INSERT INTO products (name, hebrew_name, spanish_name, upc, brand, category,
            size, case_price, pack_qty, unit_cost, retail_price_usd, retail_price_mxn,
            image_data, image_source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        data["name"], data.get("hebrew_name", ""), data.get("spanish_name", ""),
        data.get("upc", ""), data.get("brand", ""), data.get("category", "General Grocery"),
        data.get("size", ""), data.get("case_price", 0), data.get("pack_qty", 1),
        data.get("unit_cost", 0), data.get("retail_price_usd", 0),
        data.get("retail_price_mxn", 0),
        psycopg2.Binary(data["image_data"]) if data.get("image_data") else None,
        data.get("image_source", ""),
    ))
    pid = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return pid


def update_product_price(product_id, retail_price_usd):
    retail_price_mxn = round(retail_price_usd * EXCHANGE_RATE, 2)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE products SET retail_price_usd=%s, retail_price_mxn=%s,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=%s
    """, (retail_price_usd, retail_price_mxn, product_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_product(product_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_categories():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT category, COUNT(*) as count
        FROM products GROUP BY category ORDER BY category
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT category) as categories,
               COUNT(DISTINCT brand) as brands,
               COUNT(CASE WHEN image_data IS NOT NULL THEN 1 END) as with_images
        FROM products
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row)


# ── Orders ──

def create_order(data, items):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (customer_name, phone, address, notes,
            payment_method, total_usd, total_mxn, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (
        data["customer_name"], data["phone"], data.get("address", ""),
        data.get("notes", ""), data.get("payment_method", "pay_on_delivery"),
        data["total_usd"], data["total_mxn"], "pending"
    ))
    order_id = cur.fetchone()["id"]
    for item in items:
        cur.execute("""
            INSERT INTO order_items (order_id, product_id, product_name,
                quantity, price_usd, price_mxn)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (order_id, item["product_id"], item["product_name"],
              item["quantity"], item["price_usd"], item["price_mxn"]))
    conn.commit()
    cur.close()
    conn.close()
    return order_id


def get_orders(status=None):
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT * FROM orders WHERE status=%s ORDER BY created_at DESC", (status,))
    else:
        cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = [dict(r) for r in cur.fetchall()]
    for o in orders:
        cur.execute("SELECT * FROM order_items WHERE order_id=%s", (o["id"],))
        o["items"] = [dict(r) for r in cur.fetchall()]
        o["created_at"] = str(o["created_at"])
        o["total_usd"] = float(o["total_usd"])
        o["total_mxn"] = float(o["total_mxn"])
        for it in o["items"]:
            it["price_usd"] = float(it["price_usd"])
            it["price_mxn"] = float(it["price_mxn"])
    cur.close()
    conn.close()
    return orders


def update_order_status(order_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
    conn.commit()
    cur.close()
    conn.close()


# ── Invoices ──

def save_invoice(data, file_data=None, file_name=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO invoices (vendor, invoice_number, invoice_date,
            total_amount, currency, notes, file_data, file_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (
        data["vendor"], data.get("invoice_number", ""),
        data.get("invoice_date"), data.get("total_amount", 0),
        data.get("currency", "USD"), data.get("notes", ""),
        psycopg2.Binary(file_data) if file_data else None, file_name
    ))
    inv_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return inv_id


def get_invoices():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, vendor, invoice_number, invoice_date, total_amount,
               currency, notes, file_name, created_at
        FROM invoices ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["total_amount"] = float(r["total_amount"])
        r["invoice_date"] = str(r["invoice_date"]) if r["invoice_date"] else ""
        r["created_at"] = str(r["created_at"])
    cur.close()
    conn.close()
    return rows


def delete_invoice(inv_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM invoices WHERE id=%s", (inv_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_invoice_file(inv_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT file_data, file_name FROM invoices WHERE id=%s", (inv_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row["file_data"]:
        return bytes(row["file_data"]), row["file_name"]
    return None, None


# ── Inventory ──

def get_inventory():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id as product_id, p.name, p.category, p.unit_cost,
               p.retail_price_usd, p.retail_price_mxn,
               COALESCE(i.qty_on_hand, 0) as qty_on_hand,
               COALESCE(i.qty_sold, 0) as qty_sold,
               COALESCE(i.reorder_point, 5) as reorder_point
        FROM products p
        LEFT JOIN inventory i ON i.product_id = p.id
        ORDER BY p.category, p.name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["unit_cost"] = float(r["unit_cost"])
        r["retail_price_usd"] = float(r["retail_price_usd"])
        r["retail_price_mxn"] = float(r["retail_price_mxn"])
    cur.close()
    conn.close()
    return rows


def update_inventory(product_id, qty_on_hand, reorder_point=5):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO inventory (product_id, qty_on_hand, reorder_point, last_restocked)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (product_id) DO UPDATE SET
            qty_on_hand = EXCLUDED.qty_on_hand,
            reorder_point = EXCLUDED.reorder_point,
            last_restocked = CURRENT_TIMESTAMP
    """, (product_id, qty_on_hand, reorder_point))
    conn.commit()
    cur.close()
    conn.close()


# ── Financial Summary ──

def get_financial_summary():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total_usd), 0) as revenue_usd,
               COALESCE(SUM(total_mxn), 0) as revenue_mxn,
               COUNT(*) as total_orders
        FROM orders WHERE status != 'cancelled'
    """)
    rev = dict(cur.fetchone())
    rev["revenue_usd"] = float(rev["revenue_usd"])
    rev["revenue_mxn"] = float(rev["revenue_mxn"])

    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0) as total_costs
        FROM invoices
    """)
    costs = dict(cur.fetchone())
    costs["total_costs"] = float(costs["total_costs"])

    cur.execute("""
        SELECT COALESCE(SUM(i.qty_on_hand * p.unit_cost), 0) as inventory_value_usd
        FROM inventory i JOIN products p ON p.id = i.product_id
    """)
    inv = dict(cur.fetchone())
    inv["inventory_value_usd"] = float(inv["inventory_value_usd"])

    cur.execute("SELECT COUNT(*) as pending FROM orders WHERE status='pending'")
    pending = cur.fetchone()["pending"]

    cur.close()
    conn.close()
    return {
        "revenue_usd": rev["revenue_usd"],
        "revenue_mxn": rev["revenue_mxn"],
        "total_orders": rev["total_orders"],
        "total_costs": costs["total_costs"],
        "profit_usd": rev["revenue_usd"] - costs["total_costs"],
        "inventory_value_usd": inv["inventory_value_usd"],
        "pending_orders": pending,
    }
