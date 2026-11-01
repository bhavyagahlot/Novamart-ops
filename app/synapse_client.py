"""Synapse HTTP Client SDK for NovaMart Ops

This client communicates with the external Synapse OS / monitoring platform.
It reports agent run lifecycle events (start, steps, end/metrics) and checks
for human approval decisions on runs in WAITING_APPROVAL status.
Includes circuit-breaker backoff so unreachable Synapse endpoints don't degrade latency.
"""

import time
import logging
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings

logger = logging.getLogger("novamart.synapse")

# ==============================================================================
# Synapse API Endpoints Configuration
# TODO: Confirm or customize the exact Synapse API endpoints below with your
# Synapse platform deployment specifications.
# ==============================================================================
SYNAPSE_RUNS_ENDPOINT = "/api/v1/runs"
SYNAPSE_STEPS_ENDPOINT = "/api/v1/runs/{run_id}/steps"
SYNAPSE_APPROVAL_ENDPOINT = "/api/v1/runs/{run_id}/approval"


class SynapseClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        self.base_url = (base_url or settings.SYNAPSE_URL).rstrip("/")
        self.api_key = api_key or settings.SYNAPSE_API_KEY
        self.project_id = project_id or settings.SYNAPSE_PROJECT_ID
        self.timeout = httpx.Timeout(connect=0.5, read=1.0, write=1.0, pool=0.5)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Project-ID": self.project_id,
            "Content-Type": "application/json",
            "User-Agent": "NovaMart-Ops/1.0.0"
        }
        # Circuit-breaker state
        self._is_reachable: bool = True
        self._last_failure_time: float = 0.0
        self._backoff_seconds: float = 30.0

    def _should_attempt_call(self) -> bool:
        if not self._is_reachable:
            if time.time() - self._last_failure_time > self._backoff_seconds:
                # Retry after backoff period
                self._is_reachable = True
                return True
            return False
        return True

    def _mark_failure(self, url: str, reason: str):
        if self._is_reachable:
            logger.warning(
                f"[Synapse Unreachable] Could not communicate with Synapse at {url}. "
                f"Reason: {reason}. Switching to offline fallback mode for {self._backoff_seconds}s."
            )
        self._is_reachable = False
        self._last_failure_time = time.time()

    def _safe_request(self, method: str, path: str, json_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Executes HTTP request to Synapse with graceful fallback and warning logs if unreachable."""
        if not self._should_attempt_call():
            return None

        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data
                )
                if response.is_success:
                    self._is_reachable = True
                    try:
                        return response.json()
                    except Exception:
                        return {"status": "ok"}
                else:
                    logger.warning(f"[Synapse] HTTP {response.status_code} from {url}: {response.text[:150]}")
                    return None
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as ex:
            self._mark_failure(url, str(ex))
            return None
        except Exception as ex:
            self._mark_failure(url, str(ex))
            return None

    def report_run_start(self, run_id: str, agent_name: str, conversation_id: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Reports the initiation of an agent run."""
        payload = {
            "run_id": run_id,
            "project_id": self.project_id,
            "agent_name": agent_name,
            "conversation_id": conversation_id,
            "status": "PROCESSING",
            "metadata": metadata or {}
        }
        return self._safe_request("POST", SYNAPSE_RUNS_ENDPOINT, payload)

    def report_run_step(self, run_id: str, step_name: str, status: str = "COMPLETED", details: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Reports an intermediate execution trace step for an agent."""
        path = SYNAPSE_STEPS_ENDPOINT.format(run_id=run_id)
        payload = {
            "step_name": step_name,
            "status": status,
            "details": details or {}
        }
        return self._safe_request("POST", path, payload)

    def report_run_end(
        self,
        run_id: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
        steps: List[Dict[str, Any]],
        output_text: str
    ) -> Optional[Dict[str, Any]]:
        """Reports the completion (or waiting approval / error) of an agent run with metrics."""
        path = f"{SYNAPSE_RUNS_ENDPOINT}/{run_id}"
        payload = {
            "status": status,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "steps": steps,
            "output_text": output_text
        }
        return self._safe_request("PATCH", path, payload)

    def check_approval(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Polls or checks Synapse for human approval decision on a WAITING_APPROVAL run."""
        path = SYNAPSE_APPROVAL_ENDPOINT.format(run_id=run_id)
        return self._safe_request("GET", path)


# Global default client instance
synapse_client = SynapseClient()
