import re
from typing import Dict, Any, Tuple
from app.config import settings
from .common import AgentExecutionContext, call_gemini, estimate_tokens

PRICING_SYSTEM_PROMPT = """You are the NovaMart Pricing Agent.
Extract the discount percentage requested by the customer.
If not specified, estimate from context or default to 20.
Respond in JSON format:
{"requested_percent": 30.0}
"""

def run_pricing_agent(customer_name: str, message: str, conversation_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ctx = AgentExecutionContext(agent_name="Pricing Agent", conversation_id=conversation_id)
    ctx.add_step("Received discount inquiry", details={"customer": customer_name, "message": message})

    requested_percent = 20.0
    in_tok = 0
    out_tok = 0

    # Extract with Gemini if available
    gemini_resp, in_tok, out_tok = call_gemini(PRICING_SYSTEM_PROMPT, message)
    if gemini_resp:
        try:
            import json
            cleaned = re.sub(r"^```json\s*|\s*```$", "", gemini_resp.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)
            requested_percent = float(data.get("requested_percent", 20.0))
            ctx.add_step(f"Extracted discount request via Gemini: {requested_percent}%")
        except Exception:
            pass

    # Regex heuristic fallback if Gemini was not used or did not produce output
    if not gemini_resp:
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", message)
        if pct_match:
            requested_percent = float(pct_match.group(1))
        elif "half" in message.lower() or "50" in message:
            requested_percent = 50.0
        elif "30" in message:
            requested_percent = 30.0
        elif "10" in message:
            requested_percent = 10.0
        elif "15" in message:
            requested_percent = 15.0
        else:
            requested_percent = 20.0

        in_tok = estimate_tokens(PRICING_SYSTEM_PROMPT) + estimate_tokens(message)
        ctx.add_step(f"Parsed requested discount rate: {requested_percent}%", details={"raw_message": message})

    limit = settings.DISCOUNT_APPROVAL_LIMIT_PERCENT
    ctx.add_step(
        f"Evaluated against automated discount threshold (Max allowed: {limit}%)",
        details={"requested": requested_percent, "policy_limit": limit}
    )

    if requested_percent > limit:
        # Does NOT approve. Status WAITING_APPROVAL
        status = "WAITING_APPROVAL"
        reply = (
            f"The requested discount of {requested_percent:.0f}% exceeds our automated approval threshold of {limit:.0f}%. "
            f"Your request has been placed on hold and submitted to our store operations manager. "
            f"Current status: Waiting for human approval."
        )
        ctx.add_step(
            f"Status escalated to WAITING_APPROVAL: {requested_percent:.0f}% > {limit:.0f}%",
            status="WAITING_APPROVAL",
            details={"exceeded_by": round(requested_percent - limit, 1)}
        )
        requires_approval = True
    else:
        status = "COMPLETED"
        coupon_code = f"NOVA{int(requested_percent)}"
        reply = (
            f"Great news {customer_name}! Your requested {requested_percent:.0f}% discount has been approved. "
            f"Use promotional code {coupon_code} at checkout to receive your discount."
        )
        ctx.add_step(f"Discount approved automatically. Generated promo coupon: {coupon_code}")
        requires_approval = False

    out_tok = estimate_tokens(reply)
    run_record = ctx.finalize(status, reply, in_tok, out_tok)

    return {
        "reply": reply,
        "status": status,
        "requested_percent": requested_percent,
        "limit_percent": limit,
        "requires_approval": requires_approval
    }, run_record
