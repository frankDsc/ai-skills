"""Exact geometry with the architecture Skill's official icon assets."""
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'skills/huawei-cloud-bestpractice-demo'))
from lib.arch import _icon_group

MANIFEST = json.loads((Path(__file__).parent/'manifest.json').read_text(encoding='utf-8'))
NODES, EDGES = MANIFEST['nodes'], MANIFEST['edges']


def build():
    icons = ROOT/'skills/huawei-cloud-bestpractice-demo/assets/icons'
    out=['<svg id="arch" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 580" role="img" aria-label="HSS 最佳实践架构：演练主机与防护中心分离，业务流与管理流分层">',
         '<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#c7000b"/></marker><marker id="ag" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#9b9eaa"/></marker></defs>',
         '<defs><marker id="ad" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#177c57"/></marker></defs>',
         '<rect width="1240" height="580" fill="white"/>',
         '<rect x="485" y="170" width="270" height="225" rx="14" fill="#fff8f8" stroke="#edbbc0" stroke-dasharray="5 5"/>',
         '<text x="505" y="194" font-size="14" fill="#9a333c">独立 VPC / 子网</text>',
         '<rect x="520" y="210" width="220" height="145" rx="10" fill="none" stroke="#c7000b"/>',
         '<text x="535" y="378" font-size="12" fill="#9a333c">HSS 主机侧防护范围</text>']
    for edge in EDGES:
        d='M '+' L '.join(f'{x} {y}' for x,y in edge['points'])
        ctrl=edge.get('control')
        out.append(f'<path id="edge-{edge["id"]}" d="{d}" fill="none" stroke="{"#9b9eaa" if ctrl else "#c7000b"}" stroke-width="2" '+('stroke-dasharray="5 5" ' if ctrl else '')+f'marker-end="url(#{"ag" if ctrl else "ar"})"/>')
    for node in NODES:
        n=node;x,y,w,h=(n[k] for k in ('x','y','w','h'))
        out.append(f'<g id="node-{n["id"]}" class="node"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="white" stroke="#e4dadd"/>')
        icon=_icon_group(str(icons),n['icon'],x+14,y+16,30).replace('ic-'+n['icon'],'ic-'+n['id'])
        out.append(icon)
        out.append(f'<text x="{x+14}" y="{y+66}" fill="#23232d" font-size="16" font-weight="600">{escape(n["label"])}</text><text x="{x+14}" y="{y+86}" fill="#81818f" font-size="12">{escape(n["sub"])}</text></g>')
    out.append('<text x="40" y="555" font-size="12" fill="#888896">红色：演练指令路径　绿色动画：已查询到真实告警　CTS 为可选审计目标</text><circle id="flow-halo" r="13" fill="#c7000b" opacity=".15" visibility="hidden"/><circle id="flow-dot" r="6" fill="#c7000b" visibility="hidden"/></svg>')
    return '\n'.join(out)


if __name__=='__main__':
    here=Path(__file__).resolve().parent
    (here/'architecture.svg').write_text(build(),encoding='utf-8')
    (here/'geometry.json').write_text(json.dumps({'nodes':NODES,'edges':EDGES},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Architecture SVG and geometry generated')
