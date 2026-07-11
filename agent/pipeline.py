"""Per-clip pipeline: Ground -> Generate -> Judge -> Refine.

Every stage degrades gracefully; a clip ALWAYS returns a full captions dict
(worst case: deterministic fallbacks). Missing styles score zero — never allowed.
"""
import asyncio
import json
import os
import sys

from agent import contracts, fw
from agent.video import extract_frames

ACC_THRESHOLD = 0.85
STYLE_THRESHOLD = 0.85

# Per-style sampling temperature: cool + precise for formal, warmer for the
# humorous tones where lexical variety is the point.
STYLE_TEMPS = {
    "formal": 0.35,
    "sarcastic": 0.8,
    "humorous_tech": 0.9,
    "humorous_non_tech": 0.9,
}

# Leaderboard lesson: elaborate self-judge/refine loops that miss the time budget
# score WORSE than a simple accurate pass. Refinement is therefore best-effort and
# can be disabled globally (T2_FAST=1) or skipped per-clip when time is short.
FAST = os.getenv("T2_FAST") == "1"


async def perceive(url: str) -> dict:
    frames = await extract_frames(url)
    if fw.SKIP_API:
        return {"summary": f"Stub scene for {url} ({len(frames)} frames).",
                "subjects": ["stub"], "actions": ["stub"], "setting": "stub",
                "on_screen_text": [], "camera": "static", "mood": "neutral",
                "distinctive_details": ["stub"]}
    msgs = fw.vision_messages(
        contracts.PERCEIVER_SYSTEM,
        contracts.PERCEIVER_USER.format(n=len(frames)),
        frames,
    )
    raw = await fw.chat(msgs, fw.VISION_MODEL, fw.VISION_FALLBACK,
                        max_tokens=4000, temperature=0.2, retries=2, json_mode=True)
    return fw.parse_json_block(raw)


async def _generate(scene_json: str, style: str, k: int = 3,
                    temperature: float | None = None) -> list[str]:
    msgs = [
        {"role": "system", "content": contracts.STYLIST_SYSTEM},
        {"role": "user", "content": contracts.STYLIST_USER.format(
            scene_report=scene_json, k=k, style_name=style,
            contract=contracts.STYLE_CONTRACTS[style])},
    ]
    raw = await fw.chat(msgs, fw.STYLIST_MODEL, fw.STYLIST_FALLBACK,
                        max_tokens=1600,
                        temperature=temperature if temperature is not None
                        else STYLE_TEMPS.get(style, 0.9),
                        json_mode=True)
    cands = [c.strip() for c in fw.parse_json_block(raw).get("candidates", []) if c.strip()]
    if not cands:
        raise RuntimeError(f"stylist returned no candidates for {style}")
    return cands


def _firewall(style: str, candidates: list[str]) -> list[str]:
    """Hard regex guard: drop humorous_non_tech candidates containing jargon."""
    if style != "humorous_non_tech":
        return candidates
    clean = [c for c in candidates if not contracts.jargon_violations(c)]
    return clean or candidates  # never end up empty; judge will punish leftovers


async def _judge(scene_json: str, style: str, candidates: list[str]) -> dict:
    block = "\n".join(f"[{i}] {c}" for i, c in enumerate(candidates))
    msgs = [
        {"role": "system", "content": contracts.JUDGE_SYSTEM},
        {"role": "user", "content": contracts.JUDGE_USER.format(
            scene_report=scene_json, contract=contracts.STYLE_CONTRACTS[style],
            candidates_block=block)},
    ]
    raw = await fw.chat(msgs, fw.JUDGE_MODEL, fw.JUDGE_FALLBACK,
                        max_tokens=1400, temperature=0.1, json_mode=True)
    return fw.parse_json_block(raw)


async def caption_style(scene: dict, style: str, allow_refine: bool = True,
                        temperature: float | None = None) -> dict:
    """Best caption for one style, with the internal judge's scores attached.

    temperature overrides the per-style default (demo UI creativity slider);
    the harness path never passes it, so leaderboard behaviour is unchanged.
    """
    scene_json = json.dumps(scene, ensure_ascii=False)
    if fw.SKIP_API:
        return {"text": contracts.fallback_caption(scene, style), "accuracy": 0.0, "style": 0.0}

    candidates = _firewall(style, await _generate(scene_json, style, temperature=temperature))
    verdict = await _judge(scene_json, style, candidates)
    scores = {s["i"]: s for s in verdict.get("scores", []) if isinstance(s, dict) and "i" in s}
    best_i = verdict.get("best", 0)
    best_i = best_i if isinstance(best_i, int) and 0 <= best_i < len(candidates) else 0
    best = candidates[best_i]
    acc = float(scores.get(best_i, {}).get("accuracy", 0.7))
    sty = float(scores.get(best_i, {}).get("style", 0.7))

    if allow_refine and not FAST and (acc < ACC_THRESHOLD or sty < STYLE_THRESHOLD):
        try:
            msgs = [
                {"role": "system", "content": contracts.STYLIST_SYSTEM},
                {"role": "user", "content": contracts.REFINE_USER.format(
                    style_name=style, acc=acc, sty=sty,
                    critique=verdict.get("critique_for_retry", "be more specific and on-tone"),
                    scene_report=scene_json,
                    contract=contracts.STYLE_CONTRACTS[style], k=2)},
            ]
            raw = await fw.chat(msgs, fw.STYLIST_MODEL, fw.STYLIST_FALLBACK,
                                max_tokens=1200, temperature=0.9, json_mode=True)
            retry_cands = _firewall(style, [c.strip() for c in
                                            fw.parse_json_block(raw).get("candidates", []) if c.strip()])
            pool = [best] + retry_cands
            verdict2 = await _judge(scene_json, style, pool)
            scores2 = {s["i"]: s for s in verdict2.get("scores", []) if isinstance(s, dict) and "i" in s}
            b2 = verdict2.get("best", 0)
            if isinstance(b2, int) and 0 <= b2 < len(pool):
                best = pool[b2]
                acc = float(scores2.get(b2, {}).get("accuracy", acc))
                sty = float(scores2.get(b2, {}).get("style", sty))
        except Exception as e:  # noqa: BLE001 — refinement is best-effort
            print(f"[pipeline] refine failed for {style}: {e}", file=sys.stderr)

    return {"text": best, "accuracy": acc, "style": sty}


async def process_clip_verbose(task: dict) -> tuple[dict, dict]:
    """(scene_report, {style: {text, accuracy, style}}) — demo UI uses everything."""
    task_id = task.get("task_id", "unknown")
    styles = task.get("styles") or contracts.STYLES
    url = task["video_url"]

    scene: dict = {}
    try:
        scene = await perceive(url)
        print(f"[pipeline] {task_id} scene ok: {str(scene.get('summary'))[:80]}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[pipeline] {task_id} PERCEIVE FAILED: {e}", file=sys.stderr)

    async def one(style: str) -> tuple[str, dict]:
        try:
            if not scene:
                raise RuntimeError("no scene report")
            return style, await caption_style(scene, style)
        except Exception as e:  # noqa: BLE001
            print(f"[pipeline] {task_id}/{style} fell back: {e}", file=sys.stderr)
            return style, {"text": contracts.fallback_caption(scene, style),
                           "accuracy": 0.0, "style": 0.0}

    pairs = await asyncio.gather(*(one(s) for s in styles))
    return scene, dict(pairs)


async def process_clip(task: dict) -> dict:
    """Harness contract: one task in -> guaranteed complete result out."""
    _, detailed = await process_clip_verbose(task)
    return {
        "task_id": task.get("task_id", "unknown"),
        "captions": {style: d["text"] for style, d in detailed.items()},
    }
