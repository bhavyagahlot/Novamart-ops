import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import init_db
from app.main import (
    chat_endpoint,
    get_products_endpoint,
    get_runs_endpoint,
    get_frontend_config,
    ChatRequest
)

def run_api_tests():
    print("1. Initializing DB...", flush=True)
    init_db()

    print("2. Testing get_frontend_config()...", flush=True)
    cfg = get_frontend_config()
    assert "synapse_url" in cfg
    assert "gemini_model" in cfg
    print("Config response:", cfg, flush=True)

    print("3. Testing get_products_endpoint()...", flush=True)
    prods = get_products_endpoint()
    assert len(prods["products"]) >= 5
    print(f"Products in DB: {len(prods['products'])}", flush=True)

    print("4. Testing chat_endpoint (Order a laptop)...", flush=True)
    res_order = chat_endpoint(ChatRequest(customer_name="Jordan Lee", message="Order a laptop"))
    assert res_order["status"] == "COMPLETED"
    assert any(a["agent_name"] == "Order Agent" for a in res_order["agents_ran"])
    print("Order confirmed:", res_order["reply"], flush=True)

    print("5. Testing chat_endpoint (Ask for 30% off)...", flush=True)
    res_discount = chat_endpoint(ChatRequest(customer_name="Sara Connor", message="Can I please get a 30% discount on my order?"))
    assert res_discount["status"] == "WAITING_APPROVAL"
    assert "30%" in res_discount["approval_notice"]
    print("Discount approval notice:", res_discount["approval_notice"], flush=True)

    print("6. Testing chat_endpoint (Refund an expensive order)...", flush=True)
    res_refund = chat_endpoint(ChatRequest(customer_name="Marcus Vance", message="I need to refund an expensive order of $1,299.99 for a laptop."))
    assert res_refund["status"] == "WAITING_APPROVAL"
    assert "1,299.99" in res_refund["approval_notice"] or "1299" in res_refund["approval_notice"]
    print("Refund approval notice:", res_refund["approval_notice"], flush=True)

    print("7. Testing chat_endpoint (Ask a policy question)...", flush=True)
    res_policy = chat_endpoint(ChatRequest(customer_name="Taylor Swift", message="What is your return policy and warranty on electronics?"))
    assert res_policy["status"] == "COMPLETED"
    print("Policy reply:", res_policy["reply"], flush=True)

    print("8. Testing get_runs_endpoint()...", flush=True)
    runs = get_runs_endpoint()
    assert len(runs["runs"]) >= 4
    print(f"Recorded runs in DB: {len(runs['runs'])}", flush=True)

    print("9. Verifying static assets on disk...", flush=True)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    html_path = os.path.join(base_dir, "static", "index.html")
    css_path = os.path.join(base_dir, "static", "styles.css")
    js_path = os.path.join(base_dir, "static", "app.js")
    assert os.path.exists(html_path), "index.html missing"
    assert os.path.exists(css_path), "styles.css missing"
    assert os.path.exists(js_path), "app.js missing"
    print("All static frontend files verified on disk.", flush=True)

    print("\nALL FASTAPI ENDPOINTS & LOGIC TESTS PASSED PERFECTLY!", flush=True)

if __name__ == "__main__":
    run_api_tests()
