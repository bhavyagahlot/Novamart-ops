import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("novamart.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    );
    """)

    # Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """)

    # Refunds Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        customer_name TEXT NOT NULL,
        amount REAL NOT NULL,
        reason TEXT,
        status TEXT NOT NULL,
        requires_approval INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Agent Runs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_runs (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        status TEXT NOT NULL,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        latency_ms REAL DEFAULT 0.0,
        steps_json TEXT,
        output_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed products if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        seed_products = [
            ("NovaBook Pro 16", "laptop", 1299.99, 10),
            ("NovaBook Air 13", "laptop", 899.99, 15),
            ("NovaPhone Ultra", "phone", 799.99, 20),
            ("NovaSound ANC Headphones", "headphones", 149.99, 35),
            ("NovaWatch Active", "smartwatch", 199.99, 12),
            ("NovaCharge 100W GaN", "accessory", 49.99, 50)
        ]
        cursor.executemany(
            "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
            seed_products
        )
        logger.info("Seeded initial product catalog into SQLite.")

    # Seed initial sample orders if empty
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        sample_orders = [
            (1001, "Alex Rivera", 1, "NovaBook Pro 16", 1, 1299.99, 1299.99, "DELIVERED"),
            (1002, "Sam Chen", 4, "NovaSound ANC Headphones", 1, 149.99, 149.99, "DELIVERED"),
            (1003, "Taylor Swift", 6, "NovaCharge 100W GaN", 1, 49.99, 49.99, "DELIVERED")
        ]
        cursor.executemany(
            "INSERT INTO orders (id, customer_name, product_id, product_name, quantity, unit_price, total_amount, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_orders
        )
        logger.info("Seeded sample order records.")

    conn.commit()
    conn.close()

def record_agent_run(
    run_id: str,
    conversation_id: str,
    agent_name: str,
    status: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    steps: List[Dict[str, Any]],
    output_text: str
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO agent_runs 
    (id, conversation_id, agent_name, status, input_tokens, output_tokens, cost_usd, latency_ms, steps_json, output_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id,
        conversation_id,
        agent_name,
        status,
        input_tokens,
        output_tokens,
        cost_usd,
        latency_ms,
        json.dumps(steps),
        output_text
    ))
    conn.commit()
    conn.close()

def get_agent_runs_by_conversation(conversation_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM agent_runs WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    runs = []
    for r in rows:
        runs.append({
            "id": r["id"],
            "conversation_id": r["conversation_id"],
            "agent_name": r["agent_name"],
            "status": r["status"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cost_usd": r["cost_usd"],
            "latency_ms": r["latency_ms"],
            "steps": json.loads(r["steps_json"]) if r["steps_json"] else [],
            "output_text": r["output_text"],
            "created_at": r["created_at"]
        })
    return runs

def get_products() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def find_product_by_query(query: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    # Normalize query
    q = f"%{query.strip().lower()}%"
    cursor.execute("SELECT * FROM products WHERE LOWER(name) LIKE ? OR LOWER(category) LIKE ? LIMIT 1", (q, q))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_order(customer_name: str, product_id: int, quantity: int = 1) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        raise ValueError(f"Product with ID {product_id} not found.")

    if product["stock"] < quantity:
        conn.close()
        raise ValueError(f"Insufficient stock for {product['name']}. Available: {product['stock']}")

    # Decrement stock
    cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
    
    total = product["price"] * quantity
    cursor.execute("""
    INSERT INTO orders (customer_name, product_id, product_name, quantity, unit_price, total_amount, status)
    VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED')
    """, (customer_name, product_id, product["name"], quantity, product["price"], total))
    order_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return {
        "order_id": order_id,
        "customer_name": customer_name,
        "product_name": product["name"],
        "quantity": quantity,
        "unit_price": product["price"],
        "total_amount": total,
        "status": "CONFIRMED"
    }

def create_refund(customer_name: str, amount: float, reason: str, order_id: Optional[int] = None, requires_approval: bool = False) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    status = "WAITING_APPROVAL" if requires_approval else "COMPLETED"
    cursor.execute("""
    INSERT INTO refunds (order_id, customer_name, amount, reason, status, requires_approval)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, customer_name, amount, reason, status, 1 if requires_approval else 0))
    refund_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "refund_id": refund_id,
        "order_id": order_id,
        "customer_name": customer_name,
        "amount": amount,
        "reason": reason,
        "status": status,
        "requires_approval": requires_approval
    }

def find_order(order_id: Optional[int] = None, customer_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if order_id:
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
    elif customer_name:
        q = f"%{customer_name.strip().lower()}%"
        cursor.execute("SELECT * FROM orders WHERE LOWER(customer_name) LIKE ? ORDER BY id DESC LIMIT 1", (q,))
        row = cursor.fetchone()
    else:
        cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_orders(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_analytics_summary() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    # Total requests (distinct conversations)
    cursor.execute("SELECT COUNT(DISTINCT conversation_id) FROM agent_runs")
    total_requests = cursor.fetchone()[0] or 0

    # Total runs & statuses
    cursor.execute("SELECT COUNT(*) FROM agent_runs")
    total_runs = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM agent_runs WHERE status = 'COMPLETED'")
    successful = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM agent_runs WHERE status = 'WAITING_APPROVAL'")
    waiting = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM agent_runs WHERE status IN ('ERROR', 'REJECTED')")
    failed = cursor.fetchone()[0] or 0

    # Aggregates: tokens, cost, latency
    cursor.execute("""
    SELECT 
        COALESCE(SUM(input_tokens), 0),
        COALESCE(SUM(output_tokens), 0),
        COALESCE(SUM(cost_usd), 0.0),
        COALESCE(AVG(latency_ms), 0.0)
    FROM agent_runs
    """)
    in_tok, out_tok, total_cost, avg_lat = cursor.fetchone()

    # Agent execution distribution
    cursor.execute("""
    SELECT 
        agent_name,
        COUNT(*) as run_count,
        COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
        COALESCE(SUM(cost_usd), 0.0) as cost,
        COALESCE(AVG(latency_ms), 0.0) as avg_latency
    FROM agent_runs
    GROUP BY agent_name
    ORDER BY run_count DESC
    """)
    agent_dist = [dict(r) for r in cursor.fetchall()]

    # Recent runs for time chart (last 20 runs)
    cursor.execute("""
    SELECT id, conversation_id, agent_name, status, (input_tokens + output_tokens) as tokens, cost_usd, latency_ms, created_at
    FROM agent_runs
    ORDER BY created_at DESC
    LIMIT 20
    """)
    recent_runs = [dict(r) for r in cursor.fetchall()]
    recent_runs.reverse()

    conn.close()

    return {
        "total_requests": total_requests,
        "total_runs": total_runs,
        "successful_executions": successful,
        "waiting_approval": waiting,
        "failed_executions": failed,
        "active_agents": 4,
        "total_tokens": in_tok + out_tok,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_cost_usd": round(total_cost, 6),
        "average_latency_ms": round(avg_lat, 2),
        "agent_distribution": agent_dist,
        "recent_runs": recent_runs
    }

def get_request_history(search: Optional[str] = None, status_filter: Optional[str] = None, agent_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        r.conversation_id,
        MIN(r.created_at) as started_at,
        MAX(r.created_at) as completed_at,
        COUNT(r.id) as run_count,
        GROUP_CONCAT(r.agent_name, ' → ') as agents_chain,
        SUM(r.input_tokens + r.output_tokens) as total_tokens,
        SUM(r.cost_usd) as total_cost,
        MAX(r.latency_ms) as max_latency,
        (SELECT output_text FROM agent_runs WHERE conversation_id = r.conversation_id ORDER BY created_at DESC LIMIT 1) as latest_output,
        (SELECT status FROM agent_runs WHERE conversation_id = r.conversation_id ORDER BY created_at DESC LIMIT 1) as final_status,
        (SELECT steps_json FROM agent_runs WHERE conversation_id = r.conversation_id ORDER BY created_at ASC LIMIT 1) as initial_step
    FROM agent_runs r
    """

    conditions = []
    params = []

    if status_filter and status_filter != "ALL":
        conditions.append("EXISTS (SELECT 1 FROM agent_runs ar WHERE ar.conversation_id = r.conversation_id AND ar.status = ?)")
        params.append(status_filter)

    if agent_filter and agent_filter != "ALL":
        conditions.append("EXISTS (SELECT 1 FROM agent_runs ar WHERE ar.conversation_id = r.conversation_id AND LOWER(ar.agent_name) LIKE ?)")
        params.append(f"%{agent_filter.lower()}%")

    if search:
        s = f"%{search.strip().lower()}%"
        conditions.append("(LOWER(r.conversation_id) LIKE ? OR LOWER(r.output_text) LIKE ? OR LOWER(r.steps_json) LIKE ?)")
        params.extend([s, s, s])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY r.conversation_id ORDER BY started_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    history = []
    for row in rows:
        # Extract initial customer query and customer name from initial_step if available
        customer_name = "Alex Rivera"
        user_query = "Customer inquiry"
        if row["initial_step"]:
            try:
                steps_data = json.loads(row["initial_step"])
                if steps_data and len(steps_data) > 0:
                    details = steps_data[0].get("details", {})
                    customer_name = details.get("customer", customer_name)
                    user_query = details.get("message", user_query)
            except Exception:
                pass

        history.append({
            "conversation_id": row["conversation_id"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "customer_name": customer_name,
            "query": user_query,
            "agents_chain": row["agents_chain"],
            "total_tokens": row["total_tokens"] or 0,
            "total_cost": round(row["total_cost"] or 0.0, 6),
            "final_status": row["final_status"] or "COMPLETED",
            "latest_output": row["latest_output"] or ""
        })

    conn.close()
    return history

def update_approval_decision(run_id: str, decision: str, note: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    new_status = "COMPLETED" if decision.upper() == "APPROVED" else "REJECTED"
    
    # Update agent run
    cursor.execute("UPDATE agent_runs SET status = ? WHERE id = ?", (new_status, run_id))
    
    # If there's an associated refund, update it
    cursor.execute("UPDATE refunds SET status = ? WHERE status = 'WAITING_APPROVAL' AND id = (SELECT id FROM refunds WHERE status = 'WAITING_APPROVAL' ORDER BY created_at DESC LIMIT 1)", (new_status,))
    
    conn.commit()
    conn.close()
    return {
        "run_id": run_id,
        "status": new_status,
        "decision": decision,
        "note": note
    }
