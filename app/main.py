"""FourCast demo UI — same image as the submission agent, different CMD.

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import asyncio

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent.pipeline import process_clip_verbose

app = FastAPI(title="FourCast", version="1.0.0")

EXAMPLES = {
    "Autumn boulevard": "https://storage.googleapis.com/amd-hackathon-clips/1860079-uhd_2560_1440_25fps.mp4",
    "Garden kitten": "https://storage.googleapis.com/amd-hackathon-clips/13825391-uhd_3840_2160_30fps.mp4",
    "Office worker": "https://storage.googleapis.com/amd-hackathon-clips/3044693-uhd_3840_2160_24fps.mp4",
}


class CaptionRequest(BaseModel):
    video_url: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "product": "FourCast"}


@app.post("/api/caption")
async def api_caption(req: CaptionRequest) -> dict:
    task = {"task_id": "demo", "video_url": req.video_url}
    scene, detailed = await asyncio.wait_for(process_clip_verbose(task), timeout=240)
    return {"scene": scene, "captions": detailed}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FourCast — four voices for every video</title>
<style>
  :root { --bg:#0b0e14; --card:#141a26; --line:#232c3d; --text:#e8edf7; --dim:#8b96ab;
          --accent:#ff5c1a; --good:#3ddc84; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--text); font:16px/1.55 system-ui,Segoe UI,sans-serif; padding:32px 20px 80px; }
  .wrap { max-width:1060px; margin:0 auto; }
  h1 { font-size:34px; letter-spacing:-.5px; } h1 b { color:var(--accent); }
  .sub { color:var(--dim); margin:6px 0 26px; }
  .picker { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }
  .chip { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px 16px;
          cursor:pointer; transition:.15s; } .chip:hover,.chip.sel { border-color:var(--accent); }
  .row { display:flex; gap:10px; margin-bottom:26px; }
  input { flex:1; background:var(--card); border:1px solid var(--line); border-radius:10px;
          color:var(--text); padding:12px 14px; font-size:15px; }
  button { background:var(--accent); border:0; border-radius:10px; color:#fff; font-weight:700;
           padding:12px 26px; font-size:15px; cursor:pointer; } button:disabled { opacity:.45; }
  .stage { color:var(--dim); min-height:24px; margin-bottom:18px; font-size:14px; }
  .facts { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin-bottom:22px; display:none; }
  .facts h3 { font-size:13px; text-transform:uppercase; letter-spacing:1px; color:var(--dim); margin-bottom:8px; }
  .factchips { display:flex; flex-wrap:wrap; gap:8px; }
  .factchips span { background:#0f1420; border:1px solid var(--line); border-radius:999px; padding:4px 12px; font-size:13px; color:var(--text); }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; min-height:130px; }
  .card h2 { font-size:12px; text-transform:uppercase; letter-spacing:1.4px; color:var(--accent); margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;}
  .badge { font-size:11px; color:var(--good); border:1px solid var(--good); border-radius:999px; padding:2px 10px; letter-spacing:.5px;}
  .cap { font-size:16.5px; } .dimtxt { color:var(--dim); }
</style></head><body><div class="wrap">
<h1>Four<b>Cast</b></h1>
<div class="sub">One clip in, every voice out — grounded captions in four tones, self-judged before you ever see them.</div>
<div class="picker" id="picker"></div>
<div class="row"><input id="url" placeholder="…or paste any .mp4 URL (30s–2min)">
<button id="go" onclick="run()">Caption it</button></div>
<div class="stage" id="stage"></div>
<div class="facts" id="facts"><h3>What the model actually saw (scene report)</h3><div class="factchips" id="chips"></div></div>
<div class="grid" id="grid"></div>
<script>
const EXAMPLES = __EXAMPLES__;
const STYLES = {formal:"Formal", sarcastic:"Sarcastic", humorous_tech:"Humorous · Tech", humorous_non_tech:"Humorous · Non-tech"};
const picker = document.getElementById('picker');
Object.entries(EXAMPLES).forEach(([name,u])=>{
  const d=document.createElement('div'); d.className='chip'; d.textContent=name;
  d.onclick=()=>{document.querySelectorAll('.chip').forEach(c=>c.classList.remove('sel'));d.classList.add('sel');document.getElementById('url').value=u;};
  picker.appendChild(d);
});
function card(style){ return `<div class="card" id="card-${style}"><h2>${STYLES[style]}<span class="badge" style="display:none"></span></h2><div class="cap dimtxt">…</div></div>`; }
async function run(){
  const url=document.getElementById('url').value.trim(); if(!url) return;
  const go=document.getElementById('go'); go.disabled=true;
  document.getElementById('facts').style.display='none';
  document.getElementById('grid').innerHTML=Object.keys(STYLES).map(card).join('');
  const stage=document.getElementById('stage');
  const steps=["Sampling frames straight off the video…","Kimi K2.6 is watching the clip…","Writing candidates in four voices (GLM 5.2)…","The in-house judge is rejecting the weak ones…"];
  let i=0; stage.textContent=steps[0];
  const tick=setInterval(()=>{ i=(i+1)%steps.length; stage.textContent=steps[i]; },7000);
  try{
    const r=await fetch('/api/caption',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_url:url})});
    const data=await r.json(); clearInterval(tick); stage.textContent="Done — every caption below beat its siblings in front of the judge.";
    const chips=document.getElementById('chips'); chips.innerHTML='';
    const s=data.scene||{};
    [...(s.subjects||[]),...(s.actions||[]).slice(0,3),...(s.distinctive_details||[]).slice(0,4)].forEach(f=>{const el=document.createElement('span');el.textContent=f;chips.appendChild(el);});
    if(chips.children.length) document.getElementById('facts').style.display='block';
    Object.entries(data.captions||{}).forEach(([style,d])=>{
      const c=document.getElementById('card-'+style); if(!c) return;
      c.querySelector('.cap').textContent=d.text; c.querySelector('.cap').classList.remove('dimtxt');
      const b=c.querySelector('.badge'); b.style.display='inline-block';
      b.textContent=`judge ${(d.accuracy??0).toFixed(2)} / ${(d.style??0).toFixed(2)}`;
    });
  }catch(e){ clearInterval(tick); stage.textContent="Something failed: "+e; }
  go.disabled=false;
}
</script></div></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    import json as _json

    return PAGE.replace("__EXAMPLES__", _json.dumps(EXAMPLES))
