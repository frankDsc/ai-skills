---
name: huawei-cloud-bestpractice-demo
description: 把任意华为云「最佳实践」做成可对客户演示的 Demo。支持安全、大数据、数据库、AI、容器、网络、存储等任意领域：先按最佳实践索引选型，再生成声明式 manifest，建底层资源（VPC/ECS/EIP/OBS/RDS 等），产出华为云官方图标架构图与同款动态 GUI（动作触发 + 架构图动画 + 实时事件流）。
---

# 华为云最佳实践 Demo 生成器

> 一句话：**用户说「做 XX 最佳实践」，本 skill 让它变成「能跑、能看、能演示」的完整 Demo。**
>
> **所有 Demo 都使用真实资源**：至少 1 台真实 ECS，后端通过 SSH 在虚拟机上真实执行动作命令，产出真实输出/告警。没有 mock。

## 能力边界

| 能力 | 说明 |
|---|---|
| 任意领域 | 安全 / 大数据 / 数据库 / AI / 容器 / 网络 / 存储 / 迁移…… |
| 底层资源 | VPC、安全组、ECS、EIP、OBS、RDS 等（按需，可释放） |
| 架构图 | 从 manifest 生成，使用**华为云官方图标**（`assets/icons/`，27 个） |
| 动态 GUI | 卡片 + 架构图 + 可触发动作 + 架构图动画 + 事件流 |
| 后端 | `ssh`（SSH 到**真实 ECS** 执行命令，默认）/ `hss`（SSH + 真实 HSS 检测） |

## 核心：manifest（声明式 Demo 描述）

一个 Demo = 一个 `manifest.json`。**新增任意领域，本质就是写一个新的 manifest。**

```json
{
  "id": "bigdata-demo",
  "title": "华为云大数据最佳实践 Demo",
  "subtitle": "数据接入 → 数据湖 → 数仓 → 可视化",
  "region": "cn-north-4",
  "backend": "ssh",
  "cards": [{"label": "DWS", "value": "运行中", "tone": "green"}],
  "nodes": [
    {"id": "src", "label": "数据源", "sub": "RDS/文件", "icon": "rds", "col": 0, "row": 1},
    {"id": "dws", "label": "DWS", "sub": "数据仓库", "icon": "dws", "col": 3, "row": 1}
  ],
  "edges": [{"from": "src", "to": "dws", "flow": "data"}],
  "actions": [
    {"id": "run_etl", "label": "触发 ETL", "desc": "在真实 ECS 上跑数据流",
     "flow": ["src", "dws"],
     "cmd": "awk -F, 'NR>1{s+=$2} END{print s}' /data/lake/orders.csv",
     "event": {"name": "ETL 完成", "detail": "聚合结果", "severity": "Success"}}
  ]
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` / `title` | ✅ | Demo 标识 / 标题 |
| `subtitle` / `region` | | 副标题 / 区域 |
| `backend` | | `ssh`（默认，连真实 ECS）或 `hss` |
| `cards` | | 顶部 4 张状态卡：`label` / `value` / `tone`(green/red) |
| `nodes` | ✅ | `id` / `label` / `sub` / `icon`(见 `assets/icons/` 文件名) / `col` / `row` |
| `edges` | | `from` / `to` / `flow`(`data` 实线红 / `control` 虚线灰) |
| `actions` | ✅ | `id` / `label` / `desc` / `flow`(节点 id 序列) / `cmd`(**在真实 ECS 上执行的命令**) / `event` |

> 布局用 `(col,row)` 网格，节点自动排布；连线自动正交路由。

### 高级字段（嵌套分组 / 垂直连线）

| 字段 | 说明 |
|---|---|
| `node.type: "group"` + `node.children: [...]` | **分组框**：children 可以是普通节点，也可以是另一个 group，实现嵌套（如 `VPC > HSS > ECS`） |
| `node.w` / `node.h` | 分组框占几个网格列 / 行 |
| `node.w_px` / `node.h_px` | 分组框的像素尺寸（嵌在父框内时精确控制大小） |
| `node.icon` | 分组框标题前也可显示图标 |
| `edge.dir: "up" / "down"` | 连线走垂直方向（如审计流 `VPC → CTS` 向上） |

### 图标方案（重要）

- 图标**内联成 SVG `<g>` 路径**（`lib/arch.py` 的 `_icon_group` 会重命名 clipPath id 防冲突），**不要用 `<image>`**——部分 WebView 对 SVG-in-SVG 的 `<image>` 渲染不稳定，会出现「部分图标空白」。
- 新增图标：把 `.svg` 放进 `assets/icons/`；`scripts/rasterize_icons.py` 可批量转 PNG（备用）。
- 内置 27 个图标，含自绘的 `attacker`（官方库无攻击者图标）。

### 动态效果（按业务语义设计）

- 动态效果表达本 Demo 的核心业务动作；不要把所有场景都画成攻击链。依据 action 的 `flow` 在相关节点之间逐段移动光点/数据包，并在到达时响应对应节点；支持状态分阶段呈现、调速、暂停和纯视觉重播。重播不得再次提交后端动作。
- 先定义每个 action 的业务含义、起点、终点、流向、阶段和可观察结果，再选择颜色与动画。颜色需在图例中说明，遵循业务语义，不把红色默认解释成攻击。
- 示例：数据迁移展示源端读取 → 传输/校验 → 目标端写入，并呈现记录数、进度、校验结果；备份展示数据源 → 快照/备份库 → 恢复验证；ETL 展示接入 → 清洗转换 → 数仓 → 报表；部署展示制品 → 构建 → 发布 → 健康检查；普通业务流展示请求和响应。
- 仅当用户请求安全演练且场景确实包含对抗行为时，才显示攻击路径；将演练行为、主机侧检测、云端告警和处置区分开。只有匹配到本次主机、时间窗、事件类型及新事件 ID 的真实告警后，才显示“检出”状态。按 HSS 事件时间精度归一化，并说明匹配只是演示级关联。
- 事件流每 5 秒刷新并禁用缓存；对于不产生安全告警的 Demo，显示真实动作输出、进度、迁移统计或业务状态，不伪造 HSS 告警字段。

### 架构语义约定（重要）

1. **防护类服务用「框」包住被保护资源**：HSS 应是包住 ECS 的 `group`，表示 Agent 装在 VM 内。
2. **嵌套边界**：VPC 在外、HSS 在内（`VPC > HSS > ECS`）。
3. **数据/业务流与控制流分开表达**：请求、数据迁移、备份和安全演练等流向按实际业务描述；IAM 等管理面组件不应误画成数据路径节点。
4. **审计流指向 CTS**：`资源 → CTS`，箭头朝 CTS。
5. 业务/攻击流实线红，控制/审计流虚线灰；虚线走独立走廊，不压方框。

## 工作流（Agent 执行步骤）

### 0. 环境

```bash
pip install huaweicloudsdkcore huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkeip huaweicloudsdkhss paramiko flask
cp config.example.json config.json   # 必填 AK/SK（所有 Demo 都建真实资源）
```

### 1. 选型（查索引与参考架构）

先读 [`references/best-practices-index.md`](references/best-practices-index.md)：按领域找到「产品组合 + 最佳实践要点 + 推荐 Demo 流程 + 图标名」。复杂或行业化场景再查 Haydn 架构模板；需要云资源操作能力时再检索华为云官方 Agent Skills。检索到模板或 Skill 后，提取架构和约束，不能照搬成已验证的生产设计。具体检索、复用、校验和安全边界见 [`references/huawei-reference-architectures-and-skills.md`](references/huawei-reference-architectures-and-skills.md)。产品能力/图标可用性见 [`references/service-catalog.md`](references/service-catalog.md)。

### 2. 写 manifest

复制 `templates/manifest.example.json`，改成目标领域的节点/连线/动作。
- 每个 `action` 必须有 `cmd`（在真实 ECS 上执行的命令）；
- `backend` 用 `ssh`（默认）或 `hss`；**没有 mock，所有 Demo 都连真实资源**。

### 3. 建底层资源（必需）

每套 Demo 至少创建 1 台真实 ECS（执行节点）+ EIP：
- 直接调用 `lib/provision.py` 的 `setup_vm()`（安全组 + 按需 ECS + EIP 一步到位）；
- 产出写入 `state.json`（server_id / public_ip 等）与 `demo_password.txt`；
- 参考 `examples/bigdata-demo/scripts/setup.py` 或 `examples/hwcloud-hss-demo/scripts/01_setup_env.py`。

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
- 左侧点动作 → 架构图按业务语义展示逐段流动与节点响应；
- 右侧事件流实时出现真实进度、输出、指标或告警；安全告警仅用于安全场景。

## 目录结构

```
.
├── SKILL.md / README.md / config.example.json
├── lib/
│   ├── common.py        # 配置 + SDK 客户端 + SSH
│   ├── manifest.py      # manifest 加载/校验
│   ├── arch.py          # manifest → 官方图标架构图 SVG
│   └── provision.py     # 真实资源：安全组 + ECS + EIP
├── gui/
│   ├── app.py           # 通用动态 GUI（读 manifest）
│   └── backends/        # ssh（真实 ECS）/ hss（真实 HSS）
├── examples/
│   ├── bigdata-demo/    # 大数据示例（真实 ECS + 真实命令）
│   └── hwcloud-hss-demo/# 安全示例（真实 ECS + HSS）
├── assets/icons/        # 24 个华为云官方图标
├── templates/manifest.example.json
└── references/          # 服务目录 / 最佳实践索引 / 踩坑 / 费用 / 图标来源
```

## 后端扩展

默认 `ssh` 后端已连真实 ECS；如需接入其它真实资源（如 DWS/RDS 的 API），实现三个方法：

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
- 资源释放使用原生二次确认，再要求完整 Demo ID。后端只删除状态文件记录且通过归属校验的资源；确认 ECS 删除后再删除 EIP、安全组、子网及 VPC。逐项成功即持久化移除 ID，失败保留剩余资源 ID 供重试。
- 释放成功需持久化已释放状态并刷新顶部卡片、资源地址和流程；关机不等于释放完成。测试文件、账号、计划任务的清理与云资源释放分开操作，告警只在清理产物后处置。
- HSS 场景使用固定动作白名单和回环限定；记录真实观察到的告警及未检出的策略条件，不把执行成功说成检测成功。
