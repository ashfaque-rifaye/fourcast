"""FourCast Studio — demo UI backend. Same image as the submission agent, different CMD.

    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

Endpoints:
  GET  /                  the studio single-page app (app/static/index.html)
  GET  /health            liveness probe (used by Cloud Run)
  POST /api/probe         {video_url} -> source kind, metadata, poster frame, validation
  POST /api/upload        multipart file -> {media_id, url}
  GET  /media/{media_id}  serve an uploaded clip back to the <video> player
  GET  /api/stream        SSE: the real pipeline, stage by stage (frames, scene, styles, pack)
  POST /api/caption       legacy one-shot: {video_url} -> {scene, captions, elapsed_s, models}
  POST /api/restyle       {scene, style, creativity?} -> {text, accuracy, style}
  POST /api/rewrite       {text, style, action, scene?} -> {text}   (editing studio actions)
  POST /api/content_pack  {scene, captions, options?} -> titles/hashtags/SEO/scores...
"""
import asyncio
import base64
import json
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from agent import contracts, fw
from agent.pipeline import STYLE_TEMPS, caption_style, process_clip_verbose
from agent.video import _extract_one, _run, extract_frames, ffmpeg_bin

app = FastAPI(title="FourCast Studio", version="2.0.0")

STATIC_DIR = Path(__file__).parent / "static"

EXAMPLES = {
    "Autumn boulevard": "https://storage.googleapis.com/amd-hackathon-clips/1860079-uhd_2560_1440_25fps.mp4",
    "Garden kitten": "https://storage.googleapis.com/amd-hackathon-clips/13825391-uhd_3840_2160_30fps.mp4",
    "Office worker": "https://storage.googleapis.com/amd-hackathon-clips/3044693-uhd_3840_2160_24fps.mp4",
}

# ---------------------------------------------------------------- media store
MEDIA: dict[str, dict] = {}  # media_id -> {"path": str, "name": str}
_MEDIA_DIR = Path(tempfile.gettempdir()) / "fourcast_media"
_MEDIA_DIR.mkdir(exist_ok=True)
MAX_UPLOAD = 300 * 1024 * 1024  # 300 MB


def resolve_src(video_url: str) -> str:
    """Turn the client-facing source string into something ffmpeg can open."""
    if video_url.startswith("media:"):
        media = MEDIA.get(video_url[6:])
        if not media:
            raise ValueError("uploaded clip expired — upload it again")
        return media["path"]
    return video_url


# ------------------------------------------------------------- source detect
_DRIVE_ID = re.compile(r"drive\.google\.com/(?:file/d/([\w-]{20,})|open\?id=([\w-]{20,})|uc\?.*id=([\w-]{20,}))")
_SOCIAL = re.compile(
    r"(youtube\.com|youtu\.be|tiktok\.com|instagram\.com|twitter\.com|x\.com/|"
    r"facebook\.com|fb\.watch|linkedin\.com|vimeo\.com)", re.I)


def detect_source(url: str) -> str:
    u = url.lower()
    if url.startswith("media:"):
        return "upload"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "twitter.com" in u or re.search(r"(^|\.)x\.com/", u):
        return "x"
    if "facebook.com" in u or "fb.watch" in u:
        return "facebook"
    if "linkedin.com" in u:
        return "linkedin"
    if "vimeo.com" in u:
        return "vimeo"
    if "drive.google.com" in u:
        return "gdrive"
    if "dropbox.com" in u:
        return "dropbox"
    return "direct"


async def normalize_url(url: str) -> tuple[str, str, str]:
    """(kind, ffmpeg-openable url, note). May call yt-dlp for social sources."""
    kind = detect_source(url)
    if kind == "gdrive":
        m = _DRIVE_ID.search(url)
        if m:
            gid = next(g for g in m.groups() if g)
            return kind, f"https://drive.google.com/uc?export=download&id={gid}", "Google Drive direct link"
        return kind, url, ""
    if kind == "dropbox":
        u = re.sub(r"[?&]dl=0", "", url)
        u += ("&" if "?" in u else "?") + "dl=1"
        return kind, u, "Dropbox direct link"
    if kind in ("youtube", "tiktok", "instagram", "x", "facebook", "linkedin", "vimeo"):
        stream = await _ytdlp_stream_url(url)
        return kind, stream, f"resolved via yt-dlp ({kind})"
    return kind, url, ""


async def _ytdlp_stream_url(url: str) -> str:
    try:
        from yt_dlp import YoutubeDL  # optional dep — app-only, never used by the agent
    except ImportError as e:
        raise ValueError("social-media import needs yt-dlp (pip install yt-dlp)") from e

    def _extract() -> str:
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "format": "best[ext=mp4][protocol^=http][height<=1080]/best[ext=mp4]/best",
        }
        with YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
        if info.get("entries"):
            info = info["entries"][0]
        direct = info.get("url")
        if not direct:
            raise ValueError("no playable stream found")
        return direct

    try:
        return await asyncio.wait_for(asyncio.to_thread(_extract), timeout=45)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"couldn't resolve this link ({type(e).__name__}) — "
                         "platform may block server downloads; try a direct .mp4, "
                         "Drive/Dropbox link, or upload the file") from e


# ------------------------------------------------------------------ metadata
_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
_VID_RE = re.compile(r"Stream.*Video:\s*([\w\d]+).*?(\d{2,5})x(\d{2,5}).*?([\d.]+)\s*fps", re.S)
_AUD_RE = re.compile(r"Stream.*Audio:\s*([\w\d]+)")


async def probe_media(src: str) -> dict:
    _, _, err = await _run([ffmpeg_bin(), "-hide_banner", "-i", src], timeout=45)
    banner = err.decode(errors="ignore")
    meta: dict = {"duration": None, "width": None, "height": None, "fps": None,
                  "vcodec": None, "acodec": None, "has_audio": False}
    if m := _DUR_RE.search(banner):
        h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        meta["duration"] = round(h * 3600 + mnt * 60 + s, 1)
    if m := _VID_RE.search(banner):
        meta["vcodec"] = m.group(1)
        meta["width"], meta["height"] = int(m.group(2)), int(m.group(3))
        try:
            meta["fps"] = round(float(m.group(4)), 2)
        except ValueError:
            pass
    if m := _AUD_RE.search(banner):
        meta["has_audio"], meta["acodec"] = True, m.group(1)
    if meta["duration"] is None and meta["width"] is None:
        raise ValueError("ffmpeg couldn't open this source as a video")
    return meta


def validate_duration(duration: float | None) -> dict:
    if duration is None:
        return {"ok": True, "level": "warn", "msg": "duration unknown — the track expects 30s–2min"}
    if duration < 30:
        return {"ok": True, "level": "warn",
                "msg": f"{duration:.0f}s is under the track's 30s minimum — captions will still generate"}
    if duration > 120:
        return {"ok": True, "level": "warn",
                "msg": f"{duration:.0f}s is over the track's 2min cap — frames still sample the whole clip"}
    return {"ok": True, "level": "ok", "msg": "within the track's 30s–2min window"}


# ------------------------------------------------------------------- schemas
class CaptionRequest(BaseModel):
    video_url: str


class RestyleRequest(BaseModel):
    scene: dict
    style: str
    creativity: int | None = None  # 0-100 slider
    gemma: bool | None = None      # route this regenerate through Gemma


class RewriteRequest(BaseModel):
    text: str
    style: str
    action: str
    scene: dict | None = None


class PackRequest(BaseModel):
    scene: dict
    captions: dict
    options: dict | None = None


def slider_temp(style: str, creativity: int | None) -> float | None:
    """Map the 0-100 creativity slider onto sampling temperature (0.5x–1.5x)."""
    if creativity is None:
        return None
    base = STYLE_TEMPS.get(style, 0.9)
    return round(min(1.25, max(0.1, base * (0.5 + creativity / 100.0))), 2)


# ------------------------------------------------------------------- routes
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "FourCast", "version": app.version}


@app.get("/api/examples")
def api_examples() -> dict:
    return EXAMPLES


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)) -> dict:
    media_id = uuid.uuid4().hex[:12]
    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    path = _MEDIA_DIR / f"{media_id}{suffix}"
    size = 0
    with open(path, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                f.close()
                path.unlink(missing_ok=True)
                return JSONResponse({"error": "file over 300MB"}, status_code=413)
            f.write(chunk)
    MEDIA[media_id] = {"path": str(path), "name": file.filename or "clip.mp4"}
    return {"media_id": media_id, "url": f"/media/{media_id}",
            "src": f"media:{media_id}", "name": file.filename, "size": size}


@app.get("/media/{media_id}")
def media(media_id: str):
    m = MEDIA.get(media_id)
    if not m:
        return JSONResponse({"error": "unknown media id"}, status_code=404)
    return FileResponse(m["path"], media_type="video/mp4", filename=m["name"])


@app.post("/api/probe")
async def api_probe(req: CaptionRequest) -> dict:
    t0 = time.perf_counter()
    raw = req.video_url.strip()
    kind = detect_source(raw)
    try:
        if raw.startswith("media:"):
            src, note = resolve_src(raw), "uploaded file"
        else:
            kind, src, note = await normalize_url(raw)
        meta = await probe_media(src)
    except ValueError as e:
        return JSONResponse({"error": str(e), "kind": kind}, status_code=422)

    poster = None
    try:
        t = min(1.5, (meta["duration"] or 10) * 0.15)
        if frame := await _extract_one(src, t):
            poster = "data:image/jpeg;base64," + base64.b64encode(frame[1]).decode()
    except Exception:  # noqa: BLE001 — poster is decoration
        pass

    dur = meta["duration"] or 60
    est = int(28 + dur * 0.18)  # empirical: ~45s for a 90s clip
    return {
        "kind": kind, "src": raw, "resolved": src if not raw.startswith("media:") else None,
        "note": note, "meta": meta, "poster": poster,
        "validation": validate_duration(meta["duration"]),
        "playback_url": f"/media/{raw[6:]}" if raw.startswith("media:") else (src if kind != "direct" else raw),
        "est_seconds": est, "probe_ms": int((time.perf_counter() - t0) * 1000),
    }


# --------------------------------------------------------------- SSE pipeline
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _perceive_frames(frames: list[tuple[str, bytes]]) -> dict:
    if fw.SKIP_API:
        return {"summary": f"Stub scene ({len(frames)} frames).", "subjects": ["stub"],
                "actions": ["stub"], "setting": "stub", "on_screen_text": [],
                "camera": "static", "mood": "neutral", "distinctive_details": ["stub"]}
    msgs = fw.vision_messages(contracts.PERCEIVER_SYSTEM,
                              contracts.PERCEIVER_USER.format(n=len(frames)), frames)
    raw = await fw.chat(msgs, fw.VISION_MODEL, fw.VISION_FALLBACK,
                        max_tokens=4000, temperature=0.2, retries=2, json_mode=True)
    return fw.parse_json_block(raw)


@app.get("/api/config")
def api_config() -> dict:
    """Models the UI labels/badges — kept truthful and in one place."""
    return {
        "vision": fw.VISION_MODEL.split("/")[-1],
        "default_stylist": fw.STYLIST_MODEL.split("/")[-1],
        "gemma_model": fw.GEMMA_MODEL.split("/")[-1],
        "judge": fw.JUDGE_MODEL.split("/")[-1],
    }


@app.get("/api/stream")
async def api_stream(src: str, creativity: int | None = None, pack: int = 1, gemma: int = 0):
    """The real pipeline as Server-Sent Events — every stage the UI animates is real.

    gemma=1 routes caption generation (the stylist step only) to Gemma on
    Fireworks for the bonus, keeping Kimi vision + gpt-oss judge; GLM 5.2 stays
    the automatic fallback and each caption reports the model that actually wrote it.
    """
    gemma_stylist = fw.GEMMA_MODEL if gemma else None
    gemma_fallback = "accounts/fireworks/models/glm-5p2" if gemma else None

    async def gen():
        t0 = time.perf_counter()
        try:
            yield _sse("stage", {"id": "probe", "state": "active"})
            raw = src.strip()
            if raw.startswith("media:"):
                ff_src = resolve_src(raw)
            else:
                _, ff_src, _ = await normalize_url(raw)
            meta = await probe_media(ff_src)
            yield _sse("stage", {"id": "probe", "state": "done", "meta": meta})

            yield _sse("stage", {"id": "frames", "state": "active"})
            frames = await extract_frames(ff_src)
            yield _sse("stage", {"id": "frames", "state": "done", "count": len(frames)})
            for ts, jpeg in frames[:8]:
                yield _sse("frame", {"ts": ts, "jpg": base64.b64encode(jpeg).decode()})

            yield _sse("stage", {"id": "vision", "state": "active",
                                 "model": fw.VISION_MODEL.split("/")[-1]})
            scene = await _perceive_frames(frames)
            yield _sse("scene", scene)
            yield _sse("stage", {"id": "vision", "state": "done"})

            yield _sse("stage", {"id": "styling", "state": "active",
                                 "model": (fw.GEMMA_MODEL if gemma else fw.STYLIST_MODEL).split("/")[-1],
                                 "gemma": bool(gemma)})

            async def one(style: str):
                st = time.perf_counter()
                try:
                    d = await caption_style(scene, style,
                                            temperature=slider_temp(style, creativity),
                                            stylist_model=gemma_stylist,
                                            stylist_fallback=gemma_fallback)
                except Exception as e:  # noqa: BLE001
                    print(f"[studio] {style} fell back: {e}", file=sys.stderr)
                    d = {"text": contracts.fallback_caption(scene, style),
                         "accuracy": 0.0, "style": 0.0, "model": "fallback"}
                d["jargon"] = (contracts.jargon_violations(d.get("text", ""))
                               if style == "humorous_non_tech" else [])
                d["elapsed_s"] = round(time.perf_counter() - st, 1)
                return style, d

            captions: dict = {}
            for coro in asyncio.as_completed([one(s) for s in contracts.STYLES]):
                style, d = await coro
                captions[style] = d
                # NB: d already has a "style" key (the judge's style SCORE) —
                # the style name must travel under its own key.
                yield _sse("style", {"style_id": style, **d})
            yield _sse("stage", {"id": "styling", "state": "done"})

            if pack and not fw.SKIP_API:
                yield _sse("stage", {"id": "pack", "state": "active"})
                try:
                    p = await _content_pack(scene, {k: v["text"] for k, v in captions.items()}, {})
                    yield _sse("pack", p)
                except Exception as e:  # noqa: BLE001
                    print(f"[studio] content pack failed: {e}", file=sys.stderr)
                yield _sse("stage", {"id": "pack", "state": "done"})

            used = sorted({v.get("model") for v in captions.values()
                           if v.get("model") and v.get("model") not in ("skip", "fallback")})
            yield _sse("done", {
                "elapsed_s": round(time.perf_counter() - t0, 1),
                "gemma_requested": bool(gemma),
                "models": {"vision": fw.VISION_MODEL.split("/")[-1],
                           "stylist": ", ".join(used) or fw.STYLIST_MODEL.split("/")[-1],
                           "judge": fw.JUDGE_MODEL.split("/")[-1]},
            })
        except Exception as e:  # noqa: BLE001
            yield _sse("err", {"message": str(e)[:300]})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ------------------------------------------------------- legacy + editing API
@app.post("/api/caption")
async def api_caption(req: CaptionRequest) -> dict:
    t0 = time.perf_counter()
    src = resolve_src(req.video_url)
    task = {"task_id": "demo", "video_url": src}
    scene, detailed = await asyncio.wait_for(process_clip_verbose(task), timeout=240)
    for style, d in detailed.items():
        d["jargon"] = contracts.jargon_violations(d.get("text", "")) if style == "humorous_non_tech" else []
    return {"scene": scene, "captions": detailed,
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "models": {"vision": fw.VISION_MODEL.split("/")[-1],
                       "stylist": fw.STYLIST_MODEL.split("/")[-1],
                       "judge": fw.JUDGE_MODEL.split("/")[-1]}}


@app.post("/api/restyle")
async def api_restyle(req: RestyleRequest) -> dict:
    if req.style not in contracts.STYLES:
        return {"text": "", "accuracy": 0.0, "style": 0.0}
    d = await asyncio.wait_for(
        caption_style(req.scene, req.style,
                      temperature=slider_temp(req.style, req.creativity),
                      stylist_model=(fw.GEMMA_MODEL if req.gemma else None),
                      stylist_fallback=("accounts/fireworks/models/glm-5p2" if req.gemma else None)),
        timeout=90)
    d["jargon"] = contracts.jargon_violations(d["text"]) if req.style == "humorous_non_tech" else []
    return d


REWRITE_ACTIONS = {
    "shorten": "Rewrite the caption in at most half the words. Keep the same tone and facts.",
    "expand": "Rewrite the caption slightly longer with one extra vivid grounded detail. Same tone.",
    "punchier": "Rewrite the caption to be punchier and more engaging — stronger verbs, tighter rhythm. Same tone and facts.",
    "simplify": "Rewrite the caption in simpler, clearer everyday words. Same tone and facts.",
    "emoji_add": "Rewrite the caption adding 2-3 fitting emojis (unless the tone is formal — then refuse by returning it unchanged).",
    "emoji_remove": "Rewrite the caption with every emoji removed. Same wording otherwise.",
    "grammar": "Fix any grammar, punctuation or spelling issues. Change nothing else.",
}


@app.post("/api/rewrite")
async def api_rewrite(req: RewriteRequest) -> dict:
    instr = REWRITE_ACTIONS.get(req.action)
    if not instr:
        return JSONResponse({"error": f"unknown action {req.action}"}, status_code=400)
    contract = contracts.STYLE_CONTRACTS.get(req.style, "")
    scene_line = f"\nSCENE REPORT (stay grounded in these facts):\n{json.dumps(req.scene, ensure_ascii=False)}" if req.scene else ""
    msgs = [
        {"role": "system", "content": contracts.STYLIST_SYSTEM},
        {"role": "user", "content":
            f"CAPTION:\n{req.text}\n\nSTYLE CONTRACT (must still hold):\n{contract}{scene_line}\n\n"
            f"TASK: {instr}\n\nReturn STRICT JSON: {{\"text\": \"the rewritten caption\"}}"},
    ]
    raw = await fw.chat(msgs, fw.STYLIST_MODEL, fw.STYLIST_FALLBACK,
                        max_tokens=600, temperature=0.6, json_mode=True)
    text = str(fw.parse_json_block(raw).get("text", "")).strip() or req.text
    jargon = contracts.jargon_violations(text) if req.style == "humorous_non_tech" else []
    return {"text": text, "jargon": jargon}


# -------------------------------------------------------------- content pack
PACK_PROMPT = """You are a senior social-media strategist. Using ONLY the scene report and captions
below (never invent events not present), produce a distribution kit for this video clip.

SCENE REPORT:
{scene}

THE FOUR CAPTIONS:
{captions}

OPTIONS: {options}

Return STRICT JSON exactly matching:
{{
  "titles": ["3 video title options, best first, <=60 chars each"],
  "hook": "one scroll-stopping opening line for the video",
  "summary": "2 sentence video summary",
  "hashtags": ["8-12 relevant hashtags without # prefix"],
  "keywords": ["6-10 SEO keywords"],
  "seo_description": "<=155 char meta description",
  "alt_text": "one-sentence accessibility alt text describing the video visually",
  "cta": "one fitting call-to-action line",
  "topics": ["3-6 detected topics"],
  "emotions": ["2-4 emotions the clip evokes"],
  "scores": {{
    "readability": 0-100,
    "engagement": 0-100,
    "virality": 0-100,
    "accessibility": 0-100
  }},
  "platform_fit": {{"instagram": 0-100, "tiktok": 0-100, "youtube": 0-100, "linkedin": 0-100}}
}}"""


async def _content_pack(scene: dict, captions: dict, options: dict) -> dict:
    msgs = [
        {"role": "system", "content": "You are a precise JSON-only assistant."},
        {"role": "user", "content": PACK_PROMPT.format(
            scene=json.dumps(scene, ensure_ascii=False),
            captions=json.dumps(captions, ensure_ascii=False),
            options=json.dumps(options or {}, ensure_ascii=False))},
    ]
    raw = await fw.chat(msgs, fw.STYLIST_MODEL, fw.STYLIST_FALLBACK,
                        max_tokens=1800, temperature=0.7, json_mode=True)
    return fw.parse_json_block(raw)


@app.post("/api/content_pack")
async def api_content_pack(req: PackRequest) -> dict:
    return await _content_pack(req.scene, req.captions, req.options or {})
