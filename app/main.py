"""FourCast demo — a premium AI captioning studio (same image as the agent).

    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

Hosting truth surfaced in the UI:
  • The web app is hosted on Google Cloud Run (detected via $K_SERVICE).
  • Inference runs on Fireworks AI, served on AMD Instinct GPUs.

Endpoints:
  GET  /                 the single-page studio UI
  GET  /health           liveness probe (Cloud Run)
  POST /api/caption      {video_url} -> {scene, captions, frame_marks, duration, ...}
  POST /api/restyle      {scene, style} -> {text, accuracy, style}   (per-card regenerate)
"""
import asyncio
import os
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import contracts, fw
from agent.pipeline import caption_style, process_clip_verbose
from agent.video import pick_timestamps, probe_duration

app = FastAPI(title="FourCast", version="1.2.0")

HOST_LABEL = "Google Cloud Run" if os.getenv("K_SERVICE") else "Local dev"
INFER_LABEL = "Fireworks AI · AMD Instinct GPUs"

EXAMPLES = {
    "Autumn Boulevard": "https://storage.googleapis.com/amd-hackathon-clips/1860079-uhd_2560_1440_25fps.mp4",
    "Garden Kitten": "https://storage.googleapis.com/amd-hackathon-clips/13825391-uhd_3840_2160_30fps.mp4",
    "Office Worker": "https://storage.googleapis.com/amd-hackathon-clips/3044693-uhd_3840_2160_24fps.mp4",
}


class CaptionRequest(BaseModel):
    video_url: str


class RestyleRequest(BaseModel):
    scene: dict
    style: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "FourCast", "version": app.version, "host": HOST_LABEL}


@app.post("/api/caption")
async def api_caption(req: CaptionRequest) -> dict:
    t0 = time.perf_counter()
    task = {"task_id": "demo", "video_url": req.video_url}

    async def _marks():
        try:
            d = await probe_duration(req.video_url)
            return d, pick_timestamps(d)
        except Exception:
            return 0.0, []

    (scene, detailed), (duration, marks) = await asyncio.gather(
        asyncio.wait_for(process_clip_verbose(task), timeout=240), _marks()
    )
    for style, d in detailed.items():
        d["jargon"] = contracts.jargon_violations(d.get("text", "")) if style == "humorous_non_tech" else []
    return {
        "scene": scene,
        "captions": detailed,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "duration": round(duration, 2),
        "frame_marks": marks,
        "models": {"vision": fw.VISION_MODEL.split("/")[-1],
                   "stylist": (fw.AMD_VLLM_MODEL if fw.AMD_VLLM_BASE_URL else fw.STYLIST_MODEL).split("/")[-1],
                   "judge": fw.JUDGE_MODEL.split("/")[-1]},
        "host": HOST_LABEL,
        "inference": INFER_LABEL,
    }


@app.post("/api/restyle")
async def api_restyle(req: RestyleRequest) -> dict:
    if req.style not in contracts.STYLES:
        return {"text": "", "accuracy": 0.0, "style": 0.0}
    d = await asyncio.wait_for(caption_style(req.scene, req.style), timeout=90)
    d["jargon"] = contracts.jargon_violations(d["text"]) if req.style == "humorous_non_tech" else []
    return d


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FourCast — AI Captioning Studio · Team Mindflayer</title>
<style>
  :root{
    --bg:#080a10; --bg2:#0d111b; --card:#121826; --card2:#161d2e; --line:#232c40;
    --text:#eaf0fb; --dim:#8a95ac; --accent:#ff5c1a; --accent2:#ff8a4c; --good:#39d98a;
    --formal:#5aa9ff; --sarcastic:#c792ff; --htech:#39d98a; --hnon:#ffcf5a;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:radial-gradient(1200px 600px at 80% -10%,rgba(255,92,26,.10),transparent 60%),
       radial-gradient(900px 500px at -10% 10%,rgba(90,169,255,.08),transparent 55%),var(--bg);
       color:var(--text);font:16px/1.55 ui-sans-serif,system-ui,"Segoe UI",Roboto,sans-serif;
       padding:30px 20px 90px;min-height:100vh}
  .wrap{max-width:1160px;margin:0 auto}
  header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:8px}
  .brand{display:flex;align-items:center;gap:13px}
  .logo{width:46px;height:46px;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--accent2));
        display:grid;place-items:center;font-weight:800;font-size:22px;color:#fff;box-shadow:0 8px 24px rgba(255,92,26,.4)}
  h1{font-size:29px;letter-spacing:-.6px;font-weight:800}
  h1 b{color:var(--accent)}
  .tag{color:var(--dim);font-size:13px;margin-top:1px}
  .statuses{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .pill{font-size:12px;color:var(--text);border:1px solid var(--line);border-radius:999px;padding:6px 12px;
        display:flex;align-items:center;gap:7px;background:rgba(255,255,255,.02)}
  .pill .g{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 8px var(--good)}
  .pill.gcp .g{background:#4c8bf5;box-shadow:0 0 8px #4c8bf5}
  .pill.amd .g{background:var(--accent);box-shadow:0 0 8px var(--accent)}
  .pill.team{background:linear-gradient(135deg,rgba(255,92,26,.18),rgba(255,138,76,.06));border-color:var(--accent);font-weight:700}
  .sub{color:var(--dim);margin:12px 0 22px;max-width:820px}

  /* ---- Cinematic player ---- */
  .studio{position:relative;margin-bottom:20px}
  .stage-wrap{position:relative;border-radius:22px;padding:2px;
       background:linear-gradient(120deg,rgba(255,92,26,.6),rgba(90,169,255,.35),rgba(199,146,255,.4),rgba(255,92,26,.6));
       background-size:300% 300%;animation:border 8s ease infinite;
       box-shadow:0 30px 80px -30px rgba(255,92,26,.35),0 10px 40px -20px rgba(90,169,255,.3)}
  @keyframes border{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
  .stage{position:relative;border-radius:20px;overflow:hidden;background:#05070c;
        aspect-ratio:16/9;display:grid;place-items:center;transition:transform .2s ease}
  .stage video{width:100%;height:100%;object-fit:contain;display:none;background:#05070c}
  .glow{position:absolute;inset:-2px;border-radius:22px;pointer-events:none;
        box-shadow:inset 0 0 120px rgba(255,92,26,.10)}

  /* empty state */
  .empty{position:absolute;inset:0;display:grid;place-items:center;text-align:center;padding:24px}
  .empty .orb{width:96px;height:96px;border-radius:50%;margin:0 auto 18px;
        background:radial-gradient(circle at 35% 30%,var(--accent2),var(--accent) 60%,#7a2a0a);
        box-shadow:0 0 60px rgba(255,92,26,.5);animation:float 3.4s ease-in-out infinite}
  @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
  .empty h3{font-size:19px;margin-bottom:6px}
  .empty p{color:var(--dim);font-size:14px}
  .particles{position:absolute;inset:0;overflow:hidden;pointer-events:none}
  .particles i{position:absolute;bottom:-10px;width:4px;height:4px;border-radius:50%;background:rgba(255,138,76,.6);
        animation:rise linear infinite}
  @keyframes rise{to{transform:translateY(-420px);opacity:0}}

  /* processing overlay */
  .proc{position:absolute;inset:0;display:none;flex-direction:column;justify-content:center;gap:14px;padding:34px 40px;
        background:rgba(5,7,12,.72);backdrop-filter:blur(6px)}
  .scanline{position:absolute;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--accent),transparent);
        box-shadow:0 0 14px var(--accent);animation:scan 2.4s ease-in-out infinite}
  @keyframes scan{0%{top:8%}50%{top:92%}100%{top:8%}}
  .corner{position:absolute;width:34px;height:34px;border:2px solid rgba(255,92,26,.5)}
  .corner.tl{top:16px;left:16px;border-right:0;border-bottom:0}
  .corner.tr{top:16px;right:16px;border-left:0;border-bottom:0}
  .corner.bl{bottom:16px;left:16px;border-right:0;border-top:0}
  .corner.br{bottom:16px;right:16px;border-left:0;border-top:0}
  .steps{max-width:420px;margin:0 auto;width:100%}
  .step{display:flex;align-items:center;gap:12px;padding:7px 0;color:var(--dim);font-size:14px;transition:.3s}
  .step .ic{width:22px;height:22px;border-radius:50%;border:2px solid var(--line);display:grid;place-items:center;
        font-size:12px;flex-shrink:0;transition:.3s}
  .step.active{color:var(--text)} .step.active .ic{border-color:var(--accent);box-shadow:0 0 12px rgba(255,92,26,.5)}
  .step.done .ic{border-color:var(--good);background:var(--good);color:#04110a}
  .step.active .ic:after{content:"";width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

  /* custom controls */
  .controls{position:absolute;left:0;right:0;bottom:0;padding:10px 14px 12px;
        background:linear-gradient(0deg,rgba(5,7,12,.92),rgba(5,7,12,.4) 70%,transparent);
        opacity:0;transform:translateY(8px);transition:.25s;display:none;flex-direction:column;gap:8px}
  .stage.ready:hover .controls,.stage.ready.paused .controls{opacity:1;transform:none}
  .timeline{position:relative;height:16px;display:flex;align-items:center;cursor:pointer}
  .track{position:absolute;left:0;right:0;height:5px;border-radius:3px;background:rgba(255,255,255,.15)}
  .buffered{position:absolute;left:0;height:5px;border-radius:3px;background:rgba(255,255,255,.25);width:0}
  .fill{position:absolute;left:0;height:5px;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));width:0}
  .scrub{position:absolute;width:13px;height:13px;border-radius:50%;background:#fff;transform:translateX(-50%);
        box-shadow:0 0 10px rgba(255,92,26,.8);left:0;opacity:0;transition:opacity .15s}
  .timeline:hover .scrub{opacity:1}
  .mark{position:absolute;top:50%;width:3px;height:10px;border-radius:2px;background:var(--accent2);
        transform:translate(-50%,-50%);opacity:.8;box-shadow:0 0 6px rgba(255,138,76,.7)}
  .tip{position:absolute;bottom:20px;transform:translateX(-50%);background:#0e1420;border:1px solid var(--line);
        border-radius:7px;padding:3px 8px;font-size:12px;display:none;white-space:nowrap}
  .ctrlrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
  .cbtn{background:rgba(255,255,255,.06);border:1px solid transparent;border-radius:9px;color:var(--text);
        width:36px;height:36px;display:grid;place-items:center;cursor:pointer;font-size:14px;transition:.14s;position:relative}
  .cbtn:hover{background:rgba(255,92,26,.18);border-color:rgba(255,92,26,.4);transform:translateY(-1px)}
  .cbtn.wide{width:auto;padding:0 12px;font-size:13px;font-weight:600}
  .cbtn.on{background:rgba(255,92,26,.25);border-color:var(--accent)}
  .time{font-variant-numeric:tabular-nums;font-size:13px;color:var(--text);padding:0 6px;min-width:104px}
  .vol{width:0;opacity:0;transition:.2s;accent-color:var(--accent)}
  .volwrap:hover .vol{width:80px;opacity:1;margin:0 6px}
  .spacer{flex:1}
  .cbtn .tt{position:absolute;bottom:44px;left:50%;transform:translateX(-50%);background:#0e1420;border:1px solid var(--line);
        color:var(--text);font-size:11px;padding:3px 8px;border-radius:6px;white-space:nowrap;opacity:0;pointer-events:none;transition:.15s}
  .cbtn:hover .tt{opacity:1}

  /* caption overlay */
  .capoverlay{position:absolute;left:0;right:0;bottom:64px;display:flex;justify-content:center;padding:0 10%;
        pointer-events:none;transition:opacity .35s,transform .35s}
  .capbox{background:rgba(8,10,16,.55);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.08);
        border-radius:14px;padding:12px 18px;max-width:760px;text-align:center;font-size:20px;line-height:1.4;
        box-shadow:0 10px 40px rgba(0,0,0,.5);transition:.35s}
  .capbox.theme-classic{background:rgba(0,0,0,.7)}
  .capbox.theme-neon{border-color:var(--accent);box-shadow:0 0 30px rgba(255,92,26,.4)}
  .capbox .lbl{font-size:10px;letter-spacing:1.6px;text-transform:uppercase;color:var(--accent2);margin-bottom:4px;display:block}

  /* studio side toolbar */
  .studiobar{display:flex;gap:10px;align-items:center;margin:14px 0 4px;flex-wrap:wrap}
  .row{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 22px}
  input.url{flex:1;min-width:260px;background:var(--card);border:1px solid var(--line);border-radius:12px;
        color:var(--text);padding:13px 15px;font-size:15px;outline:none;transition:.16s}
  input.url:focus{border-color:var(--accent)}
  button.go{background:linear-gradient(135deg,var(--accent),var(--accent2));border:0;border-radius:12px;color:#fff;
        font-weight:700;padding:13px 26px;font-size:15px;cursor:pointer;transition:.16s;box-shadow:0 6px 18px rgba(255,92,26,.30);
        position:relative;overflow:hidden}
  button.go:hover{filter:brightness(1.06)} button.go:disabled{opacity:.45;cursor:not-allowed;box-shadow:none}
  .chip{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 15px;cursor:pointer;
        transition:.16s;font-size:14px;display:flex;align-items:center;gap:8px}
  .chip:hover{border-color:var(--accent);transform:translateY(-1px)}
  .chip.sel{border-color:var(--accent);background:linear-gradient(180deg,rgba(255,92,26,.14),transparent)}

  /* metadata widgets */
  .widgets{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:8px 0 22px}
  .widget{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:14px;padding:14px 16px}
  .widget .k{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);margin-bottom:6px}
  .widget .v{font-size:18px;font-weight:700}
  .widget .v.small{font-size:13px;font-weight:600;line-height:1.5}
  .facts{display:none;margin-bottom:20px}
  .factchips{display:flex;flex-wrap:wrap;gap:8px}
  .factchips span{background:#0e1420;border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:13px}

  /* caption cards */
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
  .card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;
        padding:18px;min-height:150px;position:relative;overflow:hidden}
  .card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent)}
  .card.formal:before{background:var(--formal)} .card.sarcastic:before{background:var(--sarcastic)}
  .card.humorous_tech:before{background:var(--htech)} .card.humorous_non_tech:before{background:var(--hnon)}
  .card h2{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;margin-bottom:12px;display:flex;
           justify-content:space-between;align-items:center;gap:8px}
  .card.formal h2 .nm{color:var(--formal)} .card.sarcastic h2 .nm{color:var(--sarcastic)}
  .card.humorous_tech h2 .nm{color:var(--htech)} .card.humorous_non_tech h2 .nm{color:var(--hnon)}
  .badge{font-size:11px;color:var(--good);border:1px solid var(--good);border-radius:999px;padding:2px 10px;display:none;white-space:nowrap}
  .cap{font-size:16.5px;line-height:1.55;min-height:48px}.cap.dimtxt{color:var(--dim)}
  .cardtools{display:flex;gap:8px;margin-top:14px;opacity:0;transition:.16s}
  .card:hover .cardtools{opacity:1}
  .tool{font-size:12px;color:var(--dim);background:#0e1420;border:1px solid var(--line);border-radius:8px;padding:5px 10px;cursor:pointer;transition:.16s}
  .tool:hover{color:var(--text);border-color:var(--accent)}
  .warn{margin-top:10px;font-size:12.5px;color:#ff7a7a;display:none}
  .footer{margin-top:26px;color:var(--dim);font-size:12.5px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
  .kbd{background:#0e1420;border:1px solid var(--line);border-radius:6px;padding:1px 7px;font-size:12px}
  .toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--card2);
         border:1px solid var(--line);color:var(--text);padding:10px 18px;border-radius:10px;opacity:0;transition:.25s;pointer-events:none;z-index:50}
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  .skel{background:linear-gradient(90deg,#141b2b,#1b2437,#141b2b);background-size:200% 100%;animation:sh 1.2s infinite;border-radius:6px;height:14px;margin:6px 0}
  @keyframes sh{to{background-position:-200% 0}}
  .hidden{display:none!important}
</style></head><body><div class="wrap">
__BODY__
</div><div class="toast" id="toast"></div>
<script>
__SCRIPT__
</script></body></html>"""


BODY = r"""
<header>
  <div class="brand"><div class="logo">4</div>
    <div><h1>Four<b>Cast</b></h1><div class="tag">Four Voices for Every Video · AI Captioning Studio</div></div>
  </div>
  <div class="statuses">
    <span class="pill gcp"><span class="g"></span>Hosted on __HOST__</span>
    <span class="pill amd"><span class="g"></span>Inference · __INFER__</span>
    <span class="pill team">Team&nbsp;Mindflayer</span>
  </div>
</header>
<div class="sub">One clip in, every voice out. Frames are read off the video and grounded into a scene report,
then written in four tones — each caption is scored by an in-house judge before you ever see it.</div>

<div class="studio">
  <div class="stage-wrap">
    <div class="stage" id="stage">
      <video id="vid" playsinline crossorigin="anonymous" preload="metadata"></video>
      <div class="empty" id="empty">
        <div class="particles" id="particles"></div>
        <div class="orb"></div>
        <h3>Drop Your Video or Paste a Link</h3>
        <p>Pick an example below, or paste any .mp4 URL (30s to 2min). The AI reads it, then writes four voices.</p>
      </div>
      <div class="proc" id="proc">
        <div class="scanline"></div>
        <div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>
        <div class="steps" id="steps"></div>
      </div>
      <div class="capoverlay hidden" id="capov"><div class="capbox theme-glass" id="capbox"><span class="lbl" id="caplbl"></span><span id="captxt"></span></div></div>
      <div class="controls" id="controls">
        <div class="timeline" id="timeline">
          <div class="track"></div><div class="buffered" id="buffered"></div><div class="fill" id="fill"></div>
          <div class="scrub" id="scrub"></div><div class="tip" id="tip"></div>
        </div>
        <div class="ctrlrow">
          <button class="cbtn" id="b10">-10<span class="tt">Back 10s</span></button>
          <button class="cbtn" id="b5">-5<span class="tt">Back 5s</span></button>
          <button class="cbtn" id="pp">&#9654;<span class="tt">Play / Pause (Space)</span></button>
          <button class="cbtn" id="f5">+5<span class="tt">Forward 5s</span></button>
          <button class="cbtn" id="f10">+10<span class="tt">Forward 10s</span></button>
          <button class="cbtn" id="fb">&#10554;<span class="tt">Previous Frame</span></button>
          <button class="cbtn" id="ff">&#10555;<span class="tt">Next Frame</span></button>
          <span class="volwrap" style="display:flex;align-items:center">
            <button class="cbtn" id="mute">&#128266;<span class="tt">Mute (M)</span></button>
            <input class="vol" id="vol" type="range" min="0" max="1" step="0.05" value="1">
          </span>
          <span class="time" id="time">0:00 / 0:00</span>
          <span class="spacer"></span>
          <button class="cbtn wide" id="speed">1x<span class="tt">Playback Speed</span></button>
          <button class="cbtn" id="loop">&#8635;<span class="tt">Loop</span></button>
          <button class="cbtn on" id="captgl">CC<span class="tt">Captions On / Off</span></button>
          <button class="cbtn" id="pip">&#9647;<span class="tt">Picture-in-Picture</span></button>
          <button class="cbtn" id="dl">&#8681;<span class="tt">Download Clip</span></button>
          <button class="cbtn" id="fs">&#9974;<span class="tt">Fullscreen (F)</span></button>
        </div>
      </div>
      <div class="glow"></div>
    </div>
  </div>
</div>

<div class="studiobar hidden" id="capbar">
  <span style="color:var(--dim);font-size:13px">Caption On Video:</span>
  <span id="capstyles" style="display:flex;gap:6px"></span>
  <button class="cbtn" id="capminus" style="width:34px;height:34px">A-<span class="tt">Smaller</span></button>
  <button class="cbtn" id="capplus" style="width:34px;height:34px">A+<span class="tt">Larger</span></button>
  <span style="color:var(--dim);font-size:12px;margin-left:6px">Opacity</span>
  <input id="capop" type="range" min="0.25" max="1" step="0.05" value="0.9" style="accent-color:var(--accent);width:90px">
  <button class="cbtn wide" id="captheme">Theme: Glass</button>
</div>

<div class="row" id="picker"></div>
<div class="row">
  <input class="url" id="url" placeholder="…or paste any .mp4 URL (30s to 2min)">
  <button class="go" id="go" onclick="run()">Caption It</button>
</div>
<div id="stagetxt" style="color:var(--dim);font-size:14px;min-height:20px;margin-bottom:16px"></div>

<div class="widgets hidden" id="widgets">
  <div class="widget"><div class="k">Judge · Avg Accuracy</div><div class="v" id="wacc">–</div></div>
  <div class="widget"><div class="k">Judge · Avg Style</div><div class="v" id="wsty">–</div></div>
  <div class="widget"><div class="k">Wall-Clock</div><div class="v" id="wtime">–</div></div>
  <div class="widget"><div class="k">Pipeline</div><div class="v small" id="wmodels">–</div></div>
</div>
<div class="facts" id="facts"><div class="factchips" id="chips"></div></div>

<div class="row hidden" id="toolbar">
  <button class="chip" onclick="downloadJSON()">&#8681; Download results.json</button>
  <button class="chip" onclick="run()">&#8635; Re-run Clip</button>
</div>
<div class="grid" id="grid"></div>
<div class="footer" id="footer"></div>
"""


SCRIPT = r"""
const EXAMPLES = __EXAMPLES__;
const STYLES = {formal:"Formal", sarcastic:"Sarcastic", humorous_tech:"Humorous · Tech", humorous_non_tech:"Humorous · Non-tech"};
const STAGES = ["Loading Video","Sampling Frames","Kimi K2.6 Watching","Grounding Scene Report",
                "Writing Four Voices","Judge Scoring & Selecting","Packaging Results"];
let LAST=null, capStyle="formal", capSize=20, capThemes=["glass","classic","neon"], capThemeIdx=0;

const $=id=>document.getElementById(id);
function toast(m){const t=$("toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),1600);}
function fmt(s){s=Math.max(0,s||0);const m=Math.floor(s/60),x=Math.floor(s%60);return m+":"+(x<10?"0":"")+x;}

// particles + picker
(function(){const p=$("particles");for(let i=0;i<18;i++){const s=document.createElement("i");
  s.style.left=(Math.random()*100)+"%";s.style.animationDuration=(4+Math.random()*5)+"s";
  s.style.animationDelay=(Math.random()*5)+"s";s.style.opacity=(.3+Math.random()*.5);p.appendChild(s);}})();
const picker=$("picker");
Object.entries(EXAMPLES).forEach(([name,u])=>{const d=document.createElement("div");d.className="chip";
  d.innerHTML='<span style="width:8px;height:8px;border-radius:50%;background:var(--accent)"></span>'+name;
  d.onclick=()=>{document.querySelectorAll("#picker .chip").forEach(c=>c.classList.remove("sel"));d.classList.add("sel");$("url").value=u;};
  picker.appendChild(d);});
$("url").addEventListener("keydown",e=>{if(e.key==="Enter")run();});

// ripple micro-interaction on primary button
$("go").addEventListener("click",e=>{const r=document.createElement("span");const d=Math.max(e.currentTarget.offsetWidth,60);
  r.style.cssText="position:absolute;border-radius:50%;background:rgba(255,255,255,.35);transform:translate(-50%,-50%);pointer-events:none;width:"+d+"px;height:"+d+"px;left:"+e.offsetX+"px;top:"+e.offsetY+"px;animation:rip .6s ease-out";
  e.currentTarget.appendChild(r);setTimeout(()=>r.remove(),600);});
const style=document.createElement("style");style.textContent="@keyframes rip{to{opacity:0;width:260px;height:260px}}";document.head.appendChild(style);

function renderSteps(active,done){const el=$("steps");el.innerHTML=STAGES.map((s,i)=>{
  const cls=i<done?"done":(i===active?"active":"");const ic=i<done?"&#10003;":(i+1);
  return '<div class="step '+cls+'"><span class="ic">'+ic+'</span>'+s+'</div>';}).join("");}

async function run(){
  const url=$("url").value.trim(); if(!url){toast("Pick a clip or paste an .mp4 URL");return;}
  const go=$("go"); go.disabled=true; LAST=null;
  $("empty").classList.add("hidden"); $("facts").style.display="none";
  $("widgets").classList.add("hidden"); $("toolbar").classList.add("hidden");
  $("capbar").classList.add("hidden"); $("capov").classList.add("hidden");
  $("footer").innerHTML=""; $("grid").innerHTML=""; $("controls").style.display="none";
  const vid=$("vid"); vid.style.display="none"; $("stage").classList.remove("ready");
  // cinematic processing sequence
  $("proc").style.display="flex"; let step=0; renderSteps(0,0);
  $("stagetxt").textContent="Reading the clip and writing four voices…";
  const tick=setInterval(()=>{ if(step<STAGES.length-1){step++;renderSteps(step,step);} },5200);
  try{
    const r=await fetch("/api/caption",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({video_url:url})});
    if(!r.ok) throw new Error("server "+r.status);
    const data=await r.json(); LAST=data; clearInterval(tick); renderSteps(STAGES.length,STAGES.length);
    await new Promise(z=>setTimeout(z,450));
    // reveal player
    $("proc").style.display="none"; vid.src=url; vid.style.display="block"; $("controls").style.display="flex";
    $("stage").classList.add("ready");
    initMarks(); wireCaptionBar(); $("capbar").classList.remove("hidden");
    setCap(capStyle); $("capov").classList.remove("hidden");
    // facts
    const s=data.scene||{}; const chips=$("chips"); chips.innerHTML="";
    [...(s.subjects||[]),...(s.actions||[]).slice(0,3),...(s.distinctive_details||[]).slice(0,4)]
      .forEach(f=>{const e=document.createElement("span");e.textContent=f;chips.appendChild(e);});
    if(chips.children.length) $("facts").style.display="block";
    // cards
    Object.entries(data.captions||{}).forEach(([st,d])=>cardFor(st,d));
    // widgets
    const vals=Object.values(data.captions||{});
    const avg=k=>vals.length?(vals.reduce((a,b)=>a+(b[k]||0),0)/vals.length):0;
    $("wacc").textContent=avg("accuracy").toFixed(2); $("wsty").textContent=avg("style").toFixed(2);
    $("wtime").textContent=data.elapsed_s+"s"; const m=data.models||{};
    $("wmodels").innerHTML="vision "+(m.vision||"?")+"<br>stylist "+(m.stylist||"?")+"<br>judge "+(m.judge||"?");
    $("widgets").classList.remove("hidden"); $("toolbar").classList.remove("hidden");
    $("stagetxt").textContent="Done in "+data.elapsed_s+"s — every caption beat two siblings in front of the judge.";
    $("footer").innerHTML="<span>Hosted on <span class='kbd'>"+(data.host||"?")+"</span></span>"+
      "<span>Inference <span class='kbd'>"+(data.inference||"?")+"</span></span>"+
      "<span><span class='kbd'>"+data.elapsed_s+"s</span> wall-clock</span>";
  }catch(e){clearInterval(tick);$("proc").style.display="none";$("empty").classList.remove("hidden");
    $("stagetxt").textContent="Something failed: "+e.message;}
  go.disabled=false;
}

function cardFor(st,d){
  const c=document.createElement("div"); c.className="card "+st; c.id="card-"+st;
  c.innerHTML='<h2><span class="nm">'+STYLES[st]+'</span><span class="badge">judge '+(d.accuracy??0).toFixed(2)+' / '+(d.style??0).toFixed(2)+'</span></h2>'+
    '<div class="cap">'+d.text+'</div>'+
    '<div class="cardtools"><span class="tool t-copy">&#10697; Copy</span><span class="tool t-regen">&#8635; Regenerate</span><span class="tool t-show">&#9655; Show on video</span></div>'+
    '<div class="warn"></div>';
  c.querySelector(".badge").style.display="inline-block";
  c.querySelector(".t-copy").onclick=()=>{navigator.clipboard.writeText(LAST.captions[st].text);toast("Caption copied");};
  c.querySelector(".t-regen").onclick=()=>regen(st);
  c.querySelector(".t-show").onclick=()=>{setCap(st);toast(STYLES[st]+" on video");};
  const w=c.querySelector(".warn"); if(d.jargon&&d.jargon.length){w.style.display="block";w.textContent="\u26a0 jargon firewall flagged: "+d.jargon.join(", ");}
  $("grid").appendChild(c);
}

async function regen(st){
  if(!LAST||!LAST.scene)return; const c=$("card-"+st); const cap=c.querySelector(".cap");
  cap.classList.add("dimtxt"); cap.textContent="Regenerating…";
  try{const r=await fetch("/api/restyle",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scene:LAST.scene,style:st})});
    const d=await r.json(); LAST.captions[st]=d; cap.classList.remove("dimtxt"); cap.textContent=d.text;
    c.querySelector(".badge").textContent="judge "+(d.accuracy??0).toFixed(2)+" / "+(d.style??0).toFixed(2);
    const w=c.querySelector(".warn"); if(d.jargon&&d.jargon.length){w.style.display="block";w.textContent="\u26a0 jargon firewall flagged: "+d.jargon.join(", ");}else w.style.display="none";
    if(capStyle===st) setCap(st); toast("Regenerated");
  }catch(e){toast("Regenerate failed");}
}

function downloadJSON(){ if(!LAST)return;
  const out=[{task_id:"demo",captions:Object.fromEntries(Object.entries(LAST.captions).map(([k,v])=>[k,v.text]))}];
  const b=new Blob([JSON.stringify(out,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="results.json";a.click();}

/* ---------- caption overlay controls ---------- */
function setCap(st){ capStyle=st; const d=(LAST&&LAST.captions&&LAST.captions[st])||{text:""};
  $("caplbl").textContent=STYLES[st]; const t=$("captxt"); t.style.opacity=0;
  setTimeout(()=>{t.textContent=d.text; $("capbox").style.fontSize=capSize+"px"; t.style.opacity=1;},120);
  document.querySelectorAll("#capstyles .cbtn").forEach(b=>b.classList.toggle("on",b.dataset.s===st));}
function wireCaptionBar(){
  const cs=$("capstyles"); cs.innerHTML="";
  Object.keys(STYLES).forEach(st=>{const b=document.createElement("button");b.className="cbtn wide"+(st===capStyle?" on":"");
    b.dataset.s=st;b.textContent=STYLES[st].replace("Humorous · ","H·");b.onclick=()=>setCap(st);cs.appendChild(b);});
  $("capminus").onclick=()=>{capSize=Math.max(13,capSize-2);$("capbox").style.fontSize=capSize+"px";};
  $("capplus").onclick=()=>{capSize=Math.min(34,capSize+2);$("capbox").style.fontSize=capSize+"px";};
  $("capop").oninput=e=>{$("capbox").style.background=$("capbox").className.includes("theme-classic")?
    "rgba(0,0,0,"+e.target.value+")":"rgba(8,10,16,"+e.target.value+")";};
  $("captheme").onclick=()=>{capThemeIdx=(capThemeIdx+1)%capThemes.length;const th=capThemes[capThemeIdx];
    $("capbox").className="capbox theme-"+th;$("captheme").textContent="Theme: "+th[0].toUpperCase()+th.slice(1);};
}

/* ---------- video player wiring ---------- */
const vid=$("vid");
function playpause(){ vid.paused?vid.play():vid.pause(); }
vid.addEventListener("play",()=>{$("pp").innerHTML="&#10073;&#10073;";$("stage").classList.remove("paused");});
vid.addEventListener("pause",()=>{$("pp").innerHTML="&#9654;";$("stage").classList.add("paused");});
$("pp").onclick=playpause;
$("b5").onclick=()=>vid.currentTime-=5; $("f5").onclick=()=>vid.currentTime+=5;
$("b10").onclick=()=>vid.currentTime-=10; $("f10").onclick=()=>vid.currentTime+=10;
$("fb").onclick=()=>{vid.pause();vid.currentTime-=1/30;}; $("ff").onclick=()=>{vid.pause();vid.currentTime+=1/30;};
$("mute").onclick=()=>{vid.muted=!vid.muted;$("mute").innerHTML=vid.muted?"&#128263;":"&#128266;";};
$("vol").oninput=e=>{vid.volume=e.target.value;vid.muted=false;};
const speeds=[0.5,1,1.5,2]; let si=1;
$("speed").onclick=()=>{si=(si+1)%speeds.length;vid.playbackRate=speeds[si];$("speed").firstChild.textContent=speeds[si]+"x";};
$("loop").onclick=()=>{vid.loop=!vid.loop;$("loop").classList.toggle("on",vid.loop);};
$("captgl").onclick=()=>{const on=$("capov").classList.toggle("hidden");$("captgl").classList.toggle("on",!on);};
$("pip").onclick=()=>{try{document.pictureInPictureElement?document.exitPictureInPicture():vid.requestPictureInPicture();}catch(e){toast("PiP unavailable");}};
$("dl").onclick=()=>{const a=document.createElement("a");a.href=vid.src;a.download="clip.mp4";a.target="_blank";a.click();};
$("fs").onclick=()=>{const st=$("stage");document.fullscreenElement?document.exitFullscreen():st.requestFullscreen&&st.requestFullscreen();};

const tl=$("timeline");
vid.addEventListener("timeupdate",()=>{const p=vid.currentTime/(vid.duration||1);
  $("fill").style.width=(p*100)+"%"; $("scrub").style.left=(p*100)+"%";
  $("time").textContent=fmt(vid.currentTime)+" / "+fmt(vid.duration);});
vid.addEventListener("progress",()=>{ if(vid.buffered.length){const e=vid.buffered.end(vid.buffered.length-1);
  $("buffered").style.width=((e/(vid.duration||1))*100)+"%";}});
function seekAt(clientX){const r=tl.getBoundingClientRect();const p=Math.min(1,Math.max(0,(clientX-r.left)/r.width));vid.currentTime=p*(vid.duration||0);}
tl.addEventListener("click",e=>seekAt(e.clientX));
tl.addEventListener("mousemove",e=>{const r=tl.getBoundingClientRect();const p=(e.clientX-r.left)/r.width;
  const tip=$("tip");tip.style.display="block";tip.style.left=((e.clientX-r.left))+"px";tip.textContent=fmt(p*(vid.duration||0));});
tl.addEventListener("mouseleave",()=>$("tip").style.display="none");
function initMarks(){ document.querySelectorAll(".mark").forEach(m=>m.remove());
  const put=()=>{ const dur=vid.duration||LAST.duration||0; if(!dur||!LAST.frame_marks)return;
    LAST.frame_marks.forEach(t=>{const m=document.createElement("div");m.className="mark";m.title="AI sampled frame @ "+fmt(t);
      m.style.left=((t/dur)*100)+"%";tl.appendChild(m);}); };
  if(vid.duration) put(); else vid.addEventListener("loadedmetadata",put,{once:true}); }

document.addEventListener("keydown",e=>{ if(!$("stage").classList.contains("ready"))return;
  if(e.target.tagName==="INPUT")return;
  if(e.code==="Space"){e.preventDefault();playpause();}
  else if(e.key==="ArrowRight")vid.currentTime+=5; else if(e.key==="ArrowLeft")vid.currentTime-=5;
  else if(e.key.toLowerCase()==="m")$("mute").click(); else if(e.key.toLowerCase()==="f")$("fs").click(); });

// mouse-responsive parallax lighting on the stage
const stage=$("stage");
stage.addEventListener("mousemove",e=>{const r=stage.getBoundingClientRect();
  const x=(e.clientX-r.left)/r.width-0.5, y=(e.clientY-r.top)/r.height-0.5;
  stage.style.transform="perspective(1200px) rotateY("+(x*2.2)+"deg) rotateX("+(-y*2.2)+"deg)";});
stage.addEventListener("mouseleave",()=>stage.style.transform="none");
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    import json as _json

    html = PAGE.replace("__BODY__", BODY).replace("__SCRIPT__", SCRIPT)
    html = html.replace("__HOST__", HOST_LABEL).replace("__INFER__", INFER_LABEL)
    html = html.replace("__EXAMPLES__", _json.dumps(EXAMPLES))
    return html
