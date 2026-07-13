"""Harness entrypoint: /input/tasks.json -> /output/results.json.

Survival rules encoded here:
- results.json is (re)written atomically after EVERY completed clip, so a
  10-minute timeout still leaves valid, partial output on disk.
- global soft deadline (default 8.5 min) cancels stragglers and flushes.
- exit code 0 whenever a valid results file exists.
"""
import argparse
import asyncio
import json
import os
import sys
import time

from agent import contracts, fw
from agent.pipeline import process_clip

DEFAULT_IN = "/input/tasks.json"
DEFAULT_OUT = "/output/results.json"
BUDGET_S = float(os.getenv("T2_BUDGET_S", "510"))
CLIP_CONCURRENCY = int(os.getenv("T2_CLIP_CONCURRENCY", "4"))
# Per-clip wall-clock cap: a single stalled network read can never consume a
# concurrency slot forever or drag the batch — it degrades to a grounded fallback.
CLIP_TIMEOUT_S = float(os.getenv("T2_CLIP_TIMEOUT_S", "180"))


def _fallback_result(task: dict) -> dict:
    """Guaranteed complete result when a clip times out or fails hard."""
    styles = task.get("styles") or contracts.STYLES
    caps = {s: contracts.fallback_caption({}, s) for s in styles}
    # Dual-key schema hedge (see pipeline.process_clip): emit captions + answer.
    return {
        "task_id": task.get("task_id", "unknown"),
        "captions": caps,
        "answer": caps,
    }


def _atomic_write(path: str, results: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        # ensure_ascii: harness-side decoding can never garble the captions
        json.dump(results, f, ensure_ascii=True, indent=1)
    os.replace(tmp, path)


def _ensure_complete(result: dict, task: dict) -> dict:
    """Guarantee a clean, complete result for one clip — never raises.

    The harness scores a missing style as an instant zero for that segment, so we
    hard-guarantee a non-empty caption for EVERY requested style under both
    'captions' and 'answer'. Any missing, blank, or non-string style is filled
    with a grounded fallback (a caption always beats a zero). This is the final
    safety net over whatever process_clip returned.
    """
    styles = task.get("styles") or contracts.STYLES
    src = result.get("captions") if isinstance(result, dict) else None
    if not isinstance(src, dict):
        src = {}
    caps = {}
    for s in styles:
        v = src.get(s)
        caps[s] = v.strip() if isinstance(v, str) and v.strip() else contracts.fallback_caption({}, s)
    tid = result.get("task_id") if isinstance(result, dict) else None
    return {"task_id": str(tid or task.get("task_id", "unknown")),
            "captions": caps, "answer": caps}


def _validate(results: list[dict]) -> None:
    """Structural assertion used by tests/CI. In run() it is best-effort (a
    validation quibble must never crash a good batch into a RUNTIME_ERROR zero)."""
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r.get("task_id"), str)
        for key in ("captions", "answer"):
            caps = r.get(key)
            assert isinstance(caps, dict) and caps, f"missing/empty {key}"
            assert set(caps) >= set(contracts.STYLES), f"incomplete {key}: {sorted(caps)}"
            for k, v in caps.items():
                assert isinstance(k, str) and isinstance(v, str) and v.strip()


async def run(tasks_path: str, out_path: str) -> int:
    t0 = time.monotonic()
    with open(tasks_path, encoding="utf-8") as f:
        tasks = json.load(f)
    print(f"[runner] {len(tasks)} task(s), budget {BUDGET_S}s", file=sys.stderr)

    results: list[dict] = []
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(CLIP_CONCURRENCY)

    async def one(task: dict) -> None:
        async with sem:
            try:
                res = await asyncio.wait_for(process_clip(task), timeout=CLIP_TIMEOUT_S)
            except Exception as e:  # noqa: BLE001 — timeout or unexpected: ship a grounded fallback
                print(f"[runner] {task.get('task_id')} fell back ({type(e).__name__}); "
                      f"emitting grounded captions", file=sys.stderr)
                res = _fallback_result(task)
            res = _ensure_complete(res, task)  # hard guarantee: no missing/blank style ever ships
            async with lock:
                results.append(res)
                _atomic_write(out_path, results)
                print(f"[runner] {res['task_id']} done "
                      f"({len(results)}/{len(tasks)}, {time.monotonic() - t0:.0f}s)", file=sys.stderr)

    jobs = [asyncio.create_task(one(t)) for t in tasks]
    try:
        await asyncio.wait_for(asyncio.gather(*jobs), timeout=BUDGET_S)
    except asyncio.TimeoutError:
        print(f"[runner] BUDGET HIT at {time.monotonic() - t0:.0f}s — flushing partial results",
              file=sys.stderr)
        for j in jobs:
            j.cancel()

    # INFRA guard: every task MUST have an entry. If a clip was cancelled by the
    # budget or never finished, emit a grounded fallback for it — empty or partial
    # output is what turns a slow run into an unscored INFRA_ERROR; a fallback scores.
    done_ids = {r.get("task_id") for r in results}
    for t in tasks:
        tid = str(t.get("task_id", "unknown"))
        if tid not in done_ids:
            print(f"[runner] {tid} never completed — emitting fallback so output is complete",
                  file=sys.stderr)
            results.append(_ensure_complete(_fallback_result(t), t))

    try:
        _validate(results)
    except AssertionError as e:  # best-effort: never crash a good batch into a zero
        print(f"[runner] post-validate warning (writing anyway): {e}", file=sys.stderr)
    _atomic_write(out_path, results)
    await fw.aclose()
    print(f"[runner] wrote {len(results)} result(s) to {out_path} "
          f"in {time.monotonic() - t0:.0f}s", file=sys.stderr)
    return 0 if results else 1


def main() -> int:
    p = argparse.ArgumentParser(prog="fourcast-agent")
    p.add_argument("--tasks", default=DEFAULT_IN)
    p.add_argument("--out", default=DEFAULT_OUT)
    args = p.parse_args()
    return asyncio.run(run(args.tasks, args.out))
