"""Fireworks AI client wrapper (OpenAI-compatible).

Two backends behind one interface:
- Fireworks serverless (AMD-hosted models, billed per token)
- Optional self-hosted vLLM on an AMD MI300X (AMD Developer Cloud), free at the margin
"""
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_MODEL = os.getenv(
    "FIREWORKS_MODEL", "accounts/fireworks/models/gemma-3-27b-it"
)

_fireworks: OpenAI | None = None
_amd_vllm: OpenAI | None = None


def fireworks_client() -> OpenAI:
    global _fireworks
    if _fireworks is None:
        key = os.getenv("FIREWORKS_API_KEY")
        if not key:
            raise RuntimeError(
                "FIREWORKS_API_KEY missing. Copy .env.example to .env and set it."
            )
        _fireworks = OpenAI(base_url=FIREWORKS_BASE_URL, api_key=key)
    return _fireworks


def amd_vllm_client() -> OpenAI | None:
    """Self-hosted Gemma on AMD MI300X, if configured."""
    global _amd_vllm
    base = os.getenv("AMD_VLLM_BASE_URL")
    if not base:
        return None
    if _amd_vllm is None:
        _amd_vllm = OpenAI(base_url=base, api_key=os.getenv("AMD_VLLM_KEY", "none"))
    return _amd_vllm


def chat(
    message: str,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.4,
) -> dict:
    """Single-turn chat with token usage + latency accounting."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    t0 = time.perf_counter()
    resp = fireworks_client().chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000)

    usage = resp.usage
    return {
        "model": resp.model,
        "content": resp.choices[0].message.content,
        "latency_ms": latency_ms,
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
        },
    }
