#!/usr/bin/env python3
"""05 用华为云官方图标生成白底红主色架构图 SVG。"""
import base64
import os
import pathlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(BASE, "assets", "icons")
OUT = os.path.join(BASE, "assets", "arch_diagram.svg")


def du(name):
    b = pathlib.Path(os.path.join(ICON, name + ".svg")).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(b).decode()


ECS, HSS, IAM, CTS, VPC = (du(n) for n in ["ecs", "hss", "iam", "cts", "vpc"])

svg = f'''<svg viewBox="0 0 1200 700" id="arch" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
      <path d="M 26 0 L 0 0 0 26" fill="none" stroke="#f6e2e2" stroke-width="1"/>
    </pattern>
    <marker id="arrowRed" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#C7000B"/>
    </marker>
    <marker id="arrowGray" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#9aa0a6"/>
    </marker>
  </defs>
  <rect width="1200" height="700" fill="#ffffff"/>
  <rect width="1200" height="700" fill="url(#grid)" opacity="0.55"/>

  <text x="40" y="42" font-size="16" font-weight="700" fill="#9E0008">控制面（身份 / 审计）</text>
  <line x1="40" y1="52" x2="300" y2="52" stroke="#C7000B" stroke-width="2"/>

  <g id="nIam">
    <rect x="480" y="64" width="150" height="116" rx="12" fill="#FDECEC" stroke="#C7000B" stroke-width="1.5"/>
    <image href="{IAM}" x="524" y="74" width="62" height="62"/>
    <text x="555" y="160" text-anchor="middle" font-size="13" font-weight="600" fill="#333333">IAM 身份认证</text>
    <text x="555" y="176" text-anchor="middle" font-size="11" fill="#999999">最小权限 · MFA</text>
  </g>
  <g id="nCts">
    <rect x="680" y="64" width="150" height="116" rx="12" fill="#FDECEC" stroke="#C7000B" stroke-width="1.5"/>
    <image href="{CTS}" x="724" y="74" width="62" height="62"/>
    <text x="755" y="160" text-anchor="middle" font-size="13" font-weight="600" fill="#333333">CTS 云审计</text>
    <text x="755" y="176" text-anchor="middle" font-size="11" fill="#999999">全程操作留痕</text>
  </g>
  <line x1="555" y1="180" x2="555" y2="276" stroke="#9aa0a6" stroke-width="1.7" stroke-dasharray="5 4" marker-end="url(#arrowGray)"/>
  <line x1="755" y1="180" x2="755" y2="276" stroke="#9aa0a6" stroke-width="1.7" stroke-dasharray="5 4" marker-end="url(#arrowGray)"/>

  <text x="40" y="300" font-size="16" font-weight="700" fill="#9E0008">业务 / 攻击路径</text>
  <line x1="40" y1="310" x2="300" y2="310" stroke="#C7000B" stroke-width="2"/>

  <g id="nAttacker">
    <circle cx="110" cy="440" r="52" fill="#2b2b2b"/>
    <text x="110" y="456" text-anchor="middle" font-size="34" fill="#ffffff">&#128128;</text>
    <text x="110" y="522" text-anchor="middle" font-size="13" font-weight="600" fill="#444444">攻击者</text>
  </g>
  <g id="nBoundary">
    <rect x="250" y="360" width="180" height="160" rx="12" fill="#FFF7E6" stroke="#D98200" stroke-width="1.8"/>
    <text x="340" y="390" text-anchor="middle" font-size="13" font-weight="600" fill="#8A6A00">公网 EIP + 安全组</text>
    <text x="340" y="414" text-anchor="middle" font-size="11" fill="#B58500">SSH 白名单</text>
    <text x="340" y="434" text-anchor="middle" font-size="11" fill="#B58500">最小放行</text>
    <text x="340" y="470" text-anchor="middle" font-size="11" fill="#B58500">hss-demo-sg</text>
  </g>
  <rect x="470" y="284" width="400" height="296" rx="14" fill="#F2F7FE" stroke="#2C6CB0" stroke-width="1.6" stroke-dasharray="6 4"/>
  <text x="490" y="310" font-size="12" font-weight="600" fill="#1E4F86">VPC</text>
  <image href="{VPC}" x="800" y="290" width="28" height="28" opacity="0.9"/>

  <g id="nEcs">
    <rect x="520" y="350" width="160" height="180" rx="12" fill="#ffffff" stroke="#2C6CB0" stroke-width="1.8"/>
    <image href="{ECS}" x="552" y="360" width="96" height="96"/>
    <text x="600" y="478" text-anchor="middle" font-size="13" font-weight="600" fill="#1E4F86">ECS 主机</text>
    <text x="600" y="498" text-anchor="middle" font-size="11" fill="#3A6EA5">hss-demo-ecs</text>
  </g>
  <g id="nHss">
    <rect x="900" y="350" width="190" height="180" rx="12" fill="#C7000B"/>
    <image href="{HSS}" x="958" y="360" width="74" height="74"/>
    <text x="995" y="462" text-anchor="middle" font-size="13" font-weight="700" fill="#ffffff">HSS 安全中心</text>
    <text x="995" y="482" text-anchor="middle" font-size="11" fill="#FFD9DB">企业版 · 按需</text>
  </g>

  <path id="pa1" d="M 162 440 L 250 440" stroke="#C7000B" stroke-width="2.6" stroke-dasharray="7 5" fill="none" marker-end="url(#arrowRed)"/>
  <path id="pa2" d="M 430 440 L 520 440" stroke="#C7000B" stroke-width="2.6" stroke-dasharray="7 5" fill="none" marker-end="url(#arrowRed)"/>
  <path id="pd" d="M 680 440 L 900 440" stroke="#C7000B" stroke-width="2.6" stroke-dasharray="7 5" fill="none" marker-end="url(#arrowRed)" opacity="0.3"/>

  <g transform="translate(40, 610)">
    <line x1="0" y1="0" x2="36" y2="0" stroke="#C7000B" stroke-width="2.6"/>
    <text x="44" y="4" font-size="12" fill="#666666">业务 / 攻击流（实线）</text>
    <line x1="230" y1="0" x2="266" y2="0" stroke="#9aa0a6" stroke-width="1.8" stroke-dasharray="5 4"/>
    <text x="274" y="4" font-size="12" fill="#666666">控制 / 审计流（虚线）</text>
  </g>
  <text x="40" y="660" font-size="11" fill="#999999">图标来源：华为云官方图标库 huaweicloud-latam/drawio-libraries v3.2（color 版）&#183; 安全组为通用边界</text>
</svg>
'''

pathlib.Path(OUT).write_text(svg, encoding="utf-8")
print("saved:", OUT)
