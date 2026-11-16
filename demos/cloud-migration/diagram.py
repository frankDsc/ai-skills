"""Reuse official inline SVG icons and retain validated geometry."""
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'skills/huawei-cloud-bestpractice-demo'))
from lib.arch import _icon_group

NODES = [
    dict(id='source',x=60,y=180,w=260,h=120,icon='ecs',label='模拟源端',sub='应用配置 · SQLite 订单 · 合成附件'),
    dict(id='transfer',x=490,y=180,w=260,h=120,icon='ecs',label='搬迁执行引擎',sub='全量复制 / 差异补迁 / 全内容校验'),
    dict(id='target',x=920,y=180,w=260,h=120,icon='ecs',label='隔离目标端',sub='目标目录 · 只读观察 · 逻辑割接'),
    dict(id='control',x=490,y=40,w=260,h=90,icon='iam',label='流程门禁',sub='冻结写入 · 校验通过 · 固定动作'),
    dict(id='audit',x=490,y=350,w=260,h=80,icon='lts',label='本实验事件日志',sub='实际输出 · 执行耗时 · 校验摘要'),
]
EDGES = [dict(id='source-transfer',points=[[320,240],[490,240]]),
         dict(id='transfer-target',points=[[750,240],[920,240]]),
         dict(id='control-transfer',points=[[620,130],[620,180]],control=True),
         dict(id='transfer-audit',points=[[620,300],[620,350]],control=True)]


def build():
    icons=ROOT/'skills/huawei-cloud-bestpractice-demo/assets/icons'
    out=['<svg id="arch" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 470" role="img" aria-label="合成数据从模拟源端经搬迁引擎复制到隔离目标端，流程门禁和事件日志独立展示">',
         '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="#c7000b"/></marker><marker id="gray" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="#a4a6b0"/></marker></defs>',
         '<rect x="35" y="155" width="1170" height="170" rx="14" stroke="#e4e5ec" fill="#fafbfc" stroke-dasharray="6 5"/>',
         '<text x="60" y="142" font-size="12" fill="#737784">执行边界：当前后端内的逻辑隔离目录；源端与目标端不是两台独立云主机</text>']
    for edge in EDGES:
        d='M '+' L '.join(f'{x} {y}' for x,y in edge['points'])
        ctrl=edge.get('control',False)
        out.append(f'<path id="edge-{edge["id"]}" d="{d}" fill="none" stroke="{"#a4a6b0" if ctrl else "#c7000b"}" stroke-width="2" marker-end="url(#{"gray" if ctrl else "arrow"})" '+('stroke-dasharray="5 5"' if ctrl else '')+'/>')
    for n in NODES:
        x,y,w,h=(n[k] for k in ('x','y','w','h'))
        out.append(f'<g id="node-{n["id"]}" class="node"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="white" stroke="#dedfe7"/>')
        out.append(_icon_group(str(icons),n['icon'],x+18,y+16,28).replace('ic-'+n['icon'],'ic-'+n['id']))
        out.append(f'<text x="{x+60}" y="{y+36}" font-size="17" fill="#252934" font-weight="600">{escape(n["label"])}</text><text x="{x+18}" y="{y+66}" font-size="12" fill="#777d8b">{escape(n["sub"])}</text></g>')
    out += ['<text x="350" y="223" font-size="12" fill="#a13e47">读取 / 复制</text><text x="780" y="223" font-size="12" fill="#a13e47">校验 / 写入</text>',
            '<text x="60" y="455" font-size="11" fill="#8d929d">华为云官方图标 v3.2；图标表示角色映射，IAM / LTS 等托管服务未在本实验开通。</text>',
            '<circle id="flow-dot" r="6" fill="#c7000b" visibility="hidden"/></svg>']
    return '\n'.join(out)


def build_sms():
    icons=ROOT/'skills/huawei-cloud-bestpractice-demo/assets/icons'
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 280" role="img" aria-label="同一 VPC 中的两台独立 ECS，源端 Agent 经私网直传到目标端；SMS 是迁移控制面">',
         '<defs><marker id="sms-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="#c7000b"/></marker></defs>',
         '<rect x="25" y="105" width="950" height="160" rx="12" fill="#fafbfc" stroke="#e4e5ec"/>',
         '<text x="45" y="255" font-size="11" fill="#89909c">专用 VPC · 北京四 · 私网直传 · 目标机无公网 IP</text>',
         '<path d="M205 130V110H450V90 M570 90V110H800V130" fill="none" stroke="#aaa" stroke-width="1.5" stroke-dasharray="5 4"/>',
         '<path d="M340 185H660" fill="none" stroke="#c7000b" stroke-width="2" marker-end="url(#sms-arrow)"/>',
         '<text x="400" y="170" font-size="12" fill="#9c4850">系统 / 应用 / 文件</text>',
         '<text x="415" y="208" font-size="11" fill="#9298a2">加密迁移数据流</text>']
    for x,y,w,h,icon,label,sub in [(400,10,220,80,'sms','SMS 迁移控制面','注册 · 编排 · 任务遥测'),
            (70,130,270,105,'ecs','源 ECS + SMS Agent','Ubuntu · 订单服务 · 合成数据'),
            (660,130,270,105,'ecs','独立目标 ECS','系统迁移 · 启动服务 · 数据验收')]:
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="white" stroke="#dedfe7"/>')
        if (icons/(icon+'.svg')).exists():
            svg.append(_icon_group(str(icons),icon,x+15,y+15,26).replace('ic-'+icon,'sms-icon-'+str(x)))
        else:
            svg.append(f'<text x="{x+15}" y="{y+32}" font-size="10" fill="#c7000b" font-weight="700">SMS</text>')
        svg.append(f'<text x="{x+50}" y="{y+33}" font-size="15" font-weight="600" fill="#252934">{label}</text><text x="{x+15}" y="{y+62}" font-size="11" fill="#8a909b">{sub}</text>')
    svg.append('<circle id="sms-flow" r="4" fill="#c7000b" style="display:none"><animateMotion dur="1.2s" repeatCount="indefinite" path="M340 185H650"/></circle></svg>')
    return ''.join(svg)


if __name__=='__main__':
    here=Path(__file__).parent
    (here/'static/architecture.svg').write_text(build())
    (here/'geometry.json').write_text(json.dumps({'nodes':NODES,'edges':EDGES},indent=2))
