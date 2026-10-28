import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("novamart.db")

def get_connection():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        description TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_runs (
        id TEXT PRIMARY KEY,
        customer_name TEXT NOT NULL,
        user_message TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        status TEXT NOT NULL,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        latency_ms REAL DEFAULT 0.0,
        reply_text TEXT,
        approval_type TEXT,
        approval_amount REAL,
        synapse_reported INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        step_number INTEGER NOT NULL,
        action TEXT NOT NULL,
        detail TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES agent_runs(id)
    );
    """)

    conn.commit()
    seed_products(conn)
    conn.close()

def seed_products(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM products")
    if cursor.fetchone()["cnt"] == 0:
        products = [
            ("NovaBook Pro 16", "Laptops", 1299.99, 15, "16-inch M-Series powerhouse with 32GB RAM & 1TB SSD"),
            ("NovaPhone 15 Ultra", "Smartphones", 999.00, 24, "Flagship smartphone with 200MP camera and OLED display"),
            ("NovaSound ANC Wireless Headphones", "Audio", 199.50, 45, "Active Noise Cancelling over-ear headphones with 40h battery"),
            ("NovaTab Pro 11", "Tablets", 499.00, 18, "Ultra-thin 120Hz display tablet with stylus support"),
            ("NovaCharge 100W Fast Adapter", "Accessories", 49.99, 90, "GaN fast charger with 3 USB-C and 1 USB-A ports")
        ]
        cursor.executemany("""
            INSERT INTO products (name, category, price, stock, description)
            VALUES (?, ?, ?, ?, ?)
        """, products)
        conn.commit()
        logger.info("Database seeded with electronics products.")

def get_all_products() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def find_product_by_query(query: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()

    query_lower = query.lower()
    # Check for direct or keyword matches
    for p in products:
        p_name = p["name"].lower()
        p_cat = p["category"].lower()
        if p_name in query_lower or query_lower in p_name:
            return dict(p)
        if "laptop" in query_lower and "laptop" in p_cat:
            return dict(p)
        if ("phone" in query_lower or "mobile" in query_lower) and "smartphones" in p_cat:
            return dict(p)
        if ("headphone" in query_lower or "audio" in query_lower) and "audio" in p_cat:
            return dict(p)
        if "tablet" in query_lower and "tablets" in p_cat:
            return dict(p)
        if "charger" in query_lower and "accessories" in p_cat:
            return dict(p)
    return None

def create_order(customer_name: str, product_name: str, quantity: int, unit_price: float, total_price: float) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO orders (customer_name, product_name, quantity, unit_price, total_price, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'CONFIRMED', ?)
    """, (customer_name, product_name, quantity, unit_price, total_price, now))
    order_id = cursor.lastrowid
    # Decrement stock
    cursor.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE name = ?", (quantity, product_name))
    conn.commit()
    conn.close()
    return order_id

def save_agent_run(
    run_id: str,
    customer_name: str,
    user_message: str,
    agent_name: str,
    status: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    reply_text: str,
    approval_type: Optional[str] = None,
    approval_amount: Optional[float] = None,
    synapse_reported: bool = False
):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO agent_runs (
            id, customer_name, user_message, agent_name, status,
            input_tokens, output_tokens, cost_usd, latency_ms,
            reply_text, approval_type, approval_amount, synapse_reported, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id, customer_name, user_message, agent_name, status,
        input_tokens, output_tokens, cost_usd, latency_ms,
        reply_text, approval_type, approval_amount, 1 if synapse_reported else 0, now
    ))
    conn.commit()
    conn.close()

def save_agent_step(run_id: str, agent_name: str, step_number: int, action: str, detail: str):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO agent_steps (run_id, agent_name, step_number, action, detail, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (run_id, agent_name, step_number, action, detail, now))
    conn.commit()
    conn.close()

def get_run_details(run_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    run = dict(row)
    cursor.execute("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_number ASC", (run_id,))
    steps = [dict(s) for s in cursor.fetchall()]
    conn.close()
    run["steps"] = steps
    return run

def get_recent_runs(limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    runs = []
    for r in rows:
        run_dict = dict(r)
        cursor.execute("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_number ASC", (run_dict["id"],))
        run_dict["steps"] = [dict(s) for s in cursor.fetchall()]
        runs.append(run_dict)
    conn.close()
    return runs
