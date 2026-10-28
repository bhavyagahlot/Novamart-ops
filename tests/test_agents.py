import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import init_db, get_all_products, get_recent_runs
from app.agents.orchestrator import process_customer_message

def test_all():
    print("Initializing test DB...")
    init_db()

    print("\n--- Test 1: Order a laptop ---")
    res1 = process_customer_message("Jordan Lee", "I would like to order a laptop, please.")
    print("Status:", res1["status"])
    print("Reply:", res1["reply"])
    print("Agents ran:", [a["agent_name"] for a in res1["agents_ran"]])
    assert res1["status"] == "COMPLETED", f"Expected COMPLETED, got {res1['status']}"
    assert any(a["agent_name"] == "Order Agent" for a in res1["agents_ran"]), "Order Agent did not run"

    print("\n--- Test 2: Ask for 30% off ---")
    res2 = process_customer_message("Sara Connor", "Can I please get a 30% discount on my order?")
    print("Status:", res2["status"])
    print("Reply:", res2["reply"])
    print("Approval notice:", res2["approval_notice"])
    print("Agents ran:", [a["agent_name"] for a in res2["agents_ran"]])
    assert res2["status"] == "WAITING_APPROVAL", f"Expected WAITING_APPROVAL, got {res2['status']}"
    assert "30%" in res2["approval_notice"], "Approval notice does not mention 30%"
    assert any(a["agent_name"] == "Pricing Agent" for a in res2["agents_ran"]), "Pricing Agent did not run"

    print("\n--- Test 3: Refund an expensive order ---")
    res3 = process_customer_message("Marcus Vance", "I need to refund an expensive order of $1,299.99 for a laptop.")
    print("Status:", res3["status"])
    print("Reply:", res3["reply"])
    print("Approval notice:", res3["approval_notice"])
    print("Agents ran:", [a["agent_name"] for a in res3["agents_ran"]])
    assert res3["status"] == "WAITING_APPROVAL", f"Expected WAITING_APPROVAL, got {res3['status']}"
    assert "$1,299.99" in res3["approval_notice"] or "1299" in res3["approval_notice"], "Approval notice missing amount"
    assert any(a["agent_name"] == "Billing Agent" for a in res3["agents_ran"]), "Billing Agent did not run"

    print("\n--- Test 4: Ask a policy question ---")
    res4 = process_customer_message("Taylor Swift", "What is your return policy and warranty on electronics?")
    print("Status:", res4["status"])
    print("Reply:", res4["reply"])
    print("Agents ran:", [a["agent_name"] for a in res4["agents_ran"]])
    assert res4["status"] == "COMPLETED", f"Expected COMPLETED, got {res4['status']}"
    assert "return policy" in res4["reply"].lower() or "warranty" in res4["reply"].lower() or "novamart" in res4["reply"].lower()

    print("\n--- Test 5: Verify SQLite persistence ---")
    runs = get_recent_runs(limit=10)
    print(f"Total runs recorded in DB: {len(runs)}")
    assert len(runs) >= 4, f"Expected at least 4 runs, found {len(runs)}"
    for r in runs[:4]:
        print(f"Run {r['id']}: Agent={r['agent_name']}, Status={r['status']}, Steps={len(r['steps'])}, Cost=${r['cost_usd']:.6f}")

    print("\nALL 5 TEST SUITES PASSED PERFECTLY!")

if __name__ == "__main__":
    test_all()
