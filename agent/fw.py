"""Async Fireworks client for the FourCast agent.

Credentials resolve in order: FIREWORKS_API_KEY env → T2_FW_KEY_B64 env
(base64, for the baked container) → .env file (local dev).
"""
import asyncio
import base64
import json
import os
import re
import sys

import httpx

try:  # .env is a local-dev convenience only
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_URL = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")

# Model matrix probed 2026-07-11 (scripts/model_matrix.py): kimi-k2p5 = 500s (dead),
# gpt-oss-120b fastest clean-JSON (1.6s), glm-5p2 2.1s, kimi-k2p6 vision OK (9s).
VISION_MODEL = os.getenv("T2_VISION_MODEL", "accounts/fireworks/models/kimi-k2p6")
VISION_FALLBACK = os.getenv("T2_VISION_FALLBACK") or None

# Gemma stylist path (opt-in) — unlocks the "Best Use of Gemma in Video Captioning"
# bonus. Set T2_USE_GEMMA=1 to route the stylist through Gemma on Fireworks while
# keeping Kimi vision + gpt-oss judge. GLM 5.2 stays the fallback, so if Gemma is
# unavailable on the key the pipeline degrades gracefully instead of failing.
USE_GEMMA = os.getenv("T2_USE_GEMMA") == "1"
GEMMA_MODEL = os.getenv("T2_GEMMA_MODEL", "accounts/fireworks/models/gemma-4-31b-it")

STYLIST_MODEL = os.getenv("T2_STYLIST_MODEL") or (
    GEMMA_MODEL if USE_GEMMA else "accounts/fireworks/models/glm-5p2"
)
STYLIST_FALLBACK = os.getenv("T2_STYLIST_FALLBACK") or (
    "accounts/fireworks/models/glm-5p2" if USE_GEMMA else "accounts/fireworks/models/kimi-k2p6"
)
JUDGE_MODEL = os.getenv("T2_JUDGE_MODEL", "accounts/fireworks/models/gpt-oss-120b")
JUDGE_FALLBACK = os.getenv("T2_JUDGE_FALLBACK", "accounts/fireworks/models/glm-5p1")

# --- Gemma on AMD Developer Cloud (self-hosted, for the "Best Use of Gemma" bonus) ---
# Fireworks serverless does not expose Gemma on every key, so the reliable Gemma
# route is a vLLM server on an AMD Instinct MI300X (ROCm). Point the stylist at it
# by setting AMD_VLLM_BASE_URL; GLM 5.2 on Fireworks stays the automatic fallback.
AMD_VLLM_BASE_URL = os.getenv("AMD_VLLM_BASE_URL") or None
AMD_VLLM_MODEL = os.getenv("AMD_VLLM_MODEL", "google/gemma-3-27b-it")
AMD_VLLM_KEY = os.getenv("AMD_VLLM_KEY", "EMPTY")

SKIP_API = os.getenv("SKIP_API") == "1"

_clients: dict[str, httpx.AsyncClient] = {}


def _api_key() -> str:
    key = os.getenv("FIREWORKS_API_KEY")
    if not key and os.getenv("T2_FW_KEY_B64"):
        key = base64.b64decode(os.environ["T2_FW_KEY_B64"]).decode()
    if not key:
        raise RuntimeError("No Fireworks credentials (FIREWORKS_API_KEY / T2_FW_KEY_B64)")
    return key


def client(base_url: str | None = None, api_key: str | None = None) -> httpx.AsyncClient:
    """Cached client per endpoint — Fireworks by default, or a self-hosted vLLM."""
    base = base_url or BASE_URL
    if base not in _clients:
        _clients[base] = httpx.AsyncClient(
            base_url=base,
            headers={"Authorization": f"Bearer {api_key or _api_key()}"},
            timeout=httpx.Timeout(75.0, connect=15.0),
        )
    return _clients[base]


async def chat(
    messages: list[dict],
    model: str,
    fallback_model: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.6,
    retries: int = 1,
    json_mode: bool = False,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """One chat completion, with retry then model fallback. Returns content str.

    json_mode uses Fireworks' response_format json_object; if a model rejects
    it (400), the same model is retried without it before falling back.
    """
    last_err: Exception | None = None
    for attempt_model in filter(None, [model, fallback_model]):
        use_json = json_mode
        for attempt in range(retries + 1):
            try:
                payload: dict = {
                    "model": attempt_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if use_json:
                    payload["response_format"] = {"type": "json_object"}
                r = await client(base_url, api_key).post("/chat/completions", json=payload)
                if r.status_code == 400 and use_json:
                    use_json = False  # model rejects response_format — retry plain
                    raise RuntimeError(f"{attempt_model} rejected json_mode: {r.text[:120]}")
                if r.status_code != 200:
                    raise RuntimeError(f"{attempt_model} -> {r.status_code}: {r.text[:160]}")
                msg = r.json()["choices"][0]["message"]
                content = msg.get("content") or ""
                if not content.strip():
                    raise RuntimeError(f"{attempt_model} returned empty content")
                return content
            except Exception as e:  # noqa: BLE001 — batch agent must never die on one call
                last_err = e
                print(f"[fw] {type(e).__name__} on {attempt_model} (try {attempt}): {e}", file=sys.stderr)
                await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"chat failed on {model} and fallback: {last_err}")


def vision_messages(system: str, user_text: str, frames: list[tuple[str, bytes]]) -> list[dict]:
    """Build messages with timestamped JPEG frames as data-URI image parts."""
    content: list[dict] = []
    for ts, jpeg in frames:
        b64 = base64.b64encode(jpeg).decode()
        content.append({"type": "text", "text": f"Frame at {ts}:"})
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )
    content.append({"type": "text", "text": user_text})
    return [{"role": "system", "content": system}, {"role": "user", "content": content}]


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_json_block(text: str) -> dict:
    """Tolerant JSON extraction for reasoning models.

    Strips think-blocks/fences, then scans every '{' and raw_decodes the first
    complete object — survives prose before AND after the JSON.
    """
    text = _THINK_RE.sub("", text).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        idx = text.find("{", idx + 1)
    print(f"[fw] unparseable reply head: {text[:200]!r}", file=sys.stderr)
    raise json.JSONDecodeError("no JSON object found", text[:50], 0)


async def aclose() -> None:
    for c in list(_clients.values()):
        await c.aclose()
    _clients.clear()
