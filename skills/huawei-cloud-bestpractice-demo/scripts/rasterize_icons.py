#!/usr/bin/env python3
"""把 assets/icons/*.svg 栅格化为 assets/icons_png/*.png（144x144）。

用无头 Chrome 渲染，PNG data URI 在所有浏览器/WebView 中都能稳定显示。
"""
import base64
import glob
import os
import subprocess

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(SKILL_ROOT, "assets", "icons")
DST = os.path.join(SKILL_ROOT, "assets", "icons_png")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SIZE = 144

os.makedirs(DST, exist_ok=True)
svg_files = sorted(glob.glob(os.path.join(SRC, "*.svg")))
print(f"rasterizing {len(svg_files)} icons -> {DST}")
for f in svg_files:
    name = os.path.splitext(os.path.basename(f))[0]
    b64 = base64.b64encode(open(f, "rb").read()).decode()
    html = (f'<!DOCTYPE html><html><body style="margin:0;padding:0;background:#fff">'
            f'<img src="data:image/svg+xml;base64,{b64}" width="{SIZE}" height="{SIZE}" '
            f'style="display:block"></body></html>')
    tmp = f"/tmp/_icon_{name}.html"
    open(tmp, "w").write(html)
    out = os.path.join(DST, name + ".png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                    f"--user-data-dir=/tmp/chrome-icon-{name}",
                    f"--screenshot={out}", f"--window-size={SIZE},{SIZE}",
                    f"file://{tmp}"], capture_output=True)
    print("  ", name, "->", os.path.basename(out), os.path.getsize(out) if os.path.exists(out) else "FAIL")
print("done")
