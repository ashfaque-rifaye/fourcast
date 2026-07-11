# PROJECT_STATE.md — FourCast (AMD ACT II, Track 2)
> **The living handoff document.** Any AI or human continuing this project starts HERE.
> Last updated: 2026-07-11 ~13:00 IST. **Deadline: 2026-07-11 21:29 IST (hard).**

## What this is
**FourCast — four voices for every video.** Track 2 (Video Captioning) entry for AMD Developer Hackathon ACT II on lablab.ai. Team: `mindflayer`. A containerized batch agent that watches video clips and emits captions in 4 styles (`formal`, `sarcastic`, `humorous_tech`, `humorous_non_tech`), engineered to maximize the official LLM-judge score (accuracy 0–1 + style match 0–1 per caption).

## The exam paper (verbatim harness contract — from official Participant Guide PDF)
- Submit: **public Docker image** (GHCR/Docker Hub), **linux/amd64 manifest**, ≤10GB compressed.
- Harness runs container: reads `/input/tasks.json` → `[{"task_id":"v1","video_url":"https://...mp4","styles":["formal","sarcastic","humorous_tech","humorous_non_tech"]}]`
- Container writes `/output/results.json` before exit: `[{"task_id":"v1","captions":{"formal":"...","sarcastic":"...","humorous_tech":"...","humorous_non_tech":"..."}}]`
- Exit code 0; **max runtime 10 minutes**; malformed JSON = zero; missing style = zero for that clip.
- **No env injected for Track 2** — "use your own credentials inside the container" (bundle our Fireworks key).
- Hidden eval: **~12 clips, 30s–2min**, categories: nature, urban, animals, people, sports, food, weather, technology. English only. No hardcoding (unseen variants).
- Rate limit: **10 submissions/hour/team**. Failure statuses: PULL_ERROR / RUNTIME_ERROR / TIMEOUT / OUTPUT_MISSING / INVALID_RESULTS_SCHEMA / IMAGE_TOO_LARGE.
- Grading VM (stated for T1, assume same class): 4GB RAM, 2 vCPU.
- Example clips (dev only): see `tasks.example.json` (3 GCS URLs: autumn boulevard / kitten / office worker).

## Winning architecture (decided)
Pipeline per clip — **Ground → Generate → Judge → Refine**:
1. **Ingest**: `ffprobe` duration → pick 5–10 timestamps (evenly spaced) → extract frames DIRECTLY from URL via `ffmpeg -ss` remote seek (no full download; fallback: full download then extract), resize to 768px JPEG.
2. **Perceive** (vision model): all frames (timestamped) in ONE call → structured **Scene Report** JSON: summary, subjects, actions, setting, on_screen_text, notable_moments, mood. Rule: report only what is VISIBLE (anti-hallucination).
3. **Generate** (stylist model): per style, 3 candidate captions in one call, constrained to Scene Report facts. Style contracts (see `agent/contracts.py`) — e.g. humorous_non_tech has a **jargon firewall** (zero tech words, validated by regex + judge).
4. **Judge** (different model family to avoid self-bias): scores each candidate on accuracy/style exactly like the official judge; picks best; if best < threshold (0.85/0.85) → one refine round with critique.
5. **Emit**: incremental atomic write of `/output/results.json` after EVERY clip (timeout-proof — partial results survive).
- Concurrency: asyncio, ~4 clips in flight, per-call 60s timeout, 1 retry; global soft deadline 8.5 min → flush & exit 0.
- `SKIP_API=1` mode: stub captions (offline harness-contract testing in CI).

## Models (empirically available on our key — /v1/models verified 12:30 IST)
`flux-1-schnell-fp8` (image gen), `gpt-oss-120b`, `glm-5p1`, `glm-5p2`, `deepseek-v4-pro`, `kimi-k2p6`, `kimi-k2p5`.
- Vision/perceiver: `kimi-k2p6` (fallback `kimi-k2p5`) — Kimi K2.x are multimodal per Fireworks catalog. **⚠ UNVERIFIED: image input works — first local run must confirm.**
- Stylist: `glm-5p2` (fallback `kimi-k2p6`).
- Judge: `deepseek-v4-pro` (fallback `gpt-oss-120b`).
- NO Gemma on this key (404) → Gemma bonus not pursued. Full pricing seen: glm-5p2 $1.40/$4.40 per M; deepseek-v4-pro $1.74/$3.48; gpt-oss-120b $0.15/$0.60. Est. cost/full eval run ≈ $1–2. Credits: $50.

## Repo layout (D:\Projects\AMD Hackathon Jul 26\AMDHack — git `main`)
```
agent/            # THE submission artifact (batch agent)
  contracts.py    # style contracts + all prompts
  fw.py           # async Fireworks client (chat + vision), env-driven
  video.py        # ffprobe/ffmpeg frame extraction (imageio-ffmpeg binary)
  pipeline.py     # per-clip ground→generate→judge→refine
  runner.py       # tasks.json in → results.json out, asyncio, budget guard
  __main__.py     # python -m agent
app/              # demo UI (FastAPI) — same image, different CMD
scripts/smoke_test.py
tasks.example.json
Dockerfile        # ffmpeg + python; default CMD = python -m agent
.github/workflows/docker.yml  # build linux/amd64 → GHCR + SKIP_API harness sim
PROJECT_STATE.md  # ← this file
```
Env (.env local; baked for container — see Open Questions): `FIREWORKS_API_KEY`, optional `T2_VISION_MODEL`, `T2_STYLIST_MODEL`, `T2_JUDGE_MODEL`, `SKIP_API`.

## Completed milestones
- [x] Full participant-guide extraction (10 pp) — harness contract locked (above).
- [x] Fireworks key created & validated; model list enumerated; **model matrix probed** (13:25 IST):
      kimi-k2p5 DEAD (500s) · gpt-oss-120b JSON in 1.6s · glm-5p2 2.1s · kimi-k2p6 vision OK 9s.
- [x] agent/ package COMPLETE & VERIFIED: 3/3 example clips, 53–56s total, high-quality grounded
      captions in all 4 styles (v1 even reads "KOREA ELECTRIC ENGINEERING" signage). Fixes that
      mattered: json_mode + strict "JSON only" system line + raw_decode rescuer + brevity cap +
      max_tokens 4000 (vision) — reasoning models leak CoT into content otherwise.
- [x] pipeline refactor: caption_style returns {text, accuracy, style}; process_clip_verbose for UI.
- [x] Demo UI written (app/main.py, single-file dark page, judge badges) — NOT yet browser-tested.
- [x] Dockerfile (ffmpeg apt, FW_KEY_B64 build-arg, CMD python -m agent) + CI (build linux/amd64 →
      SKIP_API harness sim with schema assert → GHCR push) + README rewritten for FourCast.
- [x] Track decision: **Track 2** (user call, 12:15 IST). Idea locked: FourCast (this doc).

## High-priority tasks remaining (in order)
- [x] 1. Demo UI browser-tested on :8017 — kitten clip: judge badges 1.00/1.00, 1.00/1.00, 0.95/1.00, 0.85/1.00
- [x] 6a. 7-slide deck DONE + visually QA'd: assets/FourCast_Deck.pptx (generator: scripts/make_deck.js;
       regenerate: `$env:NODE_PATH=(npm root -g); node scripts/make_deck.js`). Slide PNGs in assets/deck_png/.
       COVER IMAGE = assets/deck_png/Slide1.PNG. Video script + form copy: SUBMISSION.md. FLUX image API 401s on this key — skipped.
- [ ] 2. **USER GATE** Create public repo: `cd "D:\Projects\AMD Hackathon Jul 26\AMDHack"; gh repo create fourcast --public --source . --push`
       (AI was classifier-blocked from doing this; everything is committed and ready to push)
- [ ] 3. **USER GATE** after repo exists — set the container key secret (AI must not touch the key):
       `cd "D:\Projects\AMD Hackathon Jul 26\AMDHack"; $k=((Get-Content .env | Select-String '^FIREWORKS_API_KEY=').ToString() -replace '^FIREWORKS_API_KEY=',''); [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($k)) | gh secret set FW_KEY_B64 -R ashfaque-rifaye/fourcast`
       Then: `gh workflow run container -R ashfaque-rifaye/fourcast` (or push any commit) → CI must be GREEN.
- [ ] 4. **USER GATE** GHCR package public: github.com/users/ashfaque-rifaye/packages/container/fourcast/settings → Change visibility → Public.
       Verify: `docker pull ghcr.io/ashfaque-rifaye/fourcast:latest` from any logged-out machine (or incognito check the package page).
- [ ] 5. Demo URL: decide Render/HF Spaces/cloudflared (localhost:8017 works; server currently RUNNING for video recording)
- [ ] 6b. USER records the 100s video per SUBMISSION.md script (demo UI is live at localhost:8017)
- [ ] 7. SUBMIT by ~19:30 IST (lablab.ai/.../mindflayer/submission) → verify "Qualified (preview)" → iterate (≤10/hr!)
- [ ] 8. (If time) test 2 diverse clips (sports/food); sarcastic-contract polish

## Technical debt & open questions
- ⚠ Kimi vision image_url format unverified (test #2 above decides; fallback = none on this key → would need frames→text via... no VLM alternative; mitigation: request model access or use image descriptions via flux? NO — if kimi vision fails, escalate to user immediately).
- ⚠ Key-in-image exposure: public image ⇒ extractable key. Decision: dedicated 2nd key, base64-obfuscated, revoke post-event, $50 cap, no payment method attached. USER MUST CREATE the 2nd key.
- ⚠ Demo URL hosting undecided (Render vs HF Spaces vs cloudflared tunnel). lablab form likely requires app URL.
- ⚠ Where does the Docker image URL go in the lablab form? Check form fields when submitting (mindflayer/submission).
- ⚠ 10-min budget on 2vCPU: remote-seek extraction untested on GCS URLs (range support presumed; fallback full download coded).
- Git identity: commits as Ashfaque Rifaye; CRLF warnings benign.

## UI/UX wireframe & demo flow (for app/ demo + video)
Single dark page, header "FourCast — four voices for every video".
[Clip picker: 3 example thumbs + URL input] → [Run] → left column: frame strip + Scene Report card (facts as chips); right: 4 caption cards (Formal/Sarcastic/Humorous-Tech/Humorous-Non-Tech), each with accuracy+style score badges, judge verdict tooltip, regenerate button. Money moment for video: humorous_non_tech candidate FAILS jargon firewall (red flash, "tech term detected: 'algorithm'") → auto-regenerates → passes at 0.95. Kill line: "We didn't write four captions. We built the editor who rejects the bad ones."

## Pitch skeleton (video/slides)
1. Problem: same video, four audiences — tone is the product. 2. Demo (live). 3. How: Ground→Generate→Judge→Refine (diagram; "we cloned the grader"). 4. Engineering for the harness (incremental writes, timeout-proof, schema-guaranteed). 5. Models: Kimi K2.6 vision + GLM 5.2 + DeepSeek judge on Fireworks (AMD-hosted). 6. Product: social-team caption API ("one clip in, every voice out"). 7. Team mindflayer.

## Direct prompt for the next AI (copy-paste to resume)
```
You are continuing an in-flight hackathon build. Read D:\Projects\AMD Hackathon Jul 26\AMDHack\PROJECT_STATE.md
top to bottom — it is the single source of truth (harness contract, architecture, models, tasks, open questions).
Hard deadline 2026-07-11 21:29 IST. Work the "High-priority tasks remaining" list IN ORDER, autonomously,
updating PROJECT_STATE.md checkboxes + open questions as you go. The user's Fireworks key is in .env (never
print it). Local runs: `uv run python -m agent --tasks tasks.example.json --out out/results.json`.
Container contract and scoring are NON-NEGOTIABLE — reread "The exam paper" section before touching runner.py.
Submission form: lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii/mindflayer/submission. Submit by 19:30 IST.
```
