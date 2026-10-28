import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.config import settings
from app.database import init_db, get_all_products, get_recent_runs, get_run_details
from app.agents.orchestrator import process_customer_message
from app.synapse_client import synapse_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("novamart.main")

# Initialize database tables and seed products on module load
init_db()

app = FastAPI(
    title="NovaMart Ops",
    description="Autonomous Multi-Agent E-Commerce Operations monitored via Synapse OS",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    customer_name: Optional[str] = Field(default="Alex Mercer")
    message: str

class ApprovalPollRequest(BaseModel):
    run_id: str

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    result = process_customer_message(req.customer_name or "Alex Mercer", req.message)
    return result

@app.get("/api/products")
def get_products_endpoint():
    return {"products": get_all_products()}

@app.get("/api/runs")
def get_runs_endpoint(limit: int = 10):
    return {"runs": get_recent_runs(limit=limit)}

@app.get("/api/runs/{run_id}")
def get_run_endpoint(run_id: str):
    run = get_run_details(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.get("/api/runs/{run_id}/synapse-approval")
def check_synapse_approval(run_id: str):
    """
    Polls the external Synapse platform for human approval status on this run.
    """
    decision = synapse_client.check_approval(run_id)
    return {
        "run_id": run_id,
        "synapse_url": settings.SYNAPSE_URL,
        "approval": decision or {"status": "PENDING", "source": "Synapse SDK fallback"}
    }

@app.get("/api/config")
def get_frontend_config():
    return {
        "synapse_url": settings.SYNAPSE_URL,
        "gemini_model": settings.GEMINI_MODEL,
        "refund_approval_limit": settings.REFUND_APPROVAL_LIMIT,
        "discount_approval_limit_percent": settings.DISCOUNT_APPROVAL_LIMIT_PERCENT
    }

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))
