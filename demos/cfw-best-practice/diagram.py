"""Render semantic inventory separately; embedded official color icons work offline."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
MODEL = json.loads((HERE / 'manifest.json').read_text())
ICONS = json.loads((HERE / 'icons.json').read_text())


def build():
    out = ['<svg id="arch" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 500" role="img" aria-label="演练架构：受控探测 ECS 经公网 EIP，通过 CFW 互联网边界防护访问合成订单 ECS；IAM 管理与原生日志独立显示">',
           '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0 0 L8 4 L0 8" fill="#c7000b"/></marker><marker id="control" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#9195a3"/></marker></defs>',
           '<rect width="1240" height="500" fill="white"/>',
           '<text x="40" y="34" font-size="14" fill="#a45322">演练架构 · 仅合成订单 · CFW 为托管透明防护，不部署在 ECS 内</text>']
    for x in (40, 472, 904):
        out.append(f'<rect x="{x}" y="208" width="304" height="224" rx="14" fill="#fafbfc" stroke="#d8dce4" stroke-dasharray="5 5"/>')
    for e in MODEL['edges']:
        control = e.get('control', False)
        path = 'M ' + ' L '.join(f'{x} {y}' for x, y in e['points'])
        extra = ' stroke-dasharray="5 5"' if control else ''
        out.append(f'<path id="edge-{e["id"]}" d="{path}" fill="none" stroke="{"#9195a3" if control else "#c7000b"}" stroke-width="2"{extra} marker-end="url(#{"control" if control else "arrow"})"/>')
    for n in MODEL['nodes']:
        x, y, w, h = (n[k] for k in ('x', 'y', 'w', 'h'))
        out.append(f'<g id="node-{n["id"]}" class="node"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="white" stroke="#e0e2e8"/>')
        if n.get('icon'):
            out.append(f'<image href="{ICONS[n["icon"]]}" x="{x+16}" y="{y+14}" width="32" height="32"/>')
        else:
            out.append(f'<text x="{x+16}" y="{y+39}" font-size="25" fill="#717887">≡</text>')
        out.append(f'<text x="{x+16}" y="{y+69}" font-size="16" font-weight="600" fill="#242630">{escape(n["label"])}</text><text x="{x+16}" y="{y+92}" font-size="13" fill="#777d8b">{escape(n["sub"])}</text></g>')
    for label in MODEL['labels']:
        out.append(f'<text x="{label["x"]}" y="{label["y"]+16}" font-size="14" fill="#777d8b">{escape(label["text"])}</text>')
    out.append('<text x="40" y="474" font-size="13" fill="#858996">入站向右、出站反向；管理为证书固定 TLS/443 内真实 SSH（操作端 /32）。原生日志不另购 LTS。</text><circle id="flow-dot" r="7" fill="#c7000b" visibility="hidden"/></svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    (HERE / 'architecture.svg').write_text(build())
    (HERE / 'geometry.json').write_text(json.dumps({'nodes': MODEL['nodes'] + MODEL['labels'], 'edges': MODEL['edges']}, ensure_ascii=False, indent=2))
