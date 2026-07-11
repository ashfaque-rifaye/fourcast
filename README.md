<div align="center">

# 🎬 FourCast — four voices for every video

**One clip in, every voice out.** A containerized video-captioning agent that grounds every line in what is *actually on screen*, then writes it in four tones — `formal`, `sarcastic`, `humorous_tech`, `humorous_non_tech` — each one **self-judged before it ships**.

[![container](https://github.com/ashfaque-rifaye/fourcast/actions/workflows/docker.yml/badge.svg)](https://github.com/ashfaque-rifaye/fourcast/actions/workflows/docker.yml)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![platform](https://img.shields.io/badge/image-linux%2Famd64-0A0A0A?logo=docker&logoColor=white)
![Fireworks AI](https://img.shields.io/badge/Fireworks%20AI-AMD--hosted-ff5c1a)
![license](https://img.shields.io/badge/license-MIT-green)

_AMD Developer Hackathon: ACT II · Track 2 (Video Captioning) · Team **mindflayer**_

</div>

---

## The problem

The same 30-second clip means four different things to four different audiences. A caption for a press kit is not a caption for a meme feed. Most hackathon captioners are a thin prompt wrapper — `frames → VLM → "now be funny"` — and they fail in two predictable ways:

1. **They hallucinate.** Ungrounded models invent details that aren't in the video, and an accuracy judge punishes every invented fact.
2. **They don't survive the harness.** Track 2 is scored by an automated pipeline that pulls your public image, runs it against ~12 hidden clips under a hard 10-minute budget, and expects a schema-perfect `results.json`. A crash, a timeout, one missing style, or malformed JSON scores **zero** — and the public leaderboard shows this happening to a large share of entries.

## The solution

FourCast is not a prompt wrapper. It is a **caption factory with quality control** plus a container engineered to *never* hand the grader a zero.

```
  video_url
     │
     ▼
┌──────────────┐   ffmpeg remote-seek (no full download), 5–10 frames @768px
│ 1. GROUND    │   Kimi K2.6 (vision) ─▶ strict Scene Report JSON
│              │   subjects · actions · on-screen text · distinctive details
└──────┬───────┘   RULE: only what is visible. No fact → it does not exist.
       │  (facts are the contract)
       ▼
┌──────────────┐   GLM 5.2 writes 3 candidates per style against a style contract
│ 2. GENERATE  │   humorous_non_tech must also pass a regex JARGON FIREWALL
└──────┬───────┘   (one tech word and the candidate dies)
       │  4 styles × 3 candidates
       ▼
┌──────────────┐   gpt-oss-120b (different model family — no self-bias) scores
│ 3. JUDGE     │   every candidate on accuracy + style match — the exact two
└──────┬───────┘   axes the official LLM-judge uses — and picks the winner
       │
       ▼
┌──────────────┐   winner below 0.85/0.85 → stylist gets the critique + one retry
│ 4. REFINE    │
└──────┬───────┘
       ▼
  captions{formal, sarcastic, humorous_tech, humorous_non_tech}
```

### Why it scores

| Design choice | What it buys on the leaderboard |
| --- | --- |
| **Scene-Report grounding** (facts-only, generic people) | Kills hallucination at the source → higher **accuracy** |
| **Executable style contracts** + regex **jargon firewall** | Enforceable **style match**, especially the tricky non-tech tone |
| **Judge before ship** (separate model family, same axes as the official judge) | Best-of-N on the very metric being graded |
| **Critique-guided refine** below 0.85/0.85 | Rescues weak captions instead of shipping them |

### Harness armor — the part most entries miss

The public leaderboard is full of `TIMEOUT`, `OUTPUT_MISSING`, `INVALID_RESULTS_SCHEMA`, `RUNTIME_ERROR`, and `PULL_ERROR`. FourCast is built so none of those can happen:

- **Atomic incremental writes** — `results.json` is re-written after *every* completed clip, so even a hard timeout leaves valid partial output on disk.
- **Per-clip hard timeout** — a single stalled network read can never starve a concurrency slot or drag the batch average; it degrades to a grounded fallback (`T2_CLIP_TIMEOUT_S`).
- **Every style always gets a caption** — deterministic grounded fallback means a key is never missing (a missing style scores zero).
- **Budget-aware, reliability-first** — the refine round is best-effort and can be disabled (`T2_FAST=1`) so cleverness never costs the 10-minute budget.
- **One bad clip can't crash the batch** — every stage degrades gracefully; the pipeline never raises.
- **ASCII-escaped JSON** — harness-side decoding can never garble a caption.
- **`linux/amd64` image, public on GHCR**, built and contract-tested in CI on every push.

## Container contract (Track 2)

```bash
docker run --rm \
  -v /path/to/input:/input \      # /input/tasks.json
  -v /path/to/output:/output \    # /output/results.json written before exit
  ghcr.io/ashfaque-rifaye/fourcast:latest
```

- **Reads** `/input/tasks.json`: `[{"task_id", "video_url", "styles": [...]}]`
- **Writes** `/output/results.json`: `[{"task_id", "captions": {style: text}}]`
- Exit code 0. ~20s per clip wall-clock at concurrency 4 — a 12-clip hidden set fits comfortably inside the 10-minute budget.
- Credentials ride **inside** the image (Track 2 injects none). `SKIP_API=1` runs the full contract offline (CI does this on every push — zero API spend).

## FourCast Studio — the demo UI (same image, different command)

```bash
docker run --rm -p 8000:8000 ghcr.io/ashfaque-rifaye/fourcast:latest \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

A full AI captioning studio on top of the same pipeline the harness runs:

- **Any source in** — drag & drop / local upload, direct `.mp4` links, and auto-resolved
  YouTube · TikTok · Instagram · X · Facebook · Vimeo links (via yt-dlp), plus Google
  Drive and Dropbox share links. The clip **plays right in the studio** with duration /
  resolution / fps / audio metadata and a 30s–2min track-window validation.
- **Live pipeline** — every stage streams over SSE as it really happens: probe → frame
  filmstrip (the actual extracted frames) → Scene-Report chips → four caption cards
  landing one by one with the internal judge's `accuracy / style` score rings.
- **Creativity slider** — maps to per-style sampling temperature (the four track styles
  themselves are never compromised — they're the contract).
- **Editing studio** — captions are editable inline, with AI actions (shorten, expand,
  punchier, simplify, ±emoji, fix grammar), per-card regenerate (re-judged), undo, and
  a live jargon-firewall flag on the non-tech card.
- **AI content pack** — titles, hook, hashtags, keywords, SEO description, alt text,
  CTA, topic/emotion detection, and AI-estimated readability / engagement / virality /
  accessibility gauges with platform-fit bars.
- **Exports** — `results.json` (harness schema), `.txt`, `.md`, and `.srt` / `.vtt`
  subtitles in any of the four voices. Keyboard shortcuts throughout; dark & light themes.

Tip: `/?mock=1` renders the full results view with canned data (no API spend) — handy
for screenshots; add `&theme=light` for the light variant.

### Deploy the demo (public URL)

The demo runs on **Google Cloud Run** (container-native, `ffmpeg` + long requests — Vercel can't do either). One command:

```bash
./deploy/deploy-cloudrun.sh          # or  deploy/deploy-cloudrun.ps1 on Windows
```

Full guide and the Vercel-vs-Cloud-Run rationale: [DEPLOY.md](DEPLOY.md).

## Quickstart (local)

```bash
git clone https://github.com/ashfaque-rifaye/fourcast.git
cd fourcast
cp .env.example .env                                   # add your FIREWORKS_API_KEY
uv venv && uv pip install -r requirements.txt

uv run python -m agent --tasks tasks.example.json --out out/results.json   # batch agent
uv run uvicorn app.main:app --reload                   # demo UI on :8000
uv run python scripts/model_matrix.py                  # per-model JSON/latency probe

# no key? prove the container contract offline:
SKIP_API=1 uv run python -m agent --tasks tasks.example.json --out out/results.json
```

### Run with Docker Compose

```bash
docker compose up --build       # demo UI on http://localhost:8000
```

## Sample output

On the example clips the internal judge lands at **0.85–1.00 on both axes**. Example (`humorous_tech`, garden kitten):

> _"Kitten boots from a stationary state, then begins a slow forward deploy toward the camera, tail raised high as a status indicator."_

A full `results.json` for the three example clips lives in [`out/`](out/).

## Tech stack

| Layer | Choice |
| --- | --- |
| **Vision / perceiver** | Kimi K2.6 (fallback Kimi K2.5) |
| **Stylist** | GLM 5.2 (fallback Kimi K2.6) |
| **Judge** | gpt-oss-120b (fallback GLM 5.1) |
| **Inference** | [Fireworks AI](https://fireworks.ai/) — serverless models hosted on **AMD** hardware |
| **Runtime** | Python 3.12 · asyncio · FastAPI · httpx |
| **Media** | ffmpeg (remote-seek frame extraction, no full download) |
| **Ship** | Docker (`linux/amd64`) · GitHub Actions → GHCR |

## Repository layout

```
agent/                THE submission artifact (batch agent)
  contracts.py        style contracts · every prompt · jargon firewall · fallbacks
  fw.py               async Fireworks client (chat + vision), env-driven
  video.py            duration probe + remote-seek frame extraction
  pipeline.py         per-clip Ground → Generate → Judge → Refine
  runner.py           harness I/O · concurrency · budget guard · atomic writes
  __main__.py         python -m agent
app/main.py           FourCast Studio backend (probe · upload · SSE pipeline · content pack)
app/static/index.html FourCast Studio frontend (single file, zero build step)
scripts/
  model_matrix.py     per-model JSON-mode / latency probe
  make_deck.js        pitch-deck generator
  cover.py            cover-image helper
tasks.example.json    sample harness input (3 clips)
Dockerfile            ffmpeg + python; default CMD = python -m agent
docker-compose.yml    demo UI convenience
.github/workflows/    build linux/amd64 → SKIP_API contract sim → push GHCR
PROJECT_STATE.md      living build log / handoff doc
SUBMISSION.md         lablab.ai submission copy + video script
```

## Roadmap

- ✅ **Gemma track eligibility** — opt-in Gemma stylist path (`T2_USE_GEMMA=1`) to compete for the *Best Use of Gemma in Video Captioning* bonus, keeping Kimi vision + gpt-oss judge with GLM 5.2 as fallback. *Requires a Fireworks key with Gemma access; without it the pipeline transparently falls back to GLM 5.2.*
- ✅ **Per-style temperature** — cool/precise for `formal`, warmer for the humorous tones.
- ✅ **Reliability-first budget control** — per-clip timeout + optional fast mode.
- **Audio grounding** — optional Whisper pass so speech-driven clips (technology/people categories) ground on dialogue as well as frames.
- **Adaptive sampling** — scene-change-aware frame selection instead of even spacing.

## Team & credits

Built by **team mindflayer** for the AMD Developer Hackathon: ACT II. Inference on Fireworks AI (AMD-hosted). Video frames via ffmpeg.

## License

[MIT](LICENSE) © 2026 team mindflayer.
