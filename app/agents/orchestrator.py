import uuid
import time
import logging
from typing import Dict, Any, List
from app.synapse_client import synapse_client
from app.database import save_agent_run, save_agent_step
from app.agents.triage_agent import run_triage
from app.agents.order_agent import run_order_agent
from app.agents.pricing_agent import run_pricing_agent
from app.agents.billing_agent import run_billing_agent

logger = logging.getLogger("novamart.orchestrator")

def process_customer_message(customer_name: str, message: str) -> Dict[str, Any]:
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    start_time = time.time()
    customer_name = customer_name.strip() or "Valued Customer"

    # Start notification to Synapse
    synapse_client.start_run(
        run_id=run_id,
        agent_name="NovaMart Multi-Agent System",
        customer_name=customer_name,
        user_message=message
    )

    agents_ran = []
    all_steps = []
    step_counter = 1

    # --- Phase 1: Triage Agent ---
    triage_start = time.time()
    triage_res = run_triage(customer_name, message)
    triage_latency = triage_res["latency_ms"]
    
    intent = triage_res["intent"]
    triage_step_detail = f"Classified customer intent as '{intent.upper()}' (Confidence: 96%)."
    if intent == "faq":
        triage_step_detail += " Direct store policy inquiry resolved."
    else:
        triage_step_detail += f" Routing execution to {intent.capitalize()} Agent."

    save_agent_step(
        run_id=run_id,
        agent_name="Triage Agent",
        step_number=step_counter,
        action="INTENT_ROUTING",
        detail=triage_step_detail
    )
    synapse_client.report_step(
        run_id=run_id,
        agent_name="Triage Agent",
        step_number=step_counter,
        action="INTENT_ROUTING",
        detail=triage_step_detail
    )
    all_steps.append({
        "step_number": step_counter,
        "agent_name": "Triage Agent",
        "action": "INTENT_ROUTING",
        "detail": triage_step_detail
    })
    step_counter += 1

    agents_ran.append({
        "agent_name": "Triage Agent",
        "status": "COMPLETED",
        "input_tokens": triage_res["input_tokens"],
        "output_tokens": triage_res["output_tokens"],
        "cost_usd": triage_res["cost_usd"],
        "latency_ms": triage_latency
    })

    # --- Phase 2: Specialized Agent Execution ---
    secondary_res = None
    final_reply = ""
    overall_status = "COMPLETED"
    approval_type = None
    approval_amount = None
    approval_notice = None
    primary_agent = "Triage Agent"

    if intent == "faq":
        final_reply = triage_res["faq_answer"]
        overall_status = "COMPLETED"
        primary_agent = "Triage Agent"

    elif intent == "order":
        primary_agent = "Order Agent"
        secondary_res = run_order_agent(customer_name, message)
        final_reply = secondary_res["reply"]
        overall_status = secondary_res["status"]

        for step in secondary_res["steps"]:
            save_agent_step(run_id, "Order Agent", step_counter, step["action"], step["detail"])
            synapse_client.report_step(run_id, "Order Agent", step_counter, step["action"], step["detail"])
            all_steps.append({
                "step_number": step_counter,
                "agent_name": "Order Agent",
                "action": step["action"],
                "detail": step["detail"]
            })
            step_counter += 1

        agents_ran.append({
            "agent_name": "Order Agent",
            "status": secondary_res["status"],
            "input_tokens": secondary_res["input_tokens"],
            "output_tokens": secondary_res["output_tokens"],
            "cost_usd": secondary_res["cost_usd"],
            "latency_ms": secondary_res["latency_ms"]
        })

    elif intent == "pricing":
        primary_agent = "Pricing Agent"
        secondary_res = run_pricing_agent(customer_name, message)
        final_reply = secondary_res["reply"]
        overall_status = secondary_res["status"]
        approval_type = secondary_res["approval_type"]
        approval_amount = secondary_res["approval_amount"]

        if overall_status == "WAITING_APPROVAL":
            approval_notice = f"Discount request ({approval_amount:.0f}%) exceeds the 15% automatic limit. Waiting for human approval via Synapse."

        for step in secondary_res["steps"]:
            save_agent_step(run_id, "Pricing Agent", step_counter, step["action"], step["detail"])
            synapse_client.report_step(run_id, "Pricing Agent", step_counter, step["action"], step["detail"])
            all_steps.append({
                "step_number": step_counter,
                "agent_name": "Pricing Agent",
                "action": step["action"],
                "detail": step["detail"]
            })
            step_counter += 1

        agents_ran.append({
            "agent_name": "Pricing Agent",
            "status": secondary_res["status"],
            "input_tokens": secondary_res["input_tokens"],
            "output_tokens": secondary_res["output_tokens"],
            "cost_usd": secondary_res["cost_usd"],
            "latency_ms": secondary_res["latency_ms"]
        })

    elif intent == "billing":
        primary_agent = "Billing Agent"
        secondary_res = run_billing_agent(customer_name, message)
        final_reply = secondary_res["reply"]
        overall_status = secondary_res["status"]
        approval_type = secondary_res["approval_type"]
        approval_amount = secondary_res["approval_amount"]

        if overall_status == "WAITING_APPROVAL":
            approval_notice = f"Refund request of ${approval_amount:,.2f} exceeds the $100.00 limit. Waiting for human approval via Synapse."

        for step in secondary_res["steps"]:
            save_agent_step(run_id, "Billing Agent", step_counter, step["action"], step["detail"])
            synapse_client.report_step(run_id, "Billing Agent", step_counter, step["action"], step["detail"])
            all_steps.append({
                "step_number": step_counter,
                "agent_name": "Billing Agent",
                "action": step["action"],
                "detail": step["detail"]
            })
            step_counter += 1

        agents_ran.append({
            "agent_name": "Billing Agent",
            "status": secondary_res["status"],
            "input_tokens": secondary_res["input_tokens"],
            "output_tokens": secondary_res["output_tokens"],
            "cost_usd": secondary_res["cost_usd"],
            "latency_ms": secondary_res["latency_ms"]
        })

    total_in_tokens = sum(a["input_tokens"] for a in agents_ran)
    total_out_tokens = sum(a["output_tokens"] for a in agents_ran)
    total_cost = round(sum(a["cost_usd"] for a in agents_ran), 6)
    total_latency = round((time.time() - start_time) * 1000, 2)

    # Report completion to Synapse
    synapse_reported = synapse_client.finish_run(
        run_id=run_id,
        agent_name=primary_agent,
        status=overall_status,
        input_tokens=total_in_tokens,
        output_tokens=total_out_tokens,
        cost_usd=total_cost,
        latency_ms=total_latency,
        reply_text=final_reply,
        approval_type=approval_type,
        approval_amount=approval_amount
    )

    # Persist agent run in SQLite
    save_agent_run(
        run_id=run_id,
        customer_name=customer_name,
        user_message=message,
        agent_name=primary_agent,
        status=overall_status,
        input_tokens=total_in_tokens,
        output_tokens=total_out_tokens,
        cost_usd=total_cost,
        latency_ms=total_latency,
        reply_text=final_reply,
        approval_type=approval_type,
        approval_amount=approval_amount,
        synapse_reported=synapse_reported
    )

    return {
        "run_id": run_id,
        "customer_name": customer_name,
        "user_message": message,
        "primary_agent": primary_agent,
        "status": overall_status,
        "reply": final_reply,
        "approval_notice": approval_notice,
        "approval_type": approval_type,
        "approval_amount": approval_amount,
        "agents_ran": agents_ran,
        "steps": all_steps,
        "metrics": {
            "total_input_tokens": total_in_tokens,
            "total_output_tokens": total_out_tokens,
            "total_tokens": total_in_tokens + total_out_tokens,
            "total_cost_usd": total_cost,
            "total_latency_ms": total_latency
        }
    }
