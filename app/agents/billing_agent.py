import re
import logging
from typing import Dict, Any, List
from app.config import settings
from app.agents.gemini_helper import call_gemini

logger = logging.getLogger("novamart.billing")

def run_billing_agent(customer_name: str, message: str) -> Dict[str, Any]:
    """
    Billing Agent:
    Handles refunds and billing inquiries. If refund amount > REFUND_APPROVAL_LIMIT,
    the agent sets status to WAITING_APPROVAL.
    """
    limit = settings.REFUND_APPROVAL_LIMIT  # default $100.00

    # Extract refund amount if mentioned (stripping formatting commas like $1,299.99)
    clean_msg = message.replace(",", "")
    match = re.search(r"\$\s*(\d+(\.\d+)?)", clean_msg)
    if match:
        refund_amount = float(match.group(1))
    else:
        num_match = re.search(r"\b(\d{2,6}(\.\d+)?)\b", clean_msg)
        if num_match:
            refund_amount = float(num_match.group(1))
        elif any(w in clean_msg.lower() for w in ["expensive", "laptop", "phone"]):
            refund_amount = 1299.99  # typical expensive product order
        else:
            refund_amount = 49.99

    steps: List[Dict[str, str]] = []
    steps.append({
        "action": "EVALUATE_REFUND_AMOUNT",
        "detail": f"Parsed refund request of ${refund_amount:.2f}. Auto-refund limit is ${limit:.2f}."
    })

    if refund_amount > limit:
        status = "WAITING_APPROVAL"
        reply = (
            f"Dear {customer_name}, your refund request of ${refund_amount:,.2f} exceeds our automated "
            f"limit of ${limit:,.2f}. It has been marked as WAITING_APPROVAL and submitted to a supervisor "
            "for human approval."
        )
        steps.append({
            "action": "FLAGGED_FOR_HUMAN_APPROVAL",
            "detail": f"Refund amount ${refund_amount:.2f} > threshold ${limit:.2f}. Flagged for Synapse supervisor sign-off."
        })
    else:
        status = "COMPLETED"
        refund_tx_id = f"TX-REF-{int(refund_amount * 100)}"
        reply = (
            f"Hello {customer_name}, your refund of ${refund_amount:,.2f} has been processed "
            f"successfully (Transaction #{refund_tx_id}). Funds should reflect within 2-3 business days."
        )
        steps.append({
            "action": "REFUND_PROCESSED",
            "detail": f"Refund of ${refund_amount:.2f} processed under limit. Reference {refund_tx_id}."
        })

    prompt = (
        f"Customer {customer_name} requested: '{message}'.\n"
        f"Refund amount: ${refund_amount:.2f}, Limit: ${limit:.2f}, Status: {status}.\n"
        f"Drafted Response: {reply}"
    )
    raw_response, in_tokens, out_tokens, cost_usd, latency = call_gemini(
        prompt=prompt,
        system_instruction="You are NovaMart Billing Agent. Handle billing and refund inquiries with clarity and empathy.",
        mock_response=reply
    )

    return {
        "agent": "Billing Agent",
        "status": status,
        "reply": reply,
        "refund_amount": refund_amount,
        "approval_type": "REFUND",
        "approval_amount": refund_amount,
        "steps": steps,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency
    }
