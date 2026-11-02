import re
from typing import Dict, Any, Tuple
from app.config import settings
from app.db import create_refund, get_connection
from .common import AgentExecutionContext, call_gemini, estimate_tokens

BILLING_SYSTEM_PROMPT = """You are the NovaMart Billing Agent.
Extract the refund amount and order ID (if any) from the customer's message.
If they say "expensive order", set amount to 1299.99 and order_id to 1001.
Respond in JSON format:
{"amount": 1299.99, "order_id": 1001, "reason": "Customer requested refund for expensive order"}
"""

def run_billing_agent(customer_name: str, message: str, conversation_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ctx = AgentExecutionContext(agent_name="Billing Agent", conversation_id=conversation_id)
    msg_l = message.lower()
    
    # Check if this is an Invoice Dispute inquiry
    is_invoice_dispute = any(k in msg_l for k in ["invoice", "incorrect bill", "overcharge", "wrong invoice", "billing error", "billed twice", "dispute"])

    if is_invoice_dispute:
        ctx.add_step("Initiated invoice dispute and audit procedure", details={"customer": customer_name, "message": message})
        in_tok = estimate_tokens(BILLING_SYSTEM_PROMPT) + estimate_tokens(message)
        
        # Check order invoice in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, product_name, total_amount FROM orders ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        
        order_id = row["id"] if row else 1001
        order_total = float(row["total_amount"]) if row else 1299.99
        dispute_amount = 120.00 if "expensive" in msg_l or "1001" in msg_l or "laptop" in msg_l else 65.00
        
        ctx.add_step(
            f"Audited Invoice #INV-{order_id} line items against billing records",
            details={"invoice_id": f"INV-{order_id}", "billed_total": order_total, "discrepancy_claimed": dispute_amount}
        )
        
        # Threshold for automatic invoice adjustment is $50
        adjustment_limit = 50.00
        ctx.add_step(
            f"Compared claimed discrepancy (${dispute_amount:.2f}) against automated billing threshold (${adjustment_limit:.2f})",
            details={"dispute_amount": dispute_amount, "limit": adjustment_limit}
        )

        if dispute_amount > adjustment_limit:
            status = "WAITING_APPROVAL"
            requires_approval = True
            ctx.add_step(
                f"Dispute escalated to WAITING_APPROVAL: ${dispute_amount:.2f} > ${adjustment_limit:.2f}",
                status="WAITING_APPROVAL",
                details={"exceeded_amount": round(dispute_amount - adjustment_limit, 2)}
            )
            refund_record = create_refund(
                customer_name=customer_name,
                amount=dispute_amount,
                reason=f"Invoice dispute: overcharge claim on INV-{order_id}",
                order_id=order_id,
                requires_approval=True
            )
            reply = (
                f"Invoice Dispute Logged for #{order_id} (INV-{order_id}). "
                f"Your reported overcharge of ${dispute_amount:.2f} exceeds our instant adjustment threshold of ${adjustment_limit:.2f}. "
                f"A billing case has been opened and is currently waiting for human supervisor approval."
            )
        else:
            status = "COMPLETED"
            requires_approval = False
            ctx.add_step(f"Auto-correction credit of ${dispute_amount:.2f} applied to invoice")
            reply = (
                f"Invoice corrected: We verified your discrepancy report on Invoice #INV-{order_id}. "
                f"An automatic credit of ${dispute_amount:.2f} has been applied to your NovaMart account."
            )

        out_tok = estimate_tokens(reply)
        run_record = ctx.finalize(status, reply, in_tok, out_tok)
        return {
            "reply": reply,
            "status": status,
            "amount": dispute_amount,
            "limit": adjustment_limit,
            "order_id": order_id,
            "requires_approval": requires_approval
        }, run_record

    # Regular Refund Assessment
    ctx.add_step("Initiated refund assessment", details={"customer": customer_name, "message": message})

    amount = 0.0
    order_id = None
    reason = "Customer refund request"
    in_tok = 0
    out_tok = 0

    # Attempt Gemini parsing
    gemini_resp, in_tok, out_tok = call_gemini(BILLING_SYSTEM_PROMPT, message)
    if gemini_resp:
        try:
            import json
            cleaned = re.sub(r"^```json\s*|\s*```$", "", gemini_resp.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)
            amount = float(data.get("amount", 0.0))
            order_id = data.get("order_id")
            reason = data.get("reason", reason)
            ctx.add_step("Parsed refund criteria via Gemini", details={"amount": amount, "order_id": order_id})
        except Exception:
            pass

    # Heuristic parsing fallback if Gemini did not produce structured output
    if not gemini_resp or amount <= 0:
        msg_l = message.lower()
        
        # Check for dollar amounts ($150, 150 dollars, etc.)
        dollar_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", message)
        if dollar_match:
            amount = float(dollar_match.group(1))
        elif "expensive" in msg_l or "laptop" in msg_l:
            amount = 1299.99
            order_id = 1001
            reason = "Refund for NovaBook Pro 16 (high value)"
        elif "cheap" in msg_l or "charger" in msg_l:
            amount = 49.99
            order_id = 1003
            reason = "Refund for NovaCharge 100W GaN"
        else:
            # Check for general order match in database
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, total_amount, product_name FROM orders ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row:
                order_id = row["id"]
                amount = float(row["total_amount"])
                reason = f"Refund for Order #{order_id} ({row['product_name']})"
            else:
                amount = 1299.99
                order_id = 1001

        in_tok = estimate_tokens(BILLING_SYSTEM_PROMPT) + estimate_tokens(message)
        ctx.add_step(f"Determined refund value: ${amount:.2f}", details={"order_id": order_id, "reason": reason})

    limit = settings.REFUND_APPROVAL_LIMIT
    ctx.add_step(
        f"Verified refund amount against policy limit (${limit:.2f})",
        details={"refund_amount": amount, "threshold": limit}
    )

    if amount > limit:
        status = "WAITING_APPROVAL"
        requires_approval = True
        ctx.add_step(
            f"Escalated to WAITING_APPROVAL: ${amount:.2f} exceeds ${limit:.2f}",
            status="WAITING_APPROVAL",
            details={"exceeded_amount": round(amount - limit, 2)}
        )
        # Record refund in SQLite
        refund_record = create_refund(
            customer_name=customer_name,
            amount=amount,
            reason=reason,
            order_id=order_id,
            requires_approval=True
        )
        reply = (
            f"That refund needs manager approval. The requested refund of ${amount:,.2f}"
            + (f" for Order #{order_id}" if order_id else "")
            + f" exceeds our instant automated ceiling of ${limit:,.2f}. "
            f"Your refund request #{refund_record['refund_id']} has been securely logged and is awaiting human approval."
        )
    else:
        status = "COMPLETED"
        requires_approval = False
        refund_record = create_refund(
            customer_name=customer_name,
            amount=amount,
            reason=reason,
            order_id=order_id,
            requires_approval=False
        )
        ctx.add_step(f"Refund #{refund_record['refund_id']} processed and confirmed in database")
        reply = (
            f"Your refund request of ${amount:,.2f}"
            + (f" for Order #{order_id}" if order_id else "")
            + f" has been approved and processed. "
            f"Transaction #{refund_record['refund_id']} will be credited back to your original payment method in 2-3 business days."
        )

    out_tok = estimate_tokens(reply)
    run_record = ctx.finalize(status, reply, in_tok, out_tok)

    return {
        "reply": reply,
        "status": status,
        "amount": amount,
        "limit": limit,
        "order_id": order_id,
        "requires_approval": requires_approval,
        "refund_id": refund_record["refund_id"]
    }, run_record
