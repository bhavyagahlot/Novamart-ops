import json
import re
from typing import Dict, Any, Tuple
from .common import AgentExecutionContext, call_gemini, estimate_tokens, is_kill_switch_active

FAQ_POLICIES = {
    "return": "Our return policy allows returns within 30 days of delivery for any items in original condition. Standard refunds under $100 are processed instantly, while refunds over $100 require manager approval.",
    "warranty": "All NovaMart electronics come with a 1-year standard hardware manufacturer warranty covering defects and hardware failures.",
    "shipping": "We offer free standard 2-3 day shipping on all orders over $50 across the continental United States. Standard delivery is $5.99 for orders below $50.",
    "discount": "NovaMart provides automatic promotional discounts of up to 15%. Discounts exceeding 15% are routed to our pricing team for manager authorization.",
    "invoice": "Invoices are generated upon checkout. If you notice a discrepancies, our Billing Agent can audit the line items and issue automated adjustments under $50, or escalate for review.",
    "general": "Welcome to NovaMart Ops! We are an authorized electronics retailer offering laptops, smartphones, headphones, and premium accessories with 1-year warranty and a 30-day return policy."
}

TRIAGE_SYSTEM_PROMPT = """You are the NovaMart Ops Triage Agent.
Your job is to read the customer's incoming message and determine how to route it:
1. "order": If the user wants to order, purchase, or buy a product, OR check order/shipping status (e.g. "Check order status", "track order #1001").
2. "pricing": If the user is requesting a discount, promo code, or price adjustment (e.g. "Request a 30% discount").
3. "billing": If the user is requesting a refund, OR reporting an invoice error / billing dispute (e.g. "Report an incorrect invoice", "Refund an expensive order").
4. "policy_faq": If the user is asking about store policies (shipping, warranty, return policy, support hours).

Respond ONLY with valid JSON in this exact format:
{
  "route": "order" | "pricing" | "billing" | "policy_faq",
  "reason": "Brief reason for classification",
  "faq_answer": "Helpful answer to policy question if route is policy_faq, otherwise empty string"
}
"""

def _rule_based_triage(message: str) -> Tuple[str, str, str]:
    msg = message.lower()
    
    # 1. Invoice error / Billing dispute
    if any(k in msg for k in ["invoice", "incorrect bill", "overcharge", "billed twice", "wrong price on invoice", "billing error"]):
        return "billing", "Customer is reporting an invoice dispute or billing discrepancy.", ""

    # 2. Order Tracking & Status
    if any(k in msg for k in ["order status", "track", "tracking", "where is my order", "status of my order", "check order", "package status"]):
        return "order", "Customer is inquiring about order tracking and delivery status.", ""

    # 3. Discount / Pricing
    if any(k in msg for k in ["discount", "% off", "percent off", "promo", "coupon", "cheaper", "deal", "30%"]):
        return "pricing", "Customer is requesting a discount or promotional pricing.", ""
    
    # 4. Refund / Money Back
    if any(k in msg for k in ["refund", "money back", "reimburse", "chargeback", "cancel order"]):
        return "billing", "Customer is requesting a refund or billing action.", ""
    
    # 5. Order / Purchase
    if any(k in msg for k in ["order", "buy", "purchase", "laptop", "phone", "headphones", "charger", "watch"]):
        # Check if it's asking for a policy first
        if any(q in msg for q in ["what is", "how do", "can you tell me", "policy", "warranty", "shipping days"]):
            pass
        else:
            return "order", "Customer is attempting to place an electronics order.", ""

    # 6. Policy / FAQ
    if "return" in msg or "policy" in msg:
        return "policy_faq", "Customer is asking about return/store policy.", FAQ_POLICIES["return"]
    if "warranty" in msg:
        return "policy_faq", "Customer is inquiring about product warranty.", FAQ_POLICIES["warranty"]
    if "shipping" in msg or "delivery" in msg:
        return "policy_faq", "Customer is asking about shipping timeframes.", FAQ_POLICIES["shipping"]
        
    return "policy_faq", "General inquiry addressed with store policy.", FAQ_POLICIES["general"]

def run_triage_agent(customer_name: str, message: str, conversation_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ctx = AgentExecutionContext(agent_name="Triage Agent", conversation_id=conversation_id)
    ctx.add_step("Received incoming customer inquiry", details={"customer": customer_name, "message": message})

    if is_kill_switch_active():
        ctx.add_step("Emergency Kill Switch Active: Operation blocked", status="ERROR")
        reply = "⚠️ Service Temporarily Halted: The Synapse Emergency Kill Switch has been engaged by an administrator. All automated agent operations are currently paused for safety. Please check back shortly."
        run_record = ctx.finalize("ERROR", reply, 0, estimate_tokens(reply))
        return {"route": "killswitch", "reply": reply}, run_record

    route = "policy_faq"
    reason = ""
    reply = ""
    in_tok = 0
    out_tok = 0

    # Attempt Gemini parsing
    gemini_resp, in_tok, out_tok = call_gemini(
        TRIAGE_SYSTEM_PROMPT,
        f"Customer: {customer_name}\nMessage: {message}"
    )

    if gemini_resp:
        try:
            # Clean possible markdown fencing
            cleaned = re.sub(r"^```json\s*|\s*```$", "", gemini_resp.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)
            route = data.get("route", "policy_faq")
            reason = data.get("reason", "Classified by Gemini model.")
            reply = data.get("faq_answer", "")
            ctx.add_step("Gemini Intent Classification", details={"route": route, "reason": reason})
        except Exception:
            route, reason, reply = _rule_based_triage(message)
            ctx.add_step("Heuristic Classification Fallback", details={"route": route, "reason": reason})
    else:
        route, reason, reply = _rule_based_triage(message)
        ctx.add_step("Heuristic Classification Applied", details={"route": route, "reason": reason})
        in_tok = estimate_tokens(TRIAGE_SYSTEM_PROMPT) + estimate_tokens(message)
        out_tok = estimate_tokens(reply or reason)

    # Direct resolution or routing step
    if route == "policy_faq":
        final_output = reply or FAQ_POLICIES["return"]
        ctx.add_step("Direct FAQ Response Generated", details={"reply_length": len(final_output)})
        run_record = ctx.finalize(
            status="COMPLETED",
            output_text=final_output,
            input_tokens=in_tok,
            output_tokens=out_tok
        )
        return {"route": "policy_faq", "reply": final_output}, run_record
    else:
        ctx.add_step(f"Handoff to {route.capitalize()} Specialist Agent", details={"target_agent": route})
        run_record = ctx.finalize(
            status="COMPLETED",
            output_text=f"Routed customer request to {route.capitalize()} Agent. Reason: {reason}",
            input_tokens=in_tok,
            output_tokens=out_tok
        )
        return {"route": route, "reason": reason}, run_record
