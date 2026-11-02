import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.config import settings
from app.db import (
    init_db,
    get_products,
    get_agent_runs_by_conversation,
    get_analytics_summary,
    get_request_history,
    update_approval_decision,
    get_all_orders
)
from app.agents import (
    run_triage_agent,
    run_order_agent,
    run_pricing_agent,
    run_billing_agent
)
from app.agents.common import is_kill_switch_active, set_kill_switch
from app.synapse_client import synapse_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("novamart.main")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite tables and seed data
    init_db()
    logger.info("NovaMart Ops initialized successfully.")
    yield

app = FastAPI(
    title="NovaMart Ops",
    description="Customer Operations Multi-Agent System with Synapse Integration",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class ChatRequest(BaseModel):
    customer_name: Optional[str] = Field(default="Alex Rivera", description="Customer's display name")
    message: str = Field(..., min_length=1, description="Customer message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation identifier")

class ChatResponse(BaseModel):
    conversation_id: str
    customer_name: str
    reply: str
    requires_approval: bool
    approval_notice: Optional[str] = None
    runs: List[Dict[str, Any]]

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index file not found")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/synapse-dashboard", response_class=HTMLResponse)
def serve_synapse_dashboard():
    dash_file = STATIC_DIR / "synapse_dashboard.html"
    if not dash_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard file not found")
    return HTMLResponse(content=dash_file.read_text(encoding="utf-8"))

# ==========================================
# Synapse Platform Simulation API Endpoints
# ==========================================

@app.get("/api/v1/runs")
def list_synapse_runs(limit: int = 50):
    from app.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/v1/runs")
def synapse_create_run(payload: Dict[str, Any]):
    return {"status": "ACKNOWLEDGED", "run_id": payload.get("run_id")}

@app.post("/api/v1/runs/{run_id}/steps")
def synapse_record_step(run_id: str, payload: Dict[str, Any]):
    return {"status": "RECORDED", "run_id": run_id}

@app.patch("/api/v1/runs/{run_id}")
def synapse_update_run(run_id: str, payload: Dict[str, Any]):
    return {"status": "UPDATED", "run_id": run_id}

@app.get("/api/v1/runs/{run_id}/approval")
def synapse_get_approval(run_id: str):
    from app.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM agent_runs WHERE id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"run_id": run_id, "status": row["status"]}
    return {"run_id": run_id, "status": "UNKNOWN"}

class ApprovalDecisionRequest(BaseModel):
    decision: str
    note: Optional[str] = None

@app.post("/api/v1/runs/{run_id}/approval")
def synapse_post_approval(run_id: str, req: ApprovalDecisionRequest):
    from app.db import get_connection
    new_status = "COMPLETED" if req.decision.upper() == "APPROVED" else "REJECTED"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agent_runs SET status = ? WHERE id = ?", (new_status, run_id))
    conn.commit()
    conn.close()
    return {"run_id": run_id, "status": new_status, "decision": req.decision}

@app.get("/api/analytics")
def get_analytics():
    """Returns real operational metrics aggregated from SQLite."""
    return get_analytics_summary()

@app.get("/api/history")
def get_history(
    search: Optional[str] = None,
    status: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 50
):
    """Returns conversation request history with search & filters."""
    return get_request_history(search=search, status_filter=status, agent_filter=agent, limit=limit)

@app.get("/api/orders")
def list_orders(limit: int = 50):
    """Returns recent customer orders."""
    return get_all_orders(limit=limit)

@app.get("/api/approvals")
def list_pending_approvals():
    """Returns all runs waiting for human manager authorization."""
    from app.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT * FROM agent_runs 
    WHERE status = 'WAITING_APPROVAL' 
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

class KillSwitchPayload(BaseModel):
    active: bool

@app.get("/api/killswitch")
def get_killswitch_status():
    return {"active": is_kill_switch_active()}

@app.post("/api/killswitch")
def set_killswitch_status(payload: KillSwitchPayload):
    new_state = set_kill_switch(payload.active)
    return {"active": new_state, "message": f"Kill switch is now {'ACTIVATED (emergency halt)' if new_state else 'DEACTIVATED (normal)'}"}

class SettingsUpdatePayload(BaseModel):
    refund_approval_limit: Optional[float] = None
    discount_approval_limit_percent: Optional[float] = None
    gemini_model: Optional[str] = None
    synapse_url: Optional[str] = None

@app.get("/api/settings")
def get_settings():
    return {
        "refund_approval_limit": settings.REFUND_APPROVAL_LIMIT,
        "discount_approval_limit_percent": settings.DISCOUNT_APPROVAL_LIMIT_PERCENT,
        "gemini_model": settings.GEMINI_MODEL,
        "synapse_url": settings.SYNAPSE_URL,
        "synapse_project_id": settings.SYNAPSE_PROJECT_ID,
        "kill_switch_active": is_kill_switch_active(),
        "database_path": settings.DATABASE_PATH
    }

@app.post("/api/settings")
def update_settings(payload: SettingsUpdatePayload):
    if payload.refund_approval_limit is not None:
        settings.REFUND_APPROVAL_LIMIT = payload.refund_approval_limit
    if payload.discount_approval_limit_percent is not None:
        settings.DISCOUNT_APPROVAL_LIMIT_PERCENT = payload.discount_approval_limit_percent
    if payload.gemini_model is not None:
        settings.GEMINI_MODEL = payload.gemini_model
    if payload.synapse_url is not None:
        settings.SYNAPSE_URL = payload.synapse_url
    return {"status": "UPDATED", "settings": get_settings()}

@app.get("/api/config")
def get_public_config():
    return {
        "synapse_url": settings.SYNAPSE_URL,
        "synapse_project_id": settings.SYNAPSE_PROJECT_ID,
        "refund_approval_limit": settings.REFUND_APPROVAL_LIMIT,
        "discount_approval_limit_percent": settings.DISCOUNT_APPROVAL_LIMIT_PERCENT,
        "gemini_model": settings.GEMINI_MODEL
    }

@app.get("/api/products")
def list_products():
    return get_products()

@app.get("/api/trace/{conversation_id}")
def get_trace(conversation_id: str):
    return get_agent_runs_by_conversation(conversation_id)

@app.get("/api/approval/{run_id}")
def check_run_approval(run_id: str):
    result = synapse_client.check_approval(run_id)
    if result is None:
        return {"run_id": run_id, "status": "WAITING_APPROVAL", "message": "Synapse monitoring platform offline or pending review."}
    return result

@app.post("/api/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest):
    conv_id = req.conversation_id or f"conv_{uuid.uuid4().hex[:10]}"
    customer = req.customer_name.strip() if req.customer_name and req.customer_name.strip() else "Customer"
    msg = req.message.strip()

    runs: List[Dict[str, Any]] = []
    final_reply = ""
    requires_approval = False
    approval_notice = None

    # Step 1: Run Triage Agent
    triage_result, triage_run = run_triage_agent(customer, msg, conv_id)
    runs.append(triage_run)

    route = triage_result.get("route")

    # Step 2: Route or Execute Specialist Agent
    if route == "killswitch":
        final_reply = triage_result.get("reply", "Automated operations halted by Emergency Kill Switch.")
        requires_approval = False

    elif route == "policy_faq":
        final_reply = triage_result.get("reply", "Here is our store policy.")
        requires_approval = False

    elif route == "order":
        order_result, order_run = run_order_agent(customer, msg, conv_id)
        runs.append(order_run)
        final_reply = order_result.get("reply", "Order processed.")
        requires_approval = False

    elif route == "pricing":
        pricing_result, pricing_run = run_pricing_agent(customer, msg, conv_id)
        runs.append(pricing_run)
        final_reply = pricing_result.get("reply", "Pricing inquiry processed.")
        requires_approval = pricing_result.get("requires_approval", False)
        if requires_approval:
            approval_notice = (
                f"Discount Approval Required: Requested discount ({pricing_result.get('requested_percent'):.0f}%) "
                f"exceeds the automatic authorization threshold of {pricing_result.get('limit_percent'):.0f}%."
            )

    elif route == "billing":
        billing_result, billing_run = run_billing_agent(customer, msg, conv_id)
        runs.append(billing_run)
        final_reply = billing_result.get("reply", "Billing inquiry processed.")
        requires_approval = billing_result.get("requires_approval", False)
        if requires_approval:
            approval_notice = (
                f"Billing Approval Required: Disputed/refund amount (${billing_result.get('amount', 0):,.2f}) "
                f"exceeds the automated ceiling limit of ${billing_result.get('limit', 0):,.2f}."
            )

    else:
        final_reply = "We have received your message and an agent will assist you shortly."

    return ChatResponse(
        conversation_id=conv_id,
        customer_name=customer,
        reply=final_reply,
        requires_approval=requires_approval,
        approval_notice=approval_notice,
        runs=runs
    )
