#!/usr/bin/env python3
"""通用架构图生成器：从 manifest 生成带华为云官方图标的 SVG。

布局：节点用 (col,row) 网格定位；连线走正交路径；每个 action 生成一条隐藏的 flow 路径，
供前端动画使用。
"""
import base64
import os

NODE_W = 190
NODE_H = 150


def _data_uri(icons_dir, icon):
    if not icon:
        return ""
    # 优先用 PNG（PNG data URI 在所有浏览器/WebView 都能渲染），回退 SVG
    png = os.path.join(os.path.dirname(icons_dir), "icons_png", icon + ".png")
    if os.path.exists(png):
        with open(png, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    p = os.path.join(icons_dir, icon + ".svg")
    if not os.path.exists(p):
        return ""
    with open(p, "rb") as f:
        return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()


def _positions(nodes):
    gapx, gapy = 70, 60
    mx, my = 60, 50
    pos = {}
    for n in nodes:
        pos[n["id"]] = {
            "x": mx + n["col"] * (NODE_W + gapx),
            "y": my + n["row"] * (NODE_H + gapy),
            "n": n,
        }
    return pos


def _route(s, t):
    """从 s 右边缘到 t 左边缘的正交路径点。"""
    sx, sy = s["x"] + NODE_W, s["y"] + NODE_H / 2
    tx, ty = t["x"], t["y"] + NODE_H / 2
    if abs(sy - ty) < 4:
        return [(sx, sy), (tx, ty)]
    mid = (sx + tx) / 2
    return [(sx, sy), (mid, sy), (mid, ty), (tx, ty)]


def _d(points):
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)


def build_svg(manifest, icons_dir):
    nodes = manifest["nodes"]
    pos = _positions(nodes)
    maxx = max(p["x"] for p in pos.values()) + NODE_W + 60
    maxy = max(p["y"] for p in pos.values()) + NODE_H + 60
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

    # 连线（在节点之下）
    for e in manifest.get("edges", []):
        s, t = pos.get(e["from"]), pos.get(e["to"])
        if not s or not t:
            continue
        control = e.get("flow") == "control"
        stroke = "#9aa0a6" if control else "#C7000B"
        dash = "5 4" if control else "7 5"
        marker = "arrowGray" if control else "arrowRed"
        opacity = "0.55" if control else "0.9"
        o.append(f'<path id="edge-{e["from"]}-{e["to"]}" d="{_d(_route(s, t))}" fill="none" '
                 f'stroke="{stroke}" stroke-width="2.4" stroke-dasharray="{dash}" '
                 f'marker-end="url(#{marker})" opacity="{opacity}"/>')

    # 节点
    for n in nodes:
        p = pos[n["id"]]
        uri = _data_uri(icons_dir, n["icon"])
        x, y = p["x"], p["y"]
        o.append(f'<g id="node-{n["id"]}" class="node">')
        o.append(f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="12" '
                 f'fill="#ffffff" stroke="#C7000B" stroke-width="1.6"/>')
        if uri:
            o.append(f'<image xlink:href="{uri}" href="{uri}" x="{x + (NODE_W - 64) / 2}" '
                     f'y="{y + 14}" width="64" height="64"/>')
        o.append(f'<text x="{x + NODE_W / 2}" y="{y + 104}" text-anchor="middle" '
                 f'font-size="14" font-weight="600" fill="#333333">{n["label"]}</text>')
        if n.get("sub"):
            o.append(f'<text x="{x + NODE_W / 2}" y="{y + 126}" text-anchor="middle" '
                     f'font-size="11" fill="#888888">{n["sub"]}</text>')
        o.append('</g>')

    # 每个 action 一条隐藏 flow 路径
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
