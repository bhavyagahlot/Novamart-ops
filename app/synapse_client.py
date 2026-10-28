import logging
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("novamart.synapse")

# ==============================================================================
# Synapse API Endpoints (Configurable Constants)
# TODO: Update or confirm these Synapse endpoints with your Synapse platform specification.
# ==============================================================================
SYNAPSE_ENDPOINT_START_RUN    = "/api/v1/projects/{project_id}/runs"
SYNAPSE_ENDPOINT_RECORD_STEP  = "/api/v1/projects/{project_id}/runs/{run_id}/steps"
SYNAPSE_ENDPOINT_FINISH_RUN   = "/api/v1/projects/{project_id}/runs/{run_id}/finish"
SYNAPSE_ENDPOINT_GET_APPROVAL = "/api/v1/projects/{project_id}/runs/{run_id}/approval"
# ==============================================================================

class SynapseClient:
    """
    Python SDK client for reporting agent operations and approval status
    to the external Synapse OS control plane.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        timeout: float = 0.5
    ):
        self.base_url = (base_url or settings.SYNAPSE_URL or "").rstrip("/")
        self.api_key = api_key or settings.SYNAPSE_API_KEY or ""
        self.project_id = project_id or settings.SYNAPSE_PROJECT_ID or "novamart-ops"
        self.timeout = timeout
        self._synapse_offline = False

    @property
    def headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NovaMartOps-SynapseClient/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-Synapse-Api-Key"] = self.api_key
        return headers

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _safe_post(self, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            logger.debug("Synapse URL not configured; skipping sync.")
            return None
        if self._synapse_offline:
            logger.debug("Synapse marked offline; skipping request.")
            return None
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=self.headers)
                if resp.status_code in (200, 201, 202):
                    return resp.json() if resp.text else {"status": "ok"}
                logger.warning(
                    f"Synapse responded with HTTP {resp.status_code} for POST {url}: {resp.text[:120]}"
                )
        except Exception as exc:
            self._synapse_offline = True
            logger.warning(f"Could not reach Synapse platform at {url}: {exc}. Marking Synapse offline for this session.")
        return None

    def _safe_get(self, path: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured() or self._synapse_offline:
            return None
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Synapse responded with HTTP {resp.status_code} for GET {url}")
        except Exception as exc:
            self._synapse_offline = True
            logger.warning(f"Could not reach Synapse platform at {url}: {exc}. Marking Synapse offline for this session.")
        return None

    def start_run(
        self,
        run_id: str,
        agent_name: str,
        customer_name: str,
        user_message: str
    ) -> bool:
        """Report agent run start to Synapse."""
        path = SYNAPSE_ENDPOINT_START_RUN.format(project_id=self.project_id)
        payload = {
            "run_id": run_id,
            "project_id": self.project_id,
            "agent_name": agent_name,
            "customer_name": customer_name,
            "user_message": user_message,
            "status": "PROCESSING"
        }
        res = self._safe_post(path, payload)
        return res is not None

    def report_step(
        self,
        run_id: str,
        agent_name: str,
        step_number: int,
        action: str,
        detail: str
    ) -> bool:
        """Report a step in the agent reasoning/execution pipeline."""
        path = SYNAPSE_ENDPOINT_RECORD_STEP.format(project_id=self.project_id, run_id=run_id)
        payload = {
            "run_id": run_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "action": action,
            "detail": detail
        }
        res = self._safe_post(path, payload)
        return res is not None

    def finish_run(
        self,
        run_id: str,
        agent_name: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
        reply_text: str,
        approval_type: Optional[str] = None,
        approval_amount: Optional[float] = None
    ) -> bool:
        """Report agent completion and metrics to Synapse."""
        path = SYNAPSE_ENDPOINT_FINISH_RUN.format(project_id=self.project_id, run_id=run_id)
        payload = {
            "run_id": run_id,
            "agent_name": agent_name,
            "status": status,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "reply_text": reply_text,
            "approval_type": approval_type,
            "approval_amount": approval_amount
        }
        res = self._safe_post(path, payload)
        return res is not None

    def check_approval(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Poll or check human approval decision for a WAITING_APPROVAL run."""
        path = SYNAPSE_ENDPOINT_GET_APPROVAL.format(project_id=self.project_id, run_id=run_id)
        return self._safe_get(path)

# Global default client instance
synapse_client = SynapseClient()
