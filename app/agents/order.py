import re
from typing import Dict, Any, Tuple
from app.db import find_product_by_query, create_order, get_products
from .common import AgentExecutionContext, call_gemini, estimate_tokens

ORDER_SYSTEM_PROMPT = """You are the NovaMart Order Agent.
Extract the intended electronic product name and quantity from the customer's message.
Known product catalog items include:
- NovaBook Pro 16 / laptop
- NovaBook Air 13 / laptop
- NovaPhone Ultra / smartphone
- NovaSound ANC Headphones / headphones
- NovaWatch Active / smartwatch
- NovaCharge 100W GaN / charger

Respond in JSON format:
{"product_query": "laptop", "quantity": 1}
"""

def run_order_agent(customer_name: str, message: str, conversation_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ctx = AgentExecutionContext(agent_name="Order Agent", conversation_id=conversation_id)
    ctx.add_step("Initiated order processing flow", details={"customer": customer_name, "raw_message": message})

    product_query = "laptop"
    quantity = 1
    in_tok = 0
    out_tok = 0

    # Extract with Gemini if available
    gemini_resp, in_tok, out_tok = call_gemini(ORDER_SYSTEM_PROMPT, message)
    if gemini_resp:
        try:
            import json
            cleaned = re.sub(r"^```json\s*|\s*```$", "", gemini_resp.strip(), flags=re.MULTILINE)
            parsed = json.loads(cleaned)
            product_query = parsed.get("product_query", "laptop")
            quantity = int(parsed.get("quantity", 1))
            ctx.add_step("Extracted order parameters via Gemini", details={"product_query": product_query, "quantity": quantity})
        except Exception:
            pass

    # Heuristic fallback if Gemini did not produce structured output
    if not gemini_resp:
        msg_l = message.lower()
        if "phone" in msg_l:
            product_query = "phone"
        elif "headphone" in msg_l:
            product_query = "headphones"
        elif "watch" in msg_l:
            product_query = "watch"
        elif "charger" in msg_l:
            product_query = "charger"
        else:
            product_query = "laptop"

        # Check for numeric quantity
        qty_match = re.search(r"\b(\d+)\s*(?:units?|pcs?|items?|x)?\b", msg_l)
        if qty_match:
            try:
                quantity = max(1, int(qty_match.group(1)))
            except ValueError:
                quantity = 1

        in_tok = estimate_tokens(ORDER_SYSTEM_PROMPT) + estimate_tokens(message)
        ctx.add_step("Parsed product requirement", details={"query": product_query, "quantity": quantity})

    # Query product catalog in SQLite
    product = find_product_by_query(product_query)
    if not product:
        # Fallback to the first available product in catalog
        available = get_products()
        product = available[0] if available else None

    if not product:
        reply = "Sorry, our product catalog is currently unavailable. Please try again shortly."
        ctx.add_step("Product catalog lookup failed", status="ERROR")
        run_record = ctx.finalize("ERROR", reply, in_tok, estimate_tokens(reply))
        return {"reply": reply, "order": None}, run_record

    ctx.add_step(
        f"Inventory lookup: Found '{product['name']}' (Stock: {product['stock']}, Price: ${product['price']:.2f})",
        details={"product_id": product["id"], "stock": product["stock"]}
    )

    if product["stock"] < quantity:
        reply = f"Sorry {customer_name}, '{product['name']}' is out of stock (Available: {product['stock']})."
        ctx.add_step("Insufficient inventory stock", status="ERROR")
        run_record = ctx.finalize("ERROR", reply, in_tok, estimate_tokens(reply))
        return {"reply": reply, "order": None}, run_record

    # Create the order and decrement stock in SQLite
    order_data = create_order(customer_name, product["id"], quantity)
    ctx.add_step(
        f"Order #{order_data['order_id']} created in database and stock decremented",
        details=order_data
    )

    reply = (
        f"Your order for the {order_data['product_name']} is confirmed! "
        f"(Order #{order_data['order_id']}, Qty: {order_data['quantity']}, Total: ${order_data['total_amount']:,.2f}). "
        f"Thank you for shopping with NovaMart!"
    )
    out_tok = estimate_tokens(reply)
    run_record = ctx.finalize("COMPLETED", reply, in_tok, out_tok)

    return {"reply": reply, "order": order_data}, run_record
