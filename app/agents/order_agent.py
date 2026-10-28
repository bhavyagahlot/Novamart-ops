import logging
import re
from typing import Dict, Any, List
from app.database import find_product_by_query, create_order, get_all_products
from app.agents.gemini_helper import call_gemini

logger = logging.getLogger("novamart.order")

def run_order_agent(customer_name: str, message: str) -> Dict[str, Any]:
    """
    Order Agent:
    Handles product orders, checks stock in SQLite, and creates the order.
    """
    catalog = get_all_products()
    catalog_summary = "\n".join([f"- {p['name']} (${p['price']:.2f}, {p['stock']} in stock)" for p in catalog])

    # Check for requested item
    product = find_product_by_query(message)
    quantity = 1
    # Check for quantity
    match = re.search(r"\b(\d+)\s*(unit|piece|item|laptop|phone|headphone)?\b", message, re.IGNORECASE)
    if match and int(match.group(1)) > 0 and int(match.group(1)) < 50:
        quantity = int(match.group(1))

    steps: List[Dict[str, str]] = []
    steps.append({
        "action": "CATALOG_LOOKUP",
        "detail": f"Queried catalog for '{message}'. Found match: {product['name'] if product else 'None'}"
    })

    if not product:
        reply = (
            f"Hi {customer_name}, we couldn't match an item in our current inventory. "
            f"Here are popular devices we have in stock:\n"
            + ", ".join([p["name"] for p in catalog[:3]])
        )
        status = "COMPLETED"
        order_id = None
    elif product["stock"] < quantity:
        reply = f"Sorry {customer_name}, {product['name']} is currently out of stock (only {product['stock']} available)."
        status = "COMPLETED"
        steps.append({
            "action": "STOCK_CHECK",
            "detail": f"Insufficient inventory for {product['name']} (Requested: {quantity}, Stock: {product['stock']})"
        })
        order_id = None
    else:
        total_price = round(product["price"] * quantity, 2)
        order_id = create_order(
            customer_name=customer_name,
            product_name=product["name"],
            quantity=quantity,
            unit_price=product["price"],
            total_price=total_price
        )
        reply = (
            f"Success {customer_name}! Your order for {quantity}x {product['name']} "
            f"is confirmed (Order #{order_id:04d}). Total: ${total_price:,.2f}. "
            "Express 2-day delivery has been scheduled."
        )
        status = "COMPLETED"
        steps.append({
            "action": "ORDER_CREATED",
            "detail": f"Order #{order_id:04d} placed for {quantity}x '{product['name']}' at ${total_price:.2f}. Stock updated to {product['stock'] - quantity}."
        })

    # Gemini prompt for metrics & polish
    prompt = (
        f"Customer {customer_name} asked to: '{message}'.\n"
        f"Inventory Status: {product['name'] if product else 'Not found'}, Stock: {product['stock'] if product else 0}.\n"
        f"Generated Order ID: {order_id}.\nResponse to customer: {reply}"
    )
    raw_response, in_tokens, out_tokens, cost_usd, latency = call_gemini(
        prompt=prompt,
        system_instruction="You are NovaMart Order Agent. Confirm the order details clearly and politely.",
        mock_response=reply
    )

    return {
        "agent": "Order Agent",
        "status": status,
        "reply": reply,
        "order_id": order_id,
        "steps": steps,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency
    }
