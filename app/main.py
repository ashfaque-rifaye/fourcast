"""FourCast demo UI — same image as the submission agent, different CMD.

    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

Endpoints:
  GET  /                 the single-page dark UI
  GET  /health           liveness probe (used by Cloud Run)
  POST /api/caption      {video_url} -> {scene, captions, elapsed_s, models}
  POST /api/restyle      {scene, style} -> {text, accuracy, style}  (per-card regenerate)
"""
import asyncio
import os
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import contracts, fw
from agent.pipeline import caption_style, process_clip_verbose

app = FastAPI(title="FourCast", version="1.1.0")

EXAMPLES = {
    "Autumn boulevard": "https://storage.googleapis.com/amd-hackathon-clips/1860079-uhd_2560_1440_25fps.mp4",
    "Garden kitten": "https://storage.googleapis.com/amd-hackathon-clips/13825391-uhd_3840_2160_30fps.mp4",
    "Office worker": "https://storage.googleapis.com/amd-hackathon-clips/3044693-uhd_3840_2160_24fps.mp4",
}


class CaptionRequest(BaseModel):
    video_url: str


class RestyleRequest(BaseModel):
    scene: dict
    style: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "FourCast", "version": app.version}


@app.post("/api/caption")
async def api_caption(req: CaptionRequest) -> dict:
    t0 = time.perf_counter()
    task = {"task_id": "demo", "video_url": req.video_url}
    scene, detailed = await asyncio.wait_for(process_clip_verbose(task), timeout=240)
    # surface jargon-firewall hits on the non-tech card for the "money moment"
    for style, d in detailed.items():
        d["jargon"] = contracts.jargon_violations(d.get("text", "")) if style == "humorous_non_tech" else []
    return {
        "scene": scene,
        "captions": detailed,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "models": {"vision": fw.VISION_MODEL.split("/")[-1],
                   "stylist": fw.STYLIST_MODEL.split("/")[-1],
                   "judge": fw.JUDGE_MODEL.split("/")[-1]},
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
<title>FourCast — four voices for every video</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
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
       padding:34px 20px 90px;min-height:100vh}
  .wrap{max-width:1120px;margin:0 auto}
  header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:6px}
  .brand{display:flex;align-items:center;gap:12px}
  .logo{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--accent2));
        display:grid;place-items:center;font-weight:800;font-size:20px;color:#fff;box-shadow:0 6px 20px rgba(255,92,26,.35)}
  h1{font-size:30px;letter-spacing:-.6px;font-weight:800}
  h1 b{color:var(--accent)}
  .pill{font-size:12px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:6px 12px}
  .sub{color:var(--dim);margin:10px 0 26px;max-width:760px}
  .picker{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
  .chip{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 16px;cursor:pointer;
        transition:.16s;font-size:14px;display:flex;align-items:center;gap:8px}
  .chip:hover{border-color:var(--accent);transform:translateY(-1px)}
  .chip.sel{border-color:var(--accent);background:linear-gradient(180deg,rgba(255,92,26,.14),transparent)}
  .chip .dot{width:8px;height:8px;border-radius:50%;background:var(--accent)}
  .row{display:flex;gap:10px;margin-bottom:22px;flex-wrap:wrap}
  input{flex:1;min-width:240px;background:var(--card);border:1px solid var(--line);border-radius:12px;
        color:var(--text);padding:13px 15px;font-size:15px;outline:none;transition:.16s}
  input:focus{border-color:var(--accent)}
  button.go{background:linear-gradient(135deg,var(--accent),var(--accent2));border:0;border-radius:12px;color:#fff;
        font-weight:700;padding:13px 28px;font-size:15px;cursor:pointer;transition:.16s;box-shadow:0 6px 18px rgba(255,92,26,.30)}
  button.go:hover{filter:brightness(1.06)} button.go:disabled{opacity:.45;cursor:not-allowed;box-shadow:none}
  .stage{color:var(--dim);min-height:22px;margin-bottom:18px;font-size:14px;display:flex;align-items:center;gap:10px}
  .spin{width:14px;height:14px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;
        animation:sp .8s linear infinite;display:none}
  @keyframes sp{to{transform:rotate(360deg)}}
  .facts{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;
         padding:16px 18px;margin-bottom:22px;display:none}
  .facts h3{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:var(--dim);margin-bottom:10px;
            display:flex;justify-content:space-between;align-items:center}
  .factchips{display:flex;flex-wrap:wrap;gap:8px}
  .factchips span{background:#0e1420;border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:13px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
  .card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;
        padding:18px;min-height:150px;position:relative;overflow:hidden;transition:.16s}
  .card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent)}
  .card.formal:before{background:var(--formal)} .card.sarcastic:before{background:var(--sarcastic)}
  .card.humorous_tech:before{background:var(--htech)} .card.humorous_non_tech:before{background:var(--hnon)}
  .card h2{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;margin-bottom:12px;display:flex;
           justify-content:space-between;align-items:center;gap:8px}
  .card.formal h2 .nm{color:var(--formal)} .card.sarcastic h2 .nm{color:var(--sarcastic)}
  .card.humorous_tech h2 .nm{color:var(--htech)} .card.humorous_non_tech h2 .nm{color:var(--hnon)}
  .badge{font-size:11px;color:var(--good);border:1px solid var(--good);border-radius:999px;padding:2px 10px;
         letter-spacing:.3px;display:none;white-space:nowrap}
  .cap{font-size:16.5px;line-height:1.55;min-height:48px}
  .cap.dimtxt{color:var(--dim)}
  .cardtools{display:flex;gap:8px;margin-top:14px;opacity:0;transition:.16s}
  .card:hover .cardtools{opacity:1}
  .tool{font-size:12px;color:var(--dim);background:#0e1420;border:1px solid var(--line);border-radius:8px;
        padding:5px 10px;cursor:pointer;transition:.16s}
  .tool:hover{color:var(--text);border-color:var(--accent)}
  .warn{margin-top:10px;font-size:12.5px;color:#ff7a7a;display:none}
  .toolbar{display:none;gap:10px;margin:20px 0 6px}
  .footer{margin-top:28px;color:var(--dim);font-size:12.5px;display:flex;gap:16px;flex-wrap:wrap}
  .kbd{background:#0e1420;border:1px solid var(--line);border-radius:6px;padding:1px 7px;font-size:12px}
  .toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--card2);
         border:1px solid var(--line);color:var(--text);padding:10px 18px;border-radius:10px;opacity:0;
         transition:.25s;pointer-events:none}
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  .skel{background:linear-gradient(90deg,#141b2b,#1b2437,#141b2b);background-size:200% 100%;
        animation:sh 1.2s infinite;border-radius:6px;height:14px;margin:6px 0}
  @keyframes sh{to{background-position:-200% 0}}
</style></head><body><div class="wrap">
<header>
  <div class="brand"><div class="logo">4</div>
    <div><h1>Four<b>Cast</b></h1><div style="color:var(--dim);font-size:13px">four voices for every video</div></div>
  </div>
  <div class="pill">AMD ACT II · Track 2 · team mindflayer</div>
</header>
<div class="sub">One clip in, every voice out. Frames are read off the video, grounded into a scene report,
then written in four tones — each caption beats two rivals in front of an in-house judge before you see it.</div>

<div class="picker" id="picker"></div>
<div class="row">
  <input id="url" placeholder="…or paste any .mp4 URL (30s–2min)">
  <button class="go" id="go" onclick="run()">Caption it</button>
</div>
<div class="stage" id="stage"><span class="spin" id="spin"></span><span id="stagetxt"></span></div>

<div class="facts" id="facts">
  <h3><span>What the model actually saw — scene report</span><span id="setting" style="color:var(--dim);text-transform:none;letter-spacing:0"></span></h3>
  <div class="factchips" id="chips"></div>
</div>

<div class="toolbar" id="toolbar">
  <button class="tool" onclick="downloadJSON()">⬇ Download results.json</button>
  <button class="tool" onclick="run()">↻ Re-run clip</button>
</div>
<div class="grid" id="grid"></div>

<div class="footer" id="footer"></div>
</div>
<div class="toast" id="toast"></div>

<script>
const EXAMPLES = __EXAMPLES__;
const STYLES = {formal:"Formal", sarcastic:"Sarcastic", humorous_tech:"Humorous · Tech", humorous_non_tech:"Humorous · Non-tech"};
let LAST = null;

const picker=document.getElementById('picker');
Object.entries(EXAMPLES).forEach(([name,u])=>{
  const d=document.createElement('div'); d.className='chip'; d.innerHTML=`<span class="dot"></span>${name}`;
  d.onclick=()=>{document.querySelectorAll('.chip').forEach(c=>c.classList.remove('sel'));d.classList.add('sel');document.getElementById('url').value=u;};
  picker.appendChild(d);
});
document.getElementById('url').addEventListener('keydown',e=>{if(e.key==='Enter')run();});

function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1600);}
function skelCard(style){return `<div class="card ${style}"><h2><span class="nm">${STYLES[style]}</span><span class="badge"></span></h2>
  <div class="skel" style="width:92%"></div><div class="skel" style="width:74%"></div></div>`;}
function fillCard(style,d){
  const c=document.getElementById('card-'+style); if(!c) return;
  c.querySelector('.cap')?.remove();
  const skels=c.querySelectorAll('.skel'); skels.forEach(s=>s.remove());
  let cap=document.createElement('div'); cap.className='cap'; cap.textContent=d.text; c.appendChild(cap);
  const b=c.querySelector('.badge'); b.style.display='inline-block';
  b.textContent=`judge ${(d.accuracy??0).toFixed(2)} / ${(d.style??0).toFixed(2)}`;
  let tools=c.querySelector('.cardtools');
  if(!tools){tools=document.createElement('div');tools.className='cardtools';
    tools.innerHTML=`<span class="tool">⧉ Copy</span><span class="tool">↻ Regenerate</span>`;
    tools.children[0].onclick=()=>{navigator.clipboard.writeText(d.text);toast('Caption copied');};
    tools.children[1].onclick=()=>regen(style);
    c.appendChild(tools);}
  let warn=c.querySelector('.warn'); if(!warn){warn=document.createElement('div');warn.className='warn';c.appendChild(warn);}
  if(d.jargon && d.jargon.length){warn.style.display='block';warn.textContent=`⚠ jargon firewall flagged: ${d.jargon.join(', ')}`;}
  else warn.style.display='none';
}
function shell(){document.getElementById('grid').innerHTML=Object.keys(STYLES).map(s=>
  `<div class="card ${s}" id="card-${s}"><h2><span class="nm">${STYLES[s]}</span><span class="badge"></span></h2>
   <div class="skel" style="width:92%"></div><div class="skel" style="width:74%"></div></div>`).join('');}

async function run(){
  const url=document.getElementById('url').value.trim(); if(!url){toast('Pick a clip or paste an .mp4 URL');return;}
  const go=document.getElementById('go'); go.disabled=true;
  document.getElementById('facts').style.display='none';
  document.getElementById('toolbar').style.display='none';
  document.getElementById('footer').textContent='';
  document.getElementById('spin').style.display='inline-block';
  shell();
  const steps=["Sampling frames straight off the video…","Kimi K2.6 is watching the clip…",
    "Writing candidates in four voices…","The in-house judge is rejecting the weak ones…"];
  let i=0; const st=document.getElementById('stagetxt'); st.textContent=steps[0];
  const tick=setInterval(()=>{i=(i+1)%steps.length;st.textContent=steps[i];},6000);
  try{
    const r=await fetch('/api/caption',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_url:url})});
    if(!r.ok) throw new Error('server '+r.status);
    const data=await r.json(); LAST=data; clearInterval(tick);
    document.getElementById('spin').style.display='none';
    st.textContent=`Done in ${data.elapsed_s}s — every caption below beat its siblings in front of the judge.`;
    const s=data.scene||{}; const chips=document.getElementById('chips'); chips.innerHTML='';
    document.getElementById('setting').textContent=s.setting?('· '+s.setting):'';
    [...(s.subjects||[]),...(s.actions||[]).slice(0,3),...(s.distinctive_details||[]).slice(0,4)]
      .forEach(f=>{const e=document.createElement('span');e.textContent=f;chips.appendChild(e);});
    if(chips.children.length) document.getElementById('facts').style.display='block';
    Object.entries(data.captions||{}).forEach(([style,d])=>fillCard(style,d));
    document.getElementById('toolbar').style.display='flex';
    const m=data.models||{};
    document.getElementById('footer').innerHTML=
      `<span>vision <span class="kbd">${m.vision||'?'}</span></span>
       <span>stylist <span class="kbd">${m.stylist||'?'}</span></span>
       <span>judge <span class="kbd">${m.judge||'?'}</span></span>
       <span>${data.elapsed_s}s wall-clock</span>`;
  }catch(e){clearInterval(tick);document.getElementById('spin').style.display='none';
    st.textContent='Something failed: '+e.message;}
  go.disabled=false;
}

async function regen(style){
  if(!LAST||!LAST.scene){toast('Run a clip first');return;}
  const c=document.getElementById('card-'+style);
  c.querySelector('.cap')?.remove();
  const sk=document.createElement('div');sk.className='skel';sk.style.width='80%';c.insertBefore(sk,c.querySelector('.cardtools'));
  try{
    const r=await fetch('/api/restyle',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({scene:LAST.scene,style})});
    const d=await r.json(); LAST.captions[style]=d; fillCard(style,d); toast('Regenerated');
  }catch(e){toast('Regenerate failed');}
}

function downloadJSON(){
  if(!LAST) return;
  const out=[{task_id:'demo',captions:Object.fromEntries(Object.entries(LAST.captions).map(([k,v])=>[k,v.text]))}];
  const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.json';a.click();
}
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    import json as _json

    return PAGE.replace("__EXAMPLES__", _json.dumps(EXAMPLES))
