"""Empirical model probe: which models return clean JSON, how fast, how chatty.

Tests every text model on a tiny JSON task and both Kimi models on a one-frame
vision JSON task. Prints verdicts so we can pick per-role models on evidence.

    uv run python scripts/model_matrix.py
"""
import asyncio
import sys
import time

sys.path.insert(0, ".")

from agent import fw  # noqa: E402
from agent.video import extract_frames  # noqa: E402

TEXT_MODELS = [
    "accounts/fireworks/models/gpt-oss-120b",
    "accounts/fireworks/models/glm-5p1",
    "accounts/fireworks/models/glm-5p2",
    "accounts/fireworks/models/deepseek-v4-pro",
    "accounts/fireworks/models/kimi-k2p5",
    "accounts/fireworks/models/kimi-k2p6",
]
VISION_MODELS = [
    "accounts/fireworks/models/kimi-k2p5",
    "accounts/fireworks/models/kimi-k2p6",
]

TEXT_TASK = [
    {"role": "system", "content": "Reply with the requested JSON object and nothing else."},
    {"role": "user", "content": 'Score these two captions for a cat video on humour 0-1. '
     'A: "cat exists". B: "This cat pays rent in cuteness and is three months behind." '
     'Return JSON: {"scores": [{"i": 0, "humour": 0.0}, {"i": 1, "humour": 0.0}], "best": 0}'},
]

KITTEN = "https://storage.googleapis.com/amd-hackathon-clips/13825391-uhd_3840_2160_30fps.mp4"

VISION_TASK_TEXT = ('Describe this frame. Return JSON only: '
                    '{"summary": "...", "subjects": ["..."]}')


async def probe(model: str, messages: list[dict], json_mode: bool) -> str:
    t0 = time.perf_counter()
    try:
        raw = await fw.chat(messages, model, None, max_tokens=2500,
                            temperature=0.2, retries=0, json_mode=json_mode)
        ms = (time.perf_counter() - t0) * 1000
        try:
            fw.parse_json_block(raw)
            head = raw.strip()[:70].replace("\n", " ")
            return f"JSON_OK   {ms:6.0f}ms  starts: {head!r}"
        except Exception:  # noqa: BLE001
            return f"NO_JSON   {ms:6.0f}ms  head: {raw.strip()[:90]!r}"
    except Exception as e:  # noqa: BLE001
        return f"CALL_FAIL {str(e)[:110]}"


async def main() -> None:
    print("== TEXT JSON task (json_mode=True) ==")
    results = await asyncio.gather(*(probe(m, TEXT_TASK, True) for m in TEXT_MODELS))
    for m, r in zip(TEXT_MODELS, results):
        print(f"{m.split('/')[-1]:>18}: {r}")

    print("\n== VISION JSON task (1 frame, json_mode=True) ==")
    frames = (await extract_frames(KITTEN))[:1]
    msgs = fw.vision_messages("Reply with the requested JSON object and nothing else.",
                              VISION_TASK_TEXT, frames)
    results = await asyncio.gather(*(probe(m, msgs, True) for m in VISION_MODELS))
    for m, r in zip(VISION_MODELS, results):
        print(f"{m.split('/')[-1]:>18}: {r}")

    await fw.aclose()


if __name__ == "__main__":
    asyncio.run(main())
