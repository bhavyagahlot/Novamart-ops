import json
import logging
from typing import Dict, Any, Tuple
from app.agents.gemini_helper import call_gemini

logger = logging.getLogger("novamart.triage")

STORE_POLICY = """
NovaMart Ops Policy & FAQ:
1. Return Policy: We offer a 30-day hassle-free return policy on all electronics in original condition.
2. Shipping: Free 2-day express shipping on all orders over $50 across the country.
3. Warranty: Every device includes a standard 1-year NovaCare hardware warranty.
4. Discounts: Promotional discounts up to 15% can be approved automatically; custom enterprise discounts require manager review.
5. Refunds: Immediate automated refunds are issued up to $100; larger amounts require supervisor verification.
"""

def run_triage(customer_name: str, message: str) -> Dict[str, Any]:
    """
    Triage Agent:
    Analyzes customer intent and either answers policy/FAQ directly or routes
    to 'order', 'pricing', or 'billing'.
    """
    system_prompt = (
        "You are the NovaMart Triage Agent. Analyze customer intent. "
        "Classify into exactly one intent: 'order', 'pricing', 'billing', or 'faq'. "
        "If 'faq', provide a clear, friendly answer using the store policy. "
        "Respond strictly in JSON format: {\"intent\": \"order\"|\"pricing\"|\"billing\"|\"faq\", \"confidence\": float, \"faq_answer\": str or null}"
    )

    msg_lower = message.lower()
    default_intent = "faq"
    default_faq_answer = (
        f"Hello {customer_name}! NovaMart offers a 30-day hassle-free return policy on all electronics, "
        "a 1-year NovaCare hardware warranty on every device, and free 2-day express shipping on orders over $50. "
        "Automated refunds are processed up to $100, and promotional discounts up to 15% are instantly approved."
    )

    # Priority 0: General Policy, FAQ, Warranty inquiries
    if any(k in msg_lower for k in ["policy", "faq", "warranty", "guarantee", "return policy", "tell me about", "what is your", "shipping time"]):
        default_intent = "faq"
    # Priority 1: Billing & Refunds (e.g. "refund an expensive order", "cancel order")
    elif any(k in msg_lower for k in ["refund", "chargeback", "cancel", "money back", "billing", "return my", "return this"]):
        default_intent = "billing"
    # Priority 2: Pricing & Discounts (e.g. "discount on my order", "30% off")
    elif any(k in msg_lower for k in ["discount", "percent", "%", " off", "coupon", "promo", "deal", "cheaper", "lower price"]):
        default_intent = "pricing"
    # Priority 3: Purchasing & Ordering products
    elif any(k in msg_lower for k in ["order", "buy", "purchase", "laptop", "phone", "headphone", "tablet", "charger", "get me", "i want a"]):
        default_intent = "order"
    else:
        default_intent = "faq"

    mock_json = json.dumps({
        "intent": default_intent,
        "confidence": 0.96,
        "faq_answer": default_faq_answer
    })

    prompt = f"Customer Name: {customer_name}\nStore Policy:\n{STORE_POLICY}\nCustomer Message: {message}"
    raw_response, in_tokens, out_tokens, cost_usd, latency = call_gemini(
        prompt=prompt,
        system_instruction=system_prompt,
        mock_response=mock_json
    )

    intent = default_intent
    faq_answer = default_faq_answer

    try:
        clean_text = raw_response.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:-3].strip()
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:-3].strip()
        parsed = json.loads(clean_text)
        if "intent" in parsed and parsed["intent"] in ["order", "pricing", "billing", "faq"]:
            intent = parsed["intent"]
        if parsed.get("faq_answer"):
            faq_answer = parsed["faq_answer"]
    except Exception as exc:
        logger.debug(f"Parsing triage response fallback: {exc}")

    return {
        "agent": "Triage Agent",
        "intent": intent,
        "faq_answer": faq_answer,
        "raw_response": raw_response,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency
    }
