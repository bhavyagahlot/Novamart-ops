# NovaMart Ops ⚡

An autonomous customer operations system for an online electronics retailer, driven by a 4-agent AI pipeline and monitored in real-time by the external [Synapse OS](https://synapse.example.com) platform via an HTTP SDK.

---

## 🌟 Overview & Architecture

NovaMart Ops coordinates four specialized AI agents using FastAPI, SQLite, and Google Gemini:

1. **Triage Agent**: Reads customer inquiries, extracts intent, answers store policy & warranty FAQs directly, or routes orders, discounts, and refunds to the specialist agent.
2. **Order Agent**: Inspects real-time inventory in SQLite (`NovaBook Pro`, `NovaPhone Ultra`, `NovaSound Headphones`, etc.), creates verified purchase orders, and automatically decrements stock.
3. **Pricing Agent**: Evaluates discount promo inquiries against business rules. Requests up to 15% are approved instantly. Requests over 15% are escalated to `WAITING_APPROVAL`.
4. **Billing Agent**: Evaluates refund requests. Refunds up to $100 are automatically refunded. Refunds over $100 are escalated to `WAITING_APPROVAL` for manager authorization.

Each agent run logs:
- **Status Chip**: `PROCESSING` (blue), `COMPLETED` (green), `ERROR` (red), `WAITING_APPROVAL` (amber)
- **Token Metrics**: Input tokens & output tokens
- **Financial Cost**: USD estimation based on Gemini token pricing
- **Latency**: Sub-second execution timing in milliseconds
- **Execution Step Trace**: Micro-step timeline of internal reasoning and database updates

---

## 🖥️ UI & Synapse OS Aesthetic

The interface is accessible at `http://localhost:8000`:
- **Left Column**: Customer interaction terminal, interactive customer name input, message box, and 4 one-click quick scenario tests.
- **Right Column**: Live agent trace listing the triage agent and delegated specialist agent, metrics bar, and execution sequence.
- **Approval Alerts**: Prominently warns the operator when a refund or discount exceeds threshold policy and is held in `WAITING_APPROVAL`.
- **Styling**: Synapse OS design language:
  - White background (`#ffffff`), soft panel backgrounds (`#f5f5f5`), 1px subtle borders (`#e8e8e8`).
  - Google Fonts: **Instrument Serif** for editorial titles, **Inter** for clean UI controls, and **Fragment Mono** for telemetry, IDs, and financial costs.
  - Primary color: `#3455fa`.

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.11 or newer
- Git

### 2. Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/Bhavyagahlot2007/novamart-ops.git
cd novamart-ops

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configuration
Copy the sample environment file:

```bash
# Windows
copy .env.example .env

# Linux/macOS
cp .env.example .env
```

Open `.env` and fill in your keys (the application works with built-in fallbacks if you don't have active keys yet):

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
SYNAPSE_URL=https://api.synapse.example.com
SYNAPSE_API_KEY=syn_demo_key_123456789
SYNAPSE_PROJECT_ID=novamart-ops-proj-001
REFUND_APPROVAL_LIMIT=100
DISCOUNT_APPROVAL_LIMIT_PERCENT=15
```

### 4. Running the Application
Start the FastAPI server:

```bash
uvicorn app.main:app --reload --port 8000
```

Open your browser to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Testing Quick Scenarios

Use the 4 buttons on the dashboard to test the agents:

1. **"Order a laptop"**
   - Routes: `Triage Agent` ➔ `Order Agent`
   - Outcome: Checks inventory for NovaBook Pro 16, creates Order #1004, decrements stock.
   - Status: `COMPLETED`
2. **"Ask for 30% off"**
   - Routes: `Triage Agent` ➔ `Pricing Agent`
   - Outcome: 30% > 15% limit. Agent denies instant approval.
   - Status: `WAITING_APPROVAL` (Amber notice shown to customer)
3. **"Refund an expensive order"**
   - Routes: `Triage Agent` ➔ `Billing Agent`
   - Outcome: Refund amount ($1,299.99) > $100 limit.
   - Status: `WAITING_APPROVAL` (Amber approval alert banner shown)
4. **"Ask a policy question"**
   - Routes: `Triage Agent` (direct answer)
   - Outcome: Answers 30-day return policy and 1-year warranty directly without delegating.
   - Status: `COMPLETED`

---

## 📡 Synapse Platform Integration

The `app/synapse_client.py` SDK reports run telemetry to your Synapse OS instance over HTTP.

Configurable constants located in `app/synapse_client.py`:
```python
SYNAPSE_RUNS_ENDPOINT = "/api/v1/runs"
SYNAPSE_STEPS_ENDPOINT = "/api/v1/runs/{run_id}/steps"
SYNAPSE_APPROVAL_ENDPOINT = "/api/v1/runs/{run_id}/approval"
```

If Synapse is offline or unreachable, NovaMart Ops safely logs a warning and continues processing customer requests seamlessly without disruption.
