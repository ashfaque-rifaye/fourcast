# FourCast — four voices for every video

> AMD Developer Hackathon: ACT II · Track 2 (Video Captioning) · Team **mindflayer**
> One clip in, every voice out: grounded captions in `formal`, `sarcastic`, `humorous_tech`, and `humorous_non_tech` — each one self-judged before it ships.

## Why FourCast scores

Most captioning pipelines are a prompt wrapper: frames → VLM → "be funny". FourCast is a **caption factory with quality control**:

1. **Ground** — frames are sampled straight off the video URL (`ffmpeg` remote seek, no full download) and Kimi K2.6 writes a strict *Scene Report* (subjects, actions, on-screen text, distinctive details). Facts only — people described generically.
2. **Generate** — GLM 5.2 writes 3 candidate captions per style against an explicit **style contract**. `humorous_non_tech` passes a regex **jargon firewall**: one tech word and the candidate dies.
3. **Judge** — a different model family (gpt-oss-120b) scores every candidate on *accuracy* and *style match* — the exact two axes the official LLM-judge uses — and picks the winner.
4. **Refine** — below 0.85/0.85, the stylist gets the judge's critique and one retry round.

**Harness armor:** results are atomically re-written after every completed clip (a timeout still leaves valid partial output), every style always gets a caption (deterministic grounded fallback — never a missing key), JSON is ASCII-escaped, and one bad clip can never crash the batch.

## Container contract (Track 2)

```bash
docker run --rm \
  -v /path/to/input:/input \    # /input/tasks.json
  -v /path/to/output:/output \  # /output/results.json written before exit
  ghcr.io/<owner>/<repo>:latest
```

- Reads `/input/tasks.json`: `[{"task_id", "video_url", "styles": [...]}]`
- Writes `/output/results.json`: `[{"task_id", "captions": {style: text}}]`
- Exit 0, ~20s per clip wall-clock at concurrency 4, well inside the 10-minute budget.
- Credentials ride inside the image (Track 2 injects none). `SKIP_API=1` runs the full contract offline (CI does this on every push).

## Demo UI (same image)

```bash
docker run --rm -p 8000:8000 ghcr.io/<owner>/<repo>:latest \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — pick a clip, watch the Scene Report facts appear, then four caption cards land with the internal judge's `accuracy / style` scores on each.

## Local development

```bash
cp .env.example .env                                   # your FIREWORKS_API_KEY
uv venv && uv pip install -r requirements.txt
uv run python -m agent --tasks tasks.example.json --out out/results.json
uv run uvicorn app.main:app --reload                   # demo UI on :8000
uv run python scripts/model_matrix.py                  # per-model JSON/latency probe
```

## Stack

Fireworks AI (AMD-hardware-hosted serverless): **Kimi K2.6** (vision perceiver) · **GLM 5.2** (stylist) · **gpt-oss-120b** (judge) · **FLUX.1 schnell** (cover art). Python 3.12, FastAPI, ffmpeg. Container built for `linux/amd64` via GitHub Actions → GHCR.

## Repo map

| Path | What |
| --- | --- |
| `agent/contracts.py` | Style contracts, every prompt, jargon firewall, fallbacks |
| `agent/video.py` | Duration probe + remote-seek frame extraction |
| `agent/pipeline.py` | Ground → Generate → Judge → Refine per clip |
| `agent/runner.py` | Harness I/O, concurrency, budget guard, atomic writes |
| `app/main.py` | Demo UI (FastAPI, single file) |
| `PROJECT_STATE.md` | Living build log / handoff doc |
