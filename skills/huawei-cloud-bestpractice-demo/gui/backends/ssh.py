#!/usr/bin/env python3
"""通用 SSH 后端：在真实 ECS 上执行 manifest 里 action.cmd，返回真实输出。"""
import json
import os
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config, ssh_exec


class SshBackend:
    def __init__(self, manifest):
        self.manifest = manifest
        self.cfg = load_config()
        state_path = os.path.join(SKILL_ROOT, "state.json")
        self.state = json.load(open(state_path, encoding="utf-8"))
        self.password = open(os.path.join(SKILL_ROOT, "demo_password.txt")).read().strip()
        self.log = []

    def status(self):
        return {"cards": self.manifest.get("cards", [])}

    def execute(self, action):
        cmd = action.get("cmd")
        if not cmd:
            return {"ok": False, "error": f"动作 {action['id']} 缺少 cmd（所有 Demo 必须连真实虚拟机）"}
        try:
            out = ssh_exec(self.state["public_ip"], self.password, cmd, timeout=120)
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}
        ev = action.get("event", {})
        self.log.insert(0, {
            "name": ev.get("name", action["label"]),
            "detail": out[:400] or "（无输出）",
            "severity": ev.get("severity", "Success"),
            "time": time.strftime("%H:%M:%S"),
            "ts": int(time.time() * 1000),
        })
        return {"ok": True, "output": out}

    def events(self):
        return {"total": len(self.log), "events": self.log}
