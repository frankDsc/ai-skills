#!/usr/bin/env python3
"""通用最佳实践 Demo GUI：读取 manifest，渲染卡片 + 架构图 + 动作 + 事件流。"""
import argparse
import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_ROOT)

from flask import Flask, jsonify, request

from lib import manifest as mf
from lib import arch
from gui.backends import get_backend

parser = argparse.ArgumentParser()
parser.add_argument("--manifest", default=os.path.join(SKILL_ROOT, "examples", "bigdata-demo", "manifest.json"))
parser.add_argument("--port", type=int, default=8899)
ARGS = parser.parse_args()

MANIFEST = mf.load(ARGS.manifest)
ICONS_DIR = os.path.join(SKILL_ROOT, "assets", "icons")
ARCH_SVG = arch.build_svg(MANIFEST, ICONS_DIR)
BACKEND = get_backend(MANIFEST)

app = Flask(__name__)


@app.route("/")
def index():
    html = INDEX_HTML
    html = html.replace("__TITLE__", MANIFEST["title"])
    html = html.replace("__SUBTITLE__", MANIFEST.get("subtitle", ""))
    html = html.replace("__REGION__", MANIFEST.get("region", ""))
    html = html.replace("__ARCH_SVG__", ARCH_SVG)
    return html


@app.after_request
def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/status")
def api_status():
    return jsonify(BACKEND.status())


@app.route("/api/actions")
def api_actions():
    return jsonify({"actions": MANIFEST.get("actions", [])})


@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json(force=True, silent=True) or {}
    action = next((a for a in MANIFEST.get("actions", []) if a["id"] == data.get("id")), None)
    if not action:
        return jsonify({"ok": False, "error": "未知动作"}), 400
    return jsonify(BACKEND.execute(action))


@app.route("/api/events")
def api_events():
    return jsonify(BACKEND.events())


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--red:#C7000B;--red-dark:#9E0008;--red-light:#FDECEC;--red-lighter:#FFF4F4;--gray:#4A4A4A;--border:#f0c0c0;--green:#1a9e3b;}
*{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
body{background:#f5f6f8;color:var(--gray);}
header{background:var(--red);color:#fff;padding:16px 32px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 12px rgba(199,0,11,.25);}
header h1{font-size:20px;font-weight:600;}
header .sub{font-size:12px;color:#ffd9db;margin-top:3px;}
.wrap{max-width:1320px;margin:0 auto;padding:16px 20px 40px;}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px;}
.card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px 16px;}
.card .k{font-size:12px;color:#999;}
.card .v{font-size:20px;font-weight:700;margin-top:4px;}
.card .v.green{color:var(--green);} .card .v.red{color:var(--red);}
.stage{background:#fff;border:1px solid var(--border);border-radius:14px;padding:8px 14px 4px;margin-bottom:14px;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,.04);}
svg{width:100%;height:auto;display:block;}
.node{transition:all .3s;}
.shake{animation:shake .5s;}
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-6px)}40%{transform:translateX(6px)}60%{transform:translateX(-4px)}80%{transform:translateX(4px)}}
.shake{animation:shake .5s;}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}50%{transform:translateX(5px)}75%{transform:translateX(-3px)}}
.cols{display:grid;grid-template-columns:420px 1fr;gap:16px;}
.panel{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden;}
.panel .hd{background:var(--red-light);color:var(--red-dark);font-weight:700;padding:11px 16px;font-size:14px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}
.panel .hd button{background:#fff;border:1px solid var(--red);color:var(--red);border-radius:6px;padding:3px 9px;font-size:12px;cursor:pointer;}
.cmd-row{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid #f5e5e5;transition:background .2s;}
.cmd-row:hover{background:var(--red-lighter);}
.cmd-row .nm{font-weight:600;font-size:14px;}
.cmd-row .ds{font-size:12px;color:#999;margin-top:2px;}
.fire{background:var(--red);color:#fff;border:none;border-radius:7px;padding:8px 14px;font-size:13px;cursor:pointer;white-space:nowrap;transition:all .2s;}
.fire:hover{background:var(--red-dark);transform:scale(1.04);}
.fire:disabled{background:#d9a0a4;cursor:not-allowed;transform:none;}
#feed{max-height:420px;overflow:auto;}
.ev{padding:12px 16px;border-bottom:1px solid #f5e5e5;display:flex;justify-content:space-between;align-items:flex-start;opacity:0;transform:translateY(8px);animation:slidein .45s forwards;}
@keyframes slidein{to{opacity:1;transform:translateY(0)}}
.ev .nm{font-weight:600;font-size:13px;}
.ev .cl{font-size:12px;color:#999;margin-top:2px;}
.sev{font-size:11px;font-weight:700;border-radius:4px;padding:2px 8px;white-space:nowrap;}
.sev.High{background:#ffe3e3;color:#c7000b;}
.sev.Medium{background:#fff2df;color:#d97b00;}
.sev.Success{background:#e3f6e8;color:#1a9e3b;}
.sev.Low{background:#f0f0f0;color:#888;}
.empty{text-align:center;color:#bbb;padding:40px;font-size:13px;}
#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#2b2b2b;color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;display:none;z-index:99;box-shadow:0 4px 18px rgba(0,0,0,.25);}
@media(max-width:900px){.cols{grid-template-columns:1fr;}.cards{grid-template-columns:1fr 1fr;}}
</style>
</head>
<body>
<header>
  <div><h1>__TITLE__</h1><div class="sub">__SUBTITLE__</div></div>
  <div style="text-align:right;font-size:12px;color:#ffd9db;">区域：__REGION__<br>计费：按需</div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>
  <div class="stage">__ARCH_SVG__</div>
  <div class="cols">
    <div class="panel">
      <div class="hd"><span>⚡ 可执行动作</span></div>
      <div id="actions"></div>
    </div>
    <div class="panel">
      <div class="hd"><span>📡 事件流（5 秒刷新）</span><button onclick="loadEvents(true)">立即刷新</button></div>
      <div id="feed"><div class="empty">加载中…</div></div>
    </div>
  </div>
</div>
<div id="toast"></div>
<script>
const $=id=>document.getElementById(id);
async function getJSON(u){const r=await fetch(u);return r.json();}
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';clearTimeout(t._x);t._x=setTimeout(()=>t.style.display='none',3000);}

async function loadStatus(){
  try{
    const s=await getJSON('/api/status');
    const box=$('cards'); box.innerHTML='';
    for(const c of (s.cards||[])){
      const el=document.createElement('div'); el.className='card';
      el.innerHTML='<div class="k">'+c.label+'</div><div class="v '+(c.tone||'')+'">'+c.value+'</div>';
      box.appendChild(el);
    }
  }catch(e){}
}

let ACTIONS=[];
async function loadActions(){
  try{
    const d=await getJSON('/api/actions');
    ACTIONS = d.actions || [];
    const box=$('actions'); box.innerHTML='';
    for(const a of (d.actions||[])){
      const el=document.createElement('div'); el.className='cmd-row';
      el.innerHTML='<div><span class="nm">'+a.label+'</span><div class="ds">'+(a.desc||'')+'</div></div><button class="fire" data-id="'+a.id+'">触发</button>';
      box.appendChild(el);
    }
    document.querySelectorAll('button.fire').forEach(b=>b.onclick=()=>fire(b));
  }catch(e){}
}

function animateAlong(path, dot, dur){
  return new Promise(function(res){
    const len=path.getTotalLength();
    const t0=performance.now();
    (function step(t){
      const p=Math.min((t-t0)/dur,1);
      const pt=path.getPointAtLength(p*len);
      dot.setAttribute('cx',pt.x); dot.setAttribute('cy',pt.y);
      if(p<1) requestAnimationFrame(step); else res();
    })(t0);
  });
}

function shakeNode(id){
  const el=document.getElementById('node-'+id);
  if(el){el.classList.add('shake');setTimeout(()=>el.classList.remove('shake'),520);}
}

async function animateFlow(action){
  const flow=action.flow||[];
  const dot=document.getElementById('flowDot');
  if(!dot||!flow.length) return;
  dot.setAttribute('opacity','1');
  shakeNode(flow[0]);
  for(let i=0;i<flow.length-1;i++){
    const path=document.getElementById('flow-'+action.id+'-'+i);
    if(path){ await animateAlong(path, dot, 480); }
    shakeNode(flow[i+1]);
  }
  setTimeout(function(){dot.setAttribute('opacity','0');}, 350);
}

async function fire(btn){
  const id=btn.dataset.id;
  btn.disabled=true; btn.textContent='执行中…';
  const action=ACTIONS.find(a=>a.id===id);
  if(action) animateFlow(action);
  try{ await fetch('/api/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}); }catch(e){}
  toast('已触发，处理中…');
  setTimeout(()=>{btn.disabled=false;btn.textContent='触发';loadEvents(true);},2200);
}

let lastSig='';
async function loadEvents(){
  try{
    const d=await getJSON('/api/events');
    const evs=d.events||[];
    const newest=evs.length?Math.max(...evs.map(e=>e.ts||0)):0;
    const sig=(d.total||0)+'-'+newest;
    if(sig!==lastSig){
      const feed=$('feed');
      if(!evs.length){feed.innerHTML='<div class="empty">暂无事件 — 点击左侧动作触发</div>';}
      else{feed.innerHTML=evs.map(e=>'<div class="ev"><div><div class="nm">'+(e.name||'事件')+'</div><div class="cl">'+(e.detail||'')+(e.time?' · '+e.time:'')+'</div></div><span class="sev '+(e.severity||'Low')+'">'+(e.severity||'Low')+'</span></div>').join('');}
      lastSig=sig;
    }
  }catch(e){}
}

loadStatus();loadActions();loadEvents();
setInterval(loadStatus,10000);
setInterval(loadEvents,5000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(f"Demo GUI: {MANIFEST['title']}  ->  http://127.0.0.1:{ARGS.port}", flush=True)
    app.run(host="127.0.0.1", port=ARGS.port, debug=False, threaded=True)
