# SUBMISSION.md — everything that goes into the lablab form

Form: https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii/mindflayer/submission
Deadline: **2026-07-11 21:29 IST** · submit v1 by **19:30 IST**, iterate after (limit 10/hr).

## Basic information

**Title:** FourCast — Four Voices for Every Video

**Short description (≤~200 chars):**
A video-captioning agent that grounds every line in what's actually on screen, then makes four tones — formal, sarcastic, humorous-tech, humorous-non-tech — fight an in-house judge before you see them.

**Long description:**
Most caption pipelines are a prompt wrapper. FourCast is a caption factory with quality control.

Frames are sampled straight off the video URL (ffmpeg remote seek — no full download), and Kimi K2.6 writes a strict Scene Report: subjects, actions, on-screen text, distinctive details. Facts only — if it isn't visible, it doesn't exist. GLM 5.2 then writes three candidates per style against explicit style contracts; `humorous_non_tech` must additionally survive a regex jargon firewall — one tech word and the candidate dies. A separate model family (gpt-oss-120b) judges every candidate on the exact two axes the official leaderboard uses — caption accuracy and style match — picks the winner, and sends weak ones back for a critique-guided rewrite.

The container is engineered for the evaluation harness: results are atomically rewritten after every clip (a timeout still leaves valid partial output), every style always gets a grounded caption (never a missing key), output JSON is ASCII-escaped, and one bad clip can't crash the batch. Three example clips process in ~55 seconds; a 12-clip hidden set fits comfortably inside the 10-minute budget.

On the sample clips, our internal judge scores land at 0.85–1.00 on both axes — e.g. "Kitten boots from a stationary state, then begins a slow forward deploy toward the camera, tail raised high as a status indicator."

Built solo in one day on Fireworks AI (AMD-hardware-hosted serverless models).

**Technology tags:** Fireworks AI, Kimi K2.6, GLM 5.2, gpt-oss-120b, FastAPI, Python, Docker, ffmpeg
**Category tags:** AI Agents, Video, Content Generation

## Links
- **GitHub (public):** https://github.com/ashfaque-rifaye/fourcast  ← create + push (gate #1)
- **Docker image (what the harness pulls):** ghcr.io/ashfaque-rifaye/fourcast:latest ← must be PUBLIC (gate #3)
- **Demo URL:** https://fourcast-demo-163580532635.us-central1.run.app  ← LIVE on Google Cloud Run (verified end-to-end: kitten clip, judge 0.95–1.00, 44s)
- **Video:** record per script below → YouTube unlisted → paste link
- **Slides:** assets/FourCast_Deck.pptx → upload
- **Cover image:** 1200×675 screenshot of the Studio results view — open `<demo-url>/?mock=1`
  (canned data, no API spend; add `&theme=light` for the light variant), capture the four
  caption cards + judge rings. Crop browser chrome.

## Video script (100 seconds, screen-record the demo UI)
1. **[0–10s] Hook** — UI open, empty. "Every caption tool can describe a video. The hard part is saying it in the right voice — four of them."
2. **[10–25s] Run it** — click *Garden kitten*, hit **Caption it**. "FourCast pulls frames straight off the video — no download — and a vision model writes a scene report: only what's actually on screen."
3. **[25–40s] Facts panel appears** — point at chips. "These facts are the contract. No fact, no joke — that's how we kill hallucination before it starts."
4. **[40–70s] Cards land** — read the sarcastic one aloud, then humorous_tech. "Every card you see already beat two siblings in front of an in-house judge that scores exactly what the leaderboard scores: accuracy and style. The non-tech style even runs a jargon firewall — one tech word and the caption dies."
5. **[70–90s] Engineering slide (or README scroll)** — "Under the hood it's a 10-minute-budget batch agent: incremental atomic writes, per-style fallbacks, one bad clip can never zero the batch."
6. **[90–100s] Close** — "FourCast. One clip in, every voice out. Team mindflayer, built on Fireworks AI."

## Slide deck outline (7 slides — assets/FourCast_Deck.pptx)
1. Title: FourCast — four voices for every video · team mindflayer · AMD ACT II Track 2
2. The task: 4 tones × hidden clips × LLM-judge (accuracy + style) — most pipelines are a prompt wrapper
3. The architecture: Ground → Generate → Judge → Refine (diagram)
4. The tricks that score: scene-report grounding · style contracts · jargon firewall · judge-before-ship
5. Harness armor: incremental atomic results · guaranteed styles · 55s/3 clips (10-min budget headroom)
6. Receipts: real captions + internal judge scores (kitten/office/traffic examples)
7. Product: "one clip in, every voice out" — social teams, one API · stack: Fireworks (Kimi K2.6 · GLM 5.2 · gpt-oss-120b)

## Submission-time checklist
- [ ] CI green on last commit (build + SKIP_API harness sim + GHCR push)
- [ ] `docker pull ghcr.io/ashfaque-rifaye/fourcast:latest` works from a logged-OUT shell (proves public)
- [ ] Fresh key present in image (`FW_KEY_B64` secret set BEFORE the CI run that built it)
- [ ] Demo URL loads from phone (not just localhost)
- [ ] All form fields filled; video link plays; deck uploads
- [ ] After submit: status shows **Qualified (preview)** on live?track=2 — if a failure status appears, map it via the guide's troubleshooting table and resubmit (≤10/hr)
