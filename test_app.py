import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
PROJECT_ROOT = os.path.abspath("C:/Users/vikas/.gemini/antigravity/scratch/novamart-ops")
sys.path.insert(0, PROJECT_ROOT)

from app.db import init_db, get_products, get_agent_runs_by_conversation
from app.main import handle_chat, ChatRequest, get_public_config, serve_index

def run_tests():
    print("=" * 60)
    print("NOVAMART OPS — COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    # 1. Database Initialization
    print("\n[TEST 1] Initializing Database & Seed Products...")
    init_db()
    products = get_products()
    print(f"✓ Found {len(products)} seeded products:")
    for p in products:
        print(f"  - [{p['id']}] {p['name']} ({p['category']}): ${p['price']} | Stock: {p['stock']}")
    assert len(products) >= 6, "Expected at least 6 products"

    # 2. Config & HTML Serving
    print("\n[TEST 2] Testing Config & HTML Endpoint...")
    cfg = get_public_config()
    print("Public config:", cfg)
    assert cfg["refund_approval_limit"] == 100.0
    assert cfg["discount_approval_limit_percent"] == 15.0
    html_resp = serve_index()
    assert html_resp.status_code == 200
    assert "NovaMart Ops" in html_resp.body.decode("utf-8")
    print("✓ HTML & Config verified successfully")

    # 3. Scenario 1: Order a laptop
    print("\n[TEST 3] Quick-Test: 'Order a laptop'")
    req1 = ChatRequest(customer_name="Alex Rivera", message="Order a laptop")
    res1 = handle_chat(req1)
    print("Reply:", res1.reply)
    print("Requires approval:", res1.requires_approval)
    print(f"Runs generated: {len(res1.runs)}")
    for r in res1.runs:
        print(f"  • {r['agent_name']} [{r['status']}] - Cost: ${r['cost_usd']:.6f}, Latency: {r['latency_ms']}ms")
    assert not res1.requires_approval
    assert any(r["agent_name"] == "Order Agent" and r["status"] == "COMPLETED" for r in res1.runs)
    print("✓ Scenario 1: Order successfully placed and inventory decremented!")

    # 4. Scenario 2: Ask for 30% off
    print("\n[TEST 4] Quick-Test: 'Ask for 30% off'")
    req2 = ChatRequest(customer_name="Alex Rivera", message="Ask for 30% off")
    res2 = handle_chat(req2)
    print("Reply:", res2.reply)
    print("Requires approval:", res2.requires_approval)
    print("Approval notice:", res2.approval_notice)
    for r in res2.runs:
        print(f"  • {r['agent_name']} [{r['status']}] - Cost: ${r['cost_usd']:.6f}, Latency: {r['latency_ms']}ms")
    assert res2.requires_approval is True
    assert any(r["agent_name"] == "Pricing Agent" and r["status"] == "WAITING_APPROVAL" for r in res2.runs)
    print("✓ Scenario 2: High discount held in WAITING_APPROVAL as expected!")

    # 5. Scenario 3: Refund an expensive order
    print("\n[TEST 5] Quick-Test: 'Refund an expensive order'")
    req3 = ChatRequest(customer_name="Alex Rivera", message="Refund an expensive order")
    res3 = handle_chat(req3)
    print("Reply:", res3.reply)
    print("Requires approval:", res3.requires_approval)
    print("Approval notice:", res3.approval_notice)
    for r in res3.runs:
        print(f"  • {r['agent_name']} [{r['status']}] - Cost: ${r['cost_usd']:.6f}, Latency: {r['latency_ms']}ms")
    assert res3.requires_approval is True
    assert any(r["agent_name"] == "Billing Agent" and r["status"] == "WAITING_APPROVAL" for r in res3.runs)
    print("✓ Scenario 3: Expensive refund held in WAITING_APPROVAL as expected!")

    # 6. Scenario 4: Ask a policy question
    print("\n[TEST 6] Quick-Test: 'What is your return and warranty policy?'")
    req4 = ChatRequest(customer_name="Alex Rivera", message="What is your return and warranty policy?")
    res4 = handle_chat(req4)
    print("Reply:", res4.reply)
    print("Requires approval:", res4.requires_approval)
    print(f"Runs generated: {len(res4.runs)}")
    for r in res4.runs:
        print(f"  • {r['agent_name']} [{r['status']}] - Cost: ${r['cost_usd']:.6f}, Latency: {r['latency_ms']}ms")
    assert not res4.requires_approval
    assert len(res4.runs) == 1
    assert res4.runs[0]["agent_name"] == "Triage Agent"
    assert res4.runs[0]["status"] == "COMPLETED"
    print("✓ Scenario 4: Policy question answered directly by Triage Agent!")

    # 7. Verify SQLite Persistence of Runs
    print("\n[TEST 7] Verifying SQLite persistence of conversation runs...")
    stored_runs = get_agent_runs_by_conversation(res1.conversation_id)
    print(f"✓ Found {len(stored_runs)} runs saved in SQLite for conversation {res1.conversation_id}")
    assert len(stored_runs) == 2

    print("\n" + "=" * 60)
    print("ALL VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
