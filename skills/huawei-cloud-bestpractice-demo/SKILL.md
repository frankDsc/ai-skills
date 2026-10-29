---
name: huawei-cloud-bestpractice-demo
description: 把任意华为云「最佳实践」做成可对客户演示的 Demo。支持安全、大数据、数据库、AI、容器、网络、存储等任意领域：先按最佳实践索引选型，再生成声明式 manifest，建底层资源（VPC/ECS/EIP/OBS/RDS 等），产出华为云官方图标架构图与同款动态 GUI（动作触发 + 架构图动画 + 实时事件流）。
---

# 华为云最佳实践 Demo 生成器

> 一句话：**用户说「做 XX 最佳实践」，本 skill 让它变成「能跑、能看、能演示」的完整 Demo。**

## 能力边界

| 能力 | 说明 |
|---|---|
| 任意领域 | 安全 / 大数据 / 数据库 / AI / 容器 / 网络 / 存储 / 迁移…… |
| 底层资源 | VPC、安全组、ECS、EIP、OBS、RDS 等（按需，可释放） |
| 架构图 | 从 manifest 生成，使用**华为云官方图标**（`assets/icons/`，24 个） |
| 动态 GUI | 卡片 + 架构图 + 可触发动作 + 架构图动画 + 事件流 |
| 后端可插拔 | `mock`（任意领域，零资源即可演示）/ `hss`（真实安全检测） |

## 核心：manifest（声明式 Demo 描述）

一个 Demo = 一个 `manifest.json`。**新增任意领域，本质就是写一个新的 manifest。**

```json
{
  "id": "bigdata-demo",
  "title": "华为云大数据最佳实践 Demo",
  "subtitle": "数据接入 → 数据湖 → 数仓 → 可视化",
  "region": "cn-north-4",
  "backend": "mock",
  "cards": [{"label": "DWS", "value": "运行中", "tone": "green"}],
  "nodes": [
    {"id": "src", "label": "数据源", "sub": "RDS/文件", "icon": "rds", "col": 0, "row": 1},
    {"id": "dws", "label": "DWS", "sub": "数据仓库", "icon": "dws", "col": 3, "row": 1}
  ],
  "edges": [{"from": "src", "to": "dws", "flow": "data"}],
  "actions": [
    {"id": "run_etl", "label": "触发 ETL", "desc": "跑一遍数据流",
     "flow": ["src", "dws"],
     "event": {"name": "ETL 完成", "detail": "加载 1 万行", "severity": "Success"}}
  ]
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` / `title` | ✅ | Demo 标识 / 标题 |
| `subtitle` / `region` | | 副标题 / 区域 |
| `backend` | | `mock`（默认）或 `hss` |
| `cards` | | 顶部 4 张状态卡：`label` / `value` / `tone`(green/red) |
| `nodes` | ✅ | `id` / `label` / `sub` / `icon`(见 `assets/icons/` 文件名) / `col` / `row` |
| `edges` | | `from` / `to` / `flow`(`data` 实线红 / `control` 虚线灰) |
| `actions` | ✅ | `id` / `label` / `desc` / `flow`(节点 id 序列) / `event`(mock 用) |

> 布局用 `(col,row)` 网格，节点自动排布；连线自动正交路由。

## 工作流（Agent 执行步骤）

### 0. 环境

```bash
pip install huaweicloudsdkcore huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkeip huaweicloudsdkhss paramiko flask
cp config.example.json config.json   # 需要真实资源时才填 AK/SK
```

### 1. 选型（查索引）

读 [`references/best-practices-index.md`](references/best-practices-index.md)：按领域找到「产品组合 + 最佳实践要点 + 推荐 Demo 流程 + 图标名」。产品能力/图标可用性见 [`references/service-catalog.md`](references/service-catalog.md)。

### 2. 写 manifest

复制 `templates/manifest.example.json`，改成目标领域的节点/连线/动作。
- 纯演示（不建真实资源）：`backend: "mock"`，动作填 `event` 即可。
- 需要真实资源：继续第 3 步，并把 `backend` 指向对应实现（如 `hss`）。

### 3. 建底层资源（可选）

按 manifest 的资源需求创建：VPC/安全组 → ECS/EIP → 对应 PaaS 服务。
参考 `examples/hwcloud-hss-demo/scripts/01_setup_env.py`（安全组+ECS+EIP 的完整写法）。
产出写入 `state.json`（server_id / public_ip 等），供后端与 GUI 使用。

### 4. 生成架构图

```bash
python - <<'PY'
import sys; sys.path.insert(0, '.')
from lib import manifest, arch
m = manifest.load('examples/bigdata-demo/manifest.json')
open('examples/bigdata-demo/arch.svg','w').write(arch.build_svg(m, 'assets/icons'))
PY
```

（GUI 启动时会自动生成并内嵌，一般无需单独跑。）

### 5. 起 GUI

```bash
python gui/app.py --manifest examples/bigdata-demo/manifest.json --port 8899
# 打开 http://127.0.0.1:8899
```

### 6. 演示

- 顶部卡片显示状态；
- 中间架构图（官方图标）；
- 左侧点动作 → 架构图上有红点沿路径流动；
- 右侧事件流实时出现结果/告警。

## 目录结构

```
.
├── SKILL.md / README.md / config.example.json
├── lib/
│   ├── common.py        # 配置 + SDK 客户端
│   ├── manifest.py      # manifest 加载/校验
│   └── arch.py          # manifest → 官方图标架构图 SVG
├── gui/
│   ├── app.py           # 通用动态 GUI（读 manifest）
│   └── backends/        # mock / hss 可插拔后端
├── examples/
│   ├── bigdata-demo/    # 大数据示例（mock）
│   └── hwcloud-hss-demo/# 安全示例（hss 真实后端 + 资源脚本）
├── assets/icons/        # 24 个华为云官方图标
├── templates/manifest.example.json
└── references/          # 服务目录 / 最佳实践索引 / 踩坑 / 费用 / 图标来源
```

## 后端扩展

新增一个「真实后端」只需实现三个方法：

```python
class MyBackend:
    def status(self): ...    # 返回 {"cards": [...]}
    def execute(self, action): ...  # 执行动作
    def events(self): ...    # 返回 {"total": n, "events": [...]}
```

然后在 `gui/backends/__init__.py` 注册，manifest 里 `"backend": "mybackend"`。

## 关键坑（详见 references/gotchas.md）

1. 华为云 APIG 签名 canonical URI 要带结尾 `/`；**优先用官方 SDK**。
2. HSS Agent 安装 `os_type` 必须 `Linux`（大写），`os_arch=x86_64`。
3. HSS 按需防护用 `switch_hosts_protect_status(charging_mode="on_demand")`，版本用 `hss.version.enterprise`（专业版部分区域无效）。
4. 危险命令：`/usr/bin` 新建文件 + SUID 稳定触发；`/tmp` 不触发；同一二进制只认第一次。
5. HSS 检出延迟 30–90 秒，前端要留等待。
6. ECS 默认无公网 IP，装 Agent 前先绑 EIP。

## 安全与费用

- AK/SK、`config.json`、`state.json`、密码一律不提交（`.gitignore` 已排除）。
- 所有 Demo 仅限授权环境；危险命令只在你自己的测试 ECS 上执行。
- 按需资源用完关机/释放，参考 `references/pricing.md`。
