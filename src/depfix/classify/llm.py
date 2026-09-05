"""LLM seam for the release-notes classification path.

Deterministic spec-diff classification (``spec_rules.py``) never touches this
module — it exists only so ``notes.py`` can ask a model to read prose release
notes and propose structured changes, which are then gated by an
anti-hallucination verbatim-quote check before being trusted.

``temperature=0`` on every call: eval scores need to be stable run-to-run,
and classification is not a task where creative sampling helps.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from depfix.fixers.gemini import GEMINI_PRICING

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    duration_ms: int = 0


class LLMCompleter(Protocol):
    """Structural type for anything that can answer a classification prompt."""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse: ...


class GeminiCompleter:
    """Calls Gemini. Pricing table is shared with ``fixers.gemini`` — one
    source of truth for per-model rates rather than a second copy to drift."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash") -> None:
        if genai is None:
            raise RuntimeError("google.generativeai not installed. Install 'google-generativeai'.")
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Google API key not provided (GOOGLE_API_KEY or api_key param)")
        genai.configure(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        start = time.time()
        client = genai.GenerativeModel(self.model)
        response = client.generate_content(prompt, generation_config={"temperature": temperature})
        duration_ms = int((time.time() - start) * 1000)

        try:
            text = response.text
        except Exception:
            text = ""
            if getattr(response, "candidates", None):
                parts = getattr(response.candidates[0].content, "parts", None) or []
                text = "".join(getattr(p, "text", "") for p in parts)

        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        pricing = GEMINI_PRICING.get(self.model, {"input": 1.5, "output": 10.0})
        cost = (input_tokens / 1_000_000) * pricing["input"] + (
            output_tokens / 1_000_000
        ) * pricing["output"]

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=cost,
            duration_ms=duration_ms,
        )


class OllamaCompleter:
    """Calls a local Ollama server. Cost is always zero (local inference)."""

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, prompt: str, *, temperature: float = 0.0) -> LLMResponse:
        start = time.time()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        duration_ms = int((time.time() - start) * 1000)
        return LLMResponse(
            text=data.get("response", ""),
            input_tokens=int(data.get("prompt_eval_count", 0) or 0),
            output_tokens=int(data.get("eval_count", 0) or 0),
            cost_estimate=0.0,
            duration_ms=duration_ms,
        )
