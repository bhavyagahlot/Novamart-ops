# NovaMart Ops

Autonomous multi-agent customer operations platform for a modern online electronics store, governed and monitored via the **Synapse OS** control plane.

Built with **FastAPI**, **SQLite**, and **Google Gemini 1.5 Flash**, styled after the **Synapse OS** design system (*Instrument Serif*, *Inter*, *Fragment Mono*, `#3455fa` primary accent, and clean 12px rounded panels).

---

## Architecture & Autonomous Agents

NovaMart Ops orchestrates customer operations across 4 specialized AI agents:

1. **Triage Agent**: Inspects incoming customer intent and routes execution to Order, Pricing, or Billing agents. Inquiries regarding return policies, shipping times, or device warranties are answered directly via the embedded store policy knowledge base.
2. **Order Agent**: Parses item selections and quantities, verifies real-time stock levels in SQLite, decrements inventory upon fulfillment, and generates an order confirmation with transaction ID.
3. **Pricing Agent**: Reviews promotional and custom discount requests against the safety limit (`DISCOUNT_APPROVAL_LIMIT_PERCENT = 15%`). Inquiries above 15% are marked as `WAITING_APPROVAL` and escalated to human supervision.
4. **Billing Agent**: Evaluates returns, cancellations, and refunds against the spending limit (`REFUND_APPROVAL_LIMIT = $100`). Claims exceeding $100 are marked as `WAITING_APPROVAL` for human supervisor review.

Every agent invocation records:
- **Agent Name & Lifecycle Status** (`PROCESSING`, `COMPLETED`, `WAITING_APPROVAL`, `ERROR`)
- **Token Usage** (Prompt & Candidate tokens)
- **Estimated Cost in USD** (Gemini 1.5 Flash per-token pricing)
- **Latency (ms)**
- **Audit Steps** (persisted in SQLite and synced to Synapse)

---

## Synapse OS Integration

NovaMart Ops includes a lightweight Python SDK (`app/synapse_client.py`) that syncs all agent runs and reasoning steps to your external Synapse control platform over HTTP.

Configured endpoints:
```python
SYNAPSE_ENDPOINT_START_RUN    = "/api/v1/projects/{project_id}/runs"
SYNAPSE_ENDPOINT_RECORD_STEP  = "/api/v1/projects/{project_id}/runs/{run_id}/steps"
SYNAPSE_ENDPOINT_FINISH_RUN   = "/api/v1/projects/{project_id}/runs/{run_id}/finish"
SYNAPSE_ENDPOINT_GET_APPROVAL = "/api/v1/projects/{project_id}/runs/{run_id}/approval"
```

*Resilience Note*: If the external Synapse server is unreachable, the SDK gracefully logs a warning and allows local store operations and customer conversations to proceed uninterrupted.

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/<your-username>/novamart-ops.git
cd novamart-ops

# Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# Synapse Platform Monitoring Configuration
SYNAPSE_URL=http://localhost:9000
SYNAPSE_API_KEY=your_synapse_api_key_here
SYNAPSE_PROJECT_ID=novamart-ops

# Store Policy Limits
REFUND_APPROVAL_LIMIT=100
DISCOUNT_APPROVAL_LIMIT_PERCENT=15
```

> **Note**: If `GEMINI_API_KEY` is not provided, NovaMart Ops automatically engages intelligent local heuristic reasoning, allowing you to test all flows and UI features out of the box.

### 4. Run the Application
```bash
uvicorn app.main:app --reload --port 8000
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## Quick-Test Workflows

The web UI contains 4 interactive one-click test actions:

| Quick Action | Intent Routed | Outcome |
|---|---|---|
| **💻 Order a laptop** | `Order Agent` | Confirms order for *NovaBook Pro 16*, updates SQLite stock, status `COMPLETED` (green chip). |
| **🏷️ Ask for 30% off** | `Pricing Agent` | Exceeds 15% threshold; flags status `WAITING_APPROVAL` (amber chip) and shows Synapse manager banner. |
| **💸 Refund an expensive order** | `Billing Agent` | Exceeds $100 threshold ($1,299.99); flags status `WAITING_APPROVAL` (amber chip). |
| **❓ Ask a policy question** | `Triage Agent` | Answered directly from store policy without secondary dispatch; status `COMPLETED` (green chip). |

---

## Running the Automated Test Suite

Run the unit tests:
```bash
python tests/test_agents.py
python tests/test_api.py
```

---

## Project Structure
```text
novamart-ops/
├── app/
│   ├── __init__.py
│   ├── config.py             # Pydantic settings loading from .env
│   ├── database.py           # SQLite connection, schemas & seed catalog
│   ├── synapse_client.py     # Synapse OS SDK with endpoint constants & fallback
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── gemini_helper.py  # Gemini API calls, token counts & USD cost estimator
│   │   ├── triage_agent.py   # Intent routing (Order, Pricing, Billing, FAQ)
│   │   ├── order_agent.py    # Inventory check and order placement in SQLite
│   │   ├── pricing_agent.py  # Discount approval evaluator (threshold: 15%)
│   │   ├── billing_agent.py  # Refund approval evaluator (threshold: $100)
│   │   └── orchestrator.py   # Pipeline runner, trace collector & Synapse sync
│   └── main.py               # FastAPI application & API routes
├── static/
│   ├── index.html            # Synapse-styled two-panel dashboard
│   ├── styles.css            # Clean minimal styling, status chips & fonts
│   └── app.js                # Chat submission, trace rendering & stock updates
├── tests/
│   ├── test_agents.py        # Multi-agent flow verification
│   └── test_api.py           # FastAPI endpoints & static file tests
├── .env.example              # Committed config template with placeholders
├── .gitignore                # Excludes .env, *.db, venv, and __pycache__
├── requirements.txt          # Python dependencies
└── README.md                 # Documentation
```
