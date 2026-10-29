#!/usr/bin/env python3
"""Demo 清单（manifest）加载与校验。

manifest 是「一个最佳实践 Demo」的声明式描述：
- 卡片、架构图节点/连线、可触发的动作、事件流。
- 架构图与 GUI 都从这个 manifest 渲染，因此新增一个领域只需写一个 manifest。
"""
import json
import os

REQUIRED = ["id", "title", "nodes", "actions"]


def load(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)
    return validate(m)


def validate(m):
    for k in REQUIRED:
        if k not in m:
            raise ValueError(f"manifest 缺少字段: {k}")
    ids = {n["id"] for n in m["nodes"]}
    for n in m["nodes"]:
        for k in ("id", "label", "icon"):
            if k not in n:
                raise ValueError(f"node 缺少字段 {k}: {n}")
        n.setdefault("col", 0)
        n.setdefault("row", 0)
        n.setdefault("sub", "")
    for e in m.get("edges", []):
        if e["from"] not in ids or e["to"] not in ids:
            raise ValueError(f"edge 引用了不存在的节点: {e}")
    for a in m.get("actions", []):
        for fid in a.get("flow", []):
            if fid not in ids:
                raise ValueError(f"action {a['id']} 的 flow 引用了不存在的节点: {fid}")
    m.setdefault("cards", [])
    m.setdefault("edges", [])
    m.setdefault("backend", "mock")
    m.setdefault("region", "cn-north-4")
    return m


def list_examples(skill_root):
    ex = os.path.join(skill_root, "examples")
    if not os.path.isdir(ex):
        return []
    return [d for d in sorted(os.listdir(ex)) if os.path.isdir(os.path.join(ex, d))]
