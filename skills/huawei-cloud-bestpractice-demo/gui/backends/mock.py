#!/usr/bin/env python3
"""Mock 后端：任意领域都能演示「触发动作 → 产生事件」，无需真实云资源。"""
import time


class MockBackend:
    def __init__(self, manifest):
        self.manifest = manifest
        self._events = []

    def status(self):
        return {"cards": self.manifest.get("cards", [])}

    def execute(self, action):
        ev = action.get("event", {})
        self._events.insert(0, {
            "name": ev.get("name", action["label"]),
            "detail": ev.get("detail", ""),
            "severity": ev.get("severity", "Success"),
            "time": time.strftime("%H:%M:%S"),
            "ts": int(time.time() * 1000),
        })
        return {"ok": True, "output": ev.get("detail", "")}

    def events(self):
        return {"total": len(self._events), "events": self._events}
