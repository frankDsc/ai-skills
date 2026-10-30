#!/usr/bin/env python3
"""通用架构图生成器（按 architecture-diagram-tool 布局规则）。

- 图标：**内联 SVG 路径**（不用 <image>，避免 WebView 兼容问题）
- 嵌套分组：VPC > HSS > ECS
- 正交连线：实线红=业务/攻击，虚线灰=控制/审计；dir=up/down
"""
import os
import re

NODE_W = 190
NODE_H = 150
GAPX = 70
GAPY = 60
GRID_W = NODE_W + GAPX
GRID_H = NODE_H + GAPY
MX = 56
MY = 44
GROUP_TITLE_H = 46


def _icon_group(icons_dir, icon, x, y, size):
    """把一个 SVG 图标内联为 <g>（重命名 clipPath id 防冲突），按 size 缩放。"""
    if not icon:
        return ""
    p = os.path.join(icons_dir, icon + ".svg")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as source:
        raw = source.read()
    m = re.search(r"<svg[^>]*>(.*)</svg>", raw, re.S)
    inner = m.group(1) if m else ""
    uid = "ic-" + re.sub(r"[^A-Za-z0-9_-]", "_", icon)
    inner = inner.replace('id="a"', f'id="{uid}"').replace("url(#a)", f"url(#{uid})")
    scale = size / 72.0
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({scale:.5f})">{inner}</g>'


def _layout(nodes):
    by_id = {n["id"]: n for n in nodes}
    child_of = {}
    for n in nodes:
        if n.get("type") == "group":
            for c in n.get("children", []):
                child_of[c] = n["id"]
    pos = {}
    for n in nodes:
        if n["id"] in child_of:
            continue
        x = MX + n.get("col", 0) * GRID_W
        y = MY + n.get("row", 0) * GRID_H
        _place(n, x, y, None, None, by_id, pos)
    return pos


def _place(n, x, y, w, h, by_id, pos):
    if n.get("type") == "group":
        if w is None:
            gw = n.get("w", 2) * GRID_W - GAPX
            gh = n.get("h", 1) * GRID_H - GAPY
            gx, gy = x, y
        else:
            gw = n.get("w_px") or w
            gh = n.get("h_px") or h
            gx = x + (w - gw) / 2
            gy = y + (h - gh) / 2
        pos[n["id"]] = {"x": gx, "y": gy, "w": gw, "h": gh}
        kids = [by_id[c] for c in n.get("children", [])]
        if kids:
            ix, iy = gx + 14, gy + GROUP_TITLE_H
            iw, ih = gw - 28, gh - GROUP_TITLE_H - 12
            gap = 16
            cw = (iw - gap * (len(kids) - 1)) / len(kids)
            for i, k in enumerate(kids):
                _place(k, ix + i * (cw + gap), iy, cw, ih, by_id, pos)
    else:
        nw = min(w, NODE_W) if w else NODE_W
        nh = min(h, NODE_H) if h else NODE_H
        px = x + (w - nw) / 2 if w else x
        py = y + (h - nh) / 2 if h else y
        pos[n["id"]] = {"x": px, "y": py, "w": nw, "h": nh}


def _route(s, t, direction=None):
    if direction == "up":
        scx, tcx = s["x"] + s["w"] / 2, t["x"] + t["w"] / 2
        stop, tbot = s["y"], t["y"] + t["h"]
        if abs(scx - tcx) < 4:
            return [(scx, stop), (tcx, tbot)]
        midy = (stop + tbot) / 2
        return [(scx, stop), (scx, midy), (tcx, midy), (tcx, tbot)]
    if direction == "down":
        scx, tcx = s["x"] + s["w"] / 2, t["x"] + t["w"] / 2
        sbot, ttop = s["y"] + s["h"], t["y"]
        if abs(scx - tcx) < 4:
            return [(scx, sbot), (tcx, ttop)]
        midy = (sbot + ttop) / 2
        return [(scx, sbot), (scx, midy), (tcx, midy), (tcx, ttop)]
    sx, sy = s["x"] + s["w"], s["y"] + s["h"] / 2
    tx, ty = t["x"], t["y"] + t["h"] / 2
    if abs(sy - ty) < 4:
        return [(sx, sy), (tx, ty)]
    mid = (sx + tx) / 2
    return [(sx, sy), (mid, sy), (mid, ty), (tx, ty)]


def _d(points):
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)


def build_svg(manifest, icons_dir):
    nodes = manifest["nodes"]
    pos = _layout(nodes)
    maxx = max(p["x"] + p["w"] for p in pos.values()) + 60
    maxy = max(p["y"] + p["h"] for p in pos.values()) + 60
    W = max(int(maxx), 1120)
    H = max(int(maxy), 640)

    o = ['<svg viewBox="0 0 %d %d" id="arch" xmlns="http://www.w3.org/2000/svg">' % (W, H)]
    o.append('''<defs>
      <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
        <path d="M 26 0 L 0 0 0 26" fill="none" stroke="#f6e2e2" stroke-width="1"/>
      </pattern>
      <marker id="arrowRed" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
        <path d="M0,0 L0,6 L9,3 z" fill="#C7000B"/>
      </marker>
      <marker id="arrowGray" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#9aa0a6"/>
      </marker>
    </defs>''')
    o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    o.append(f'<rect width="{W}" height="{H}" fill="url(#grid)" opacity="0.55"/>')

    # 1) 分组框（外层先画）
    groups = [n for n in nodes if n.get("type") == "group"]
    groups.sort(key=lambda n: pos[n["id"]]["w"] * pos[n["id"]]["h"], reverse=True)
    for n in groups:
        p = pos[n["id"]]
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        o.append(f'<g id="group-{n["id"]}">')
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
                 f'fill="#FDECEC" stroke="#C7000B" stroke-width="2"/>')
        icx = x + 16
        o.append(_icon_group(icons_dir, n.get("icon"), icx, y + 10, 22))
        if n.get("icon"):
            icx += 28
        o.append(f'<text x="{icx}" y="{y + 26}" font-size="13" font-weight="700" '
                 f'fill="#9E0008">{n["label"]}</text>')
        if n.get("sub"):
            o.append(f'<text x="{x + 16}" y="{y + 41}" font-size="11" fill="#B85C5C">{n["sub"]}</text>')
        o.append('</g>')

    # 2) 连线
    for e in manifest.get("edges", []):
        s, t = pos.get(e["from"]), pos.get(e["to"])
        if not s or not t:
            continue
        control = e.get("flow") == "control"
        stroke = "#9aa0a6" if control else "#C7000B"
        dash = "5 4" if control else "7 5"
        marker = "arrowGray" if control else "arrowRed"
        opacity = "0.6" if control else "0.9"
        pts = _route(s, t, e.get("dir"))
        o.append(f'<path id="edge-{e["from"]}-{e["to"]}" d="{_d(pts)}" fill="none" '
                 f'stroke="{stroke}" stroke-width="2.4" stroke-dasharray="{dash}" '
                 f'marker-end="url(#{marker})" opacity="{opacity}"/>')

    # 3) 节点（图标内联）
    for n in nodes:
        if n.get("type") == "group":
            continue
        p = pos[n["id"]]
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        o.append(f'<g id="node-{n["id"]}" class="node">')
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
                 f'fill="#ffffff" stroke="#C7000B" stroke-width="1.6"/>')
        o.append(_icon_group(icons_dir, n.get("icon"), x + (w - 64) / 2, y + 14, 64))
        o.append(f'<text x="{x + w / 2}" y="{y + 104}" text-anchor="middle" font-size="14" '
                 f'font-weight="600" fill="#333333">{n["label"]}</text>')
        if n.get("sub"):
            o.append(f'<text x="{x + w / 2}" y="{y + 126}" text-anchor="middle" font-size="11" '
                     f'fill="#888888">{n["sub"]}</text>')
        o.append('</g>')

    # 4) action flow 分段路径（每段独立，前端逐段动画，红点到达节点才震动）
    for a in manifest.get("actions", []):
        flow = a.get("flow", [])
        for i in range(len(flow) - 1):
            s, t = pos.get(flow[i]), pos.get(flow[i + 1])
            if not s or not t:
                continue
            seg = _route(s, t)
            o.append(f'<path id="flow-{a["id"]}-{i}" d="{_d(seg)}" fill="none" stroke="none"/>')

    o.append('<circle id="flowDot" cx="0" cy="0" r="8" fill="#C7000B" opacity="0"/>')
    o.append('</svg>')
    return "\n".join(o)
