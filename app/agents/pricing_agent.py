import re
import logging
from typing import Dict, Any, List
from app.config import settings
from app.agents.gemini_helper import call_gemini

logger = logging.getLogger("novamart.pricing")

def run_pricing_agent(customer_name: str, message: str) -> Dict[str, Any]:
    """
    Pricing Agent:
    Handles discount requests. If requested discount > DISCOUNT_APPROVAL_LIMIT_PERCENT,
    the agent does NOT approve it and marks status as WAITING_APPROVAL.
    """
    threshold = settings.DISCOUNT_APPROVAL_LIMIT_PERCENT  # default 15%

    # Extract discount percentage from customer message
    match = re.search(r"(\d+(\.\d+)?)\s*%", message)
    if match:
        discount_pct = float(match.group(1))
    else:
        # Check for words like "half", "thirty", etc. or general discount terms
        num_match = re.search(r"\b(\d{1,2})\b", message)
        if num_match:
            discount_pct = float(num_match.group(1))
        elif "half" in message.lower():
            discount_pct = 50.0
        else:
            discount_pct = 20.0  # sensible fallback

    steps: List[Dict[str, str]] = []
    steps.append({
        "action": "EVALUATE_DISCOUNT",
        "detail": f"Parsed requested discount: {discount_pct:.1f}%. Max auto-approval policy limit is {threshold:.1f}%."
    })

    if discount_pct > threshold:
        status = "WAITING_APPROVAL"
        reply = (
            f"Hello {customer_name}, your request for a {discount_pct:.0f}% discount exceeds our automated "
            f"store limit of {threshold:.0f}%. We have forwarded this request to a store supervisor for human approval."
        )
        steps.append({
            "action": "FLAGGED_FOR_HUMAN_APPROVAL",
            "detail": f"Discount {discount_pct:.1f}% > limit {threshold:.1f}%. Escalated to Synapse human approval queue."
        })
    else:
        status = "COMPLETED"
        coupon_code = f"NOVA{int(discount_pct)}OFF"
        reply = (
            f"Great news {customer_name}! Your {discount_pct:.0f}% discount has been pre-approved. "
            f"Use promo code '{coupon_code}' at checkout to apply your savings."
        )
        steps.append({
            "action": "AUTO_APPROVED",
            "detail": f"Discount {discount_pct:.1f}% <= limit {threshold:.1f}%. Generated coupon code {coupon_code}."
        })

    prompt = (
        f"Customer {customer_name} asked: '{message}'.\n"
        f"Discount requested: {discount_pct}%, Limit: {threshold}%, Status: {status}.\n"
        f"Drafted Response: {reply}"
    )
    raw_response, in_tokens, out_tokens, cost_usd, latency = call_gemini(
        prompt=prompt,
        system_instruction="You are NovaMart Pricing Agent. Provide concise and polite responses regarding discounts.",
        mock_response=reply
    )

    return {
        "agent": "Pricing Agent",
        "status": status,
        "reply": reply,
        "discount_percent": discount_pct,
        "approval_type": "DISCOUNT",
        "approval_amount": discount_pct,
        "steps": steps,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency
    }
