"""Fireworks smoke test — run this the moment FIREWORKS_API_KEY lands in .env.

Verifies: auth works, which Gemma models are callable, one real completion
with latency + token usage. Exits non-zero on failure.

    uv run python scripts/smoke_test.py
"""
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.fireworks.ai/inference/v1"
KEY = os.getenv("FIREWORKS_API_KEY")

CANDIDATE_MODELS = [
    "accounts/fireworks/models/gemma-4-26b-a4b-it",
    "accounts/fireworks/models/gemma-4-31b-it",
    "accounts/fireworks/models/gemma-3-27b-it",
    "accounts/fireworks/models/gemma-3-4b-it",
    "accounts/fireworks/models/gpt-oss-20b",
]


def main() -> int:
    if not KEY:
        print("FAIL: FIREWORKS_API_KEY not set. Copy .env.example to .env first.")
        return 1

    headers = {"Authorization": f"Bearer {KEY}"}

    print("== 1/2: auth + model catalog ==")
    r = httpx.get(f"{BASE}/models", headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"FAIL: /models returned {r.status_code}: {r.text[:200]}")
        return 1
    ids = [m["id"] for m in r.json().get("data", [])]
    gemma = [i for i in ids if "gemma" in i.lower()]
    print(f"OK: auth valid, {len(ids)} models visible, gemma models: {gemma or 'none listed'}")

    print("== 2/2: live completion ==")
    for model in CANDIDATE_MODELS:
        t0 = time.perf_counter()
        resp = httpx.post(
            f"{BASE}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: AMD MI300X ready"}],
                "max_tokens": 16,
            },
            timeout=60,
        )
        ms = round((time.perf_counter() - t0) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            print(f"OK: {model}\n    -> {text!r} ({ms} ms, {usage.get('total_tokens')} tokens)")
            print("\nSMOKE TEST PASSED — environment is live.")
            return 0
        print(f"skip: {model} -> {resp.status_code}")

    print("FAIL: no candidate model answered. Check model ids in the Fireworks console.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
