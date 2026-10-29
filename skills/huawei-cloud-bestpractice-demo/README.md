# 华为云最佳实践 Demo 生成器

> 把任意华为云「最佳实践」变成**能跑、能看、能演示**的 Demo：官方图标架构图 + 动态 GUI + 可触发动作 + 实时事件流。

[English](#english) · [中文](#中文)

---

## 中文

### 这是什么

一个**通用**的 Demo 生成器（不是只针对安全）。给定任意领域（大数据、数据库、AI、容器……），
它把「产品组合 + 最佳实践 + 演示流程」沉淀成一个声明式 `manifest.json`，然后：

1. 用**华为云官方图标**生成架构图；
2. 起一个**动态 GUI**（卡片 + 架构图 + 动作按钮 + 事件流 + 架构图红点流动动画）；
3. **必需**：通过 SDK 真实创建底层资源（VPC / ECS / EIP …），后端 SSH 到真实虚拟机执行动作。

> **没有 mock**：每个 Demo 都连真实资源。

### 快速开始（真实 ECS + 真实命令）

```bash
pip install huaweicloudsdkcore huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkeip paramiko flask
cp config.example.json config.json               # 填 AK/SK/project_id/vpc_id/subnet_id
python examples/bigdata-demo/scripts/setup.py    # 建真实 ECS + EIP
python gui/app.py --manifest examples/bigdata-demo/manifest.json --port 8899
# 打开 http://127.0.0.1:8899
```

点「跑 ETL 聚合」→ 架构图红点跑动 → 右侧显示**真实 ECS 上的命令输出**。

### 两个内置示例

| 示例 | 领域 | 后端 | 说明 |
|---|---|---|---|
| [`examples/bigdata-demo`](examples/bigdata-demo/) | 大数据 | `ssh` | 真实 ECS 上跑数据流水线命令 |
| [`examples/hwcloud-hss-demo`](examples/hwcloud-hss-demo/) | 安全 | `hss` | 真实 ECS + HSS 检测，含建资源脚本 |

### 核心：manifest

```json
{
  "id": "bigdata-demo",
  "title": "华为云大数据最佳实践 Demo",
  "backend": "ssh",
  "cards": [{"label": "ECS", "value": "运行中", "tone": "green"}],
  "nodes": [{"id": "src", "label": "数据源", "icon": "rds", "col": 0, "row": 1}],
  "edges": [{"from": "src", "to": "dws", "flow": "data"}],
  "actions": [{"id": "run_etl", "label": "触发 ETL", "flow": ["src", "dws"],
               "cmd": "awk -F, 'NR>1{s+=$2} END{print s}' /data/lake/orders.csv",
               "event": {"name": "ETL 完成", "detail": "聚合结果", "severity": "Success"}}]
}
```

完整字段见 [SKILL.md](SKILL.md) 与 [templates/manifest.example.json](templates/manifest.example.json)。

### 新增一个领域

1. 在 `references/best-practices-index.md` 找到该领域的产品组合与最佳实践；
2. 复制 `templates/manifest.example.json` 改成新节点/连线/动作；
3. `python gui/app.py --manifest examples/<new>/manifest.json` 即可演示。

> 新增领域 = 新增一个 manifest，**不需要改代码**。

### 真实资源（可选）

安全示例含完整脚本：`examples/hwcloud-hss-demo/scripts/01_setup_env.py` → `02_install_agent.py` → `03_enable_protect.py` → `04_trigger_verify.py`。
配置见 `config.example.json`。

### 目录

```
lib/        manifest 校验 + 通用架构图生成器
gui/        通用 GUI + 后端（ssh / hss）
assets/     24 个华为云官方图标
examples/   大数据 + HSS 两个示例
references/ 服务目录 / 最佳实践索引 / 踩坑 / 费用 / 图标来源
```

### 图标来源

华为云官方图标库 [huaweicloud-latam/drawio-libraries](https://github.com/huaweicloud-latam/drawio-libraries) v3.2（color 版）。

---

## English

A **generic** Huawei Cloud best-practice demo generator:
declare a `manifest.json` (nodes / edges / actions), and get an official-icon architecture diagram plus a dynamic GUI with action buttons, flow animation and a live event feed. Ships with 24 official icons and two examples (big data, HSS).

```bash
pip install flask
python gui/app.py --manifest examples/bigdata-demo/manifest.json --port 8899
```

See [SKILL.md](SKILL.md) for the manifest spec and the full workflow.

## License

MIT
