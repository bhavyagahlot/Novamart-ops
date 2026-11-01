import time
import uuid
import logging
from typing import Dict, Any, List, Tuple
from app.config import settings
from app.db import record_agent_run
from app.synapse_client import synapse_client

logger = logging.getLogger("novamart.agents.common")

# Gemini pricing estimates (USD per token for Gemini 1.5 Flash)
PRICE_PER_INPUT_TOKEN = 0.075 / 1_000_000
PRICE_PER_OUTPUT_TOKEN = 0.30 / 1_000_000

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    return round((input_tokens * PRICE_PER_INPUT_TOKEN) + (output_tokens * PRICE_PER_OUTPUT_TOKEN), 6)

def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 characters per token) with minimum of 1."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def call_gemini(system_instruction: str, user_prompt: str) -> Tuple[str, int, int]:
    """
    Calls Gemini API if GEMINI_API_KEY is configured.
    Falls back gracefully if key is dummy/missing or network fails.
    Returns (response_text, input_tokens, output_tokens).
    """
    prompt_tokens = estimate_tokens(system_instruction) + estimate_tokens(user_prompt)

    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system_instruction
            )
            response = model.generate_content(user_prompt)
            out_text = response.text or ""
            
            # Extract usage metadata if available
            in_tok = prompt_tokens
            out_tok = estimate_tokens(out_text)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                in_tok = getattr(response.usage_metadata, "prompt_token_count", in_tok)
                out_tok = getattr(response.usage_metadata, "candidates_token_count", out_tok)
            return out_text.strip(), in_tok, out_tok
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Utilizing fallback logic.")

    # Standalone mock/fallback for offline/demo operation
    return "", prompt_tokens, 0

class AgentExecutionContext:
    def __init__(self, agent_name: str, conversation_id: str):
        self.agent_name = agent_name
        self.conversation_id = conversation_id
        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.start_time = time.time()
        self.steps: List[Dict[str, Any]] = []
        self.status = "PROCESSING"
        self.input_tokens = 0
        self.output_tokens = 0
        self.output_text = ""

        # Report initiation to Synapse
        synapse_client.report_run_start(self.run_id, self.agent_name, self.conversation_id)

    def add_step(self, step_name: str, status: str = "COMPLETED", details: Any = None):
        step_record = {
            "step": step_name,
            "status": status,
            "time_offset_ms": round((time.time() - self.start_time) * 1000, 1),
            "details": details or {}
        }
        self.steps.append(step_record)
        synapse_client.report_run_step(self.run_id, step_name, status, details)

    def finalize(self, status: str, output_text: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        self.status = status
        self.output_text = output_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        latency_ms = round((time.time() - self.start_time) * 1000, 2)
        cost_usd = calculate_cost(self.input_tokens, self.output_tokens)

        # Record in SQLite
        record_agent_run(
            run_id=self.run_id,
            conversation_id=self.conversation_id,
            agent_name=self.agent_name,
            status=self.status,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            steps=self.steps,
            output_text=self.output_text
        )

        # Report completion to Synapse
        synapse_client.report_run_end(
            run_id=self.run_id,
            status=self.status,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            steps=self.steps,
            output_text=self.output_text
        )

        return {
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "steps": self.steps,
            "output_text": self.output_text
        }
