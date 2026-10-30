#!/usr/bin/env python3
"""通用架构图生成器：从 manifest 生成带华为云官方图标的 SVG。

支持：
- 普通节点（图标 + 标题 + 副标题）
- 分组节点（type=group，一个大框包住 children，用于 HSS 这类「防护边界包住 VM」）
- 连线（实线红=业务/攻击流，虚线灰=控制/审计流）+ 连线标签
- 每个 action 生成隐藏的 flow 路径，供前端动画
"""
import base64
import os

NODE_W = 190
NODE_H = 150
GAPX = 70
GAPY = 60
GRID_W = NODE_W + GAPX
GRID_H = NODE_H + GAPY
MX = 60
MY = 50
GROUP_TITLE_H = 46


def _data_uri(icons_dir, icon):
    p = os.path.join(icons_dir, icon + ".svg")
    if not icon or not os.path.exists(p):
        return ""
    with open(p, "rb") as f:
        return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()


def _layout(nodes):
    groups = [n for n in nodes if n.get("type") == "group"]
    child_of = {}
    for g in groups:
        for cid in g.get("children", []):
            child_of[cid] = g["id"]
    pos = {}
    for n in nodes:
        if n.get("type") == "group" or n["id"] in child_of:
            continue
        pos[n["id"]] = {"x": MX + n["col"] * GRID_W, "y": MY + n["row"] * GRID_H,
                        "w": NODE_W, "h": NODE_H}
    for g in groups:
        x = MX + g["col"] * GRID_W
        y = MY + g["row"] * GRID_H
        w = g.get("w", 2) * GRID_W - GAPX
        h = NODE_H + 60
        pos[g["id"]] = {"x": x, "y": y, "w": w, "h": h}
        kids = g.get("children", [])
        if kids:
            total = len(kids) * NODE_W + (len(kids) - 1) * 20
            sx = x + (w - total) / 2
            for i, cid in enumerate(kids):
                pos[cid] = {"x": sx + i * (NODE_W + 20), "y": y + GROUP_TITLE_H + 6,
                            "w": NODE_W, "h": NODE_H}
    return pos


def _route(s, t, direction=None):
    """正交路由。默认从 s 右边缘到 t 左边缘；direction=up/down 走垂直。"""
    sx = s["x"] + s.get("w", NODE_W)
    sy = s["y"] + s.get("h", NODE_H) / 2
    tx = t["x"]
    ty = t["y"] + t.get("h", NODE_H) / 2
    if direction == "up":
        scx = s["x"] + s.get("w", NODE_W) / 2
        tcx = t["x"] + t.get("w", NODE_W) / 2
        stop = s["y"]
        tbot = t["y"] + t.get("h", NODE_H)
        if abs(scx - tcx) < 4:
            return [(scx, stop), (tcx, tbot)]
        midy = (stop + tbot) / 2
        return [(scx, stop), (scx, midy), (tcx, midy), (tcx, tbot)]
    if direction == "down":
        scx = s["x"] + s.get("w", NODE_W) / 2
        tcx = t["x"] + t.get("w", NODE_W) / 2
        sbot = s["y"] + s.get("h", NODE_H)
        ttop = t["y"]
        if abs(scx - tcx) < 4:
            return [(scx, sbot), (tcx, ttop)]
        midy = (sbot + ttop) / 2
        return [(scx, sbot), (scx, midy), (tcx, midy), (tcx, ttop)]
    if abs(sy - ty) < 4:
        return [(sx, sy), (tx, ty)]
    mid = (sx + tx) / 2
    return [(sx, sy), (mid, sy), (mid, ty), (tx, ty)]


def _d(points):
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)


def _midpoint(points):
    segs = []
    total = 0
    for i in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        segs.append((L, x1, y1, x2, y2))
        total += L
    half = total / 2
    for L, x1, y1, x2, y2 in segs:
        if half <= L:
            r = half / L if L else 0
            return (x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
        half -= L
    return points[-1]


def build_svg(manifest, icons_dir):
    nodes = manifest["nodes"]
    pos = _layout(nodes)
    maxx = max(p["x"] + p.get("w", NODE_W) for p in pos.values()) + 60
    maxy = max(p["y"] + p.get("h", NODE_H) for p in pos.values()) + 60
    W = max(int(maxx), 1100)
    H = max(int(maxy), 640)

    o = []
    o.append(f'<svg viewBox="0 0 {W} {H}" id="arch" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">')
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

    # 1) 分组框（最底层）
    for n in nodes:
        if n.get("type") != "group":
            continue
        p = pos[n["id"]]
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        o.append(f'<g id="group-{n["id"]}">')
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
                 f'fill="#FDECEC" stroke="#C7000B" stroke-width="2"/>')
        o.append(f'<text x="{x + 16}" y="{y + 24}" font-size="13" font-weight="700" '
                 f'fill="#9E0008">{n["label"]}</text>')
        if n.get("sub"):
            o.append(f'<text x="{x + 16}" y="{y + 40}" font-size="11" '
                     f'fill="#B85C5C">{n["sub"]}</text>')
        o.append('</g>')

    # 2) 连线 + 标签
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
        if e.get("label"):
            mx, my = _midpoint(pts)
            color = "#C7000B" if not control else "#777777"
            o.append(f'<rect x="{mx - 44}" y="{my - 12}" width="88" height="20" rx="5" '
                     f'fill="#ffffff" stroke="{color}" stroke-width="1"/>')
            o.append(f'<text x="{mx}" y="{my + 3}" text-anchor="middle" font-size="11" '
                     f'font-weight="600" fill="{color}">{e["label"]}</text>')

    # 3) 节点（图标 + 文字）
    for n in nodes:
        if n.get("type") == "group":
            continue
        p = pos[n["id"]]
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        uri = _data_uri(icons_dir, n.get("icon"))
        o.append(f'<g id="node-{n["id"]}" class="node">')
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
                 f'fill="#ffffff" stroke="#C7000B" stroke-width="1.6"/>')
        if uri:
            o.append(f'<image xlink:href="{uri}" href="{uri}" x="{x + (w - 64) / 2}" y="{y + 14}" width="64" height="64"/>')
        o.append(f'<text x="{x + w / 2}" y="{y + 104}" text-anchor="middle" font-size="14" '
                 f'font-weight="600" fill="#333333">{n["label"]}</text>')
        if n.get("sub"):
            o.append(f'<text x="{x + w / 2}" y="{y + 126}" text-anchor="middle" font-size="11" '
                     f'fill="#888888">{n["sub"]}</text>')
        o.append('</g>')

    # 4) 每个 action 一条隐藏 flow 路径
    for a in manifest.get("actions", []):
        pts = []
        flow = a.get("flow", [])
        for i in range(len(flow) - 1):
            s, t = pos.get(flow[i]), pos.get(flow[i + 1])
            if not s or not t:
                continue
            seg = _route(s, t)
            pts.extend(seg if i == 0 else seg[1:])
        if pts:
            o.append(f'<path id="flow-{a["id"]}" d="{_d(pts)}" fill="none" stroke="none"/>')

    o.append('<circle id="flowDot" cx="0" cy="0" r="8" fill="#C7000B" opacity="0"/>')
    o.append('</svg>')
    return "\n".join(o)
