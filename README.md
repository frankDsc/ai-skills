# ai-skills

> AI Agent 可复用的 Skills 集合。每个 skill 都是「可被 Agent 直接执行」的完整包（含 `SKILL.md` 指令 + 脚本 + 资源）。

## Skills 索引

| Skill | 说明 | 状态 |
|---|---|---|
| [**architecture-diagram-tool**](skills/architecture-diagram-tool/) | **架构图工具**：云架构逻辑审视、官方服务图标、红白或厂商品牌配色、正交连线和几何碰撞检查；内置华为云 27 个 Draw.io 图标库 | ✅ 可用 |
| [**huawei-cloud-bestpractice-demo**](skills/huawei-cloud-bestpractice-demo/) | **华为云最佳实践 Demo 生成器**（通用）：任意领域（安全/大数据/数据库/AI/容器/网络/存储）→ manifest → 官方图标架构图 + 动态 GUI（动作触发 + 架构图动画 + 事件流）+ **真实 ECS 资源**（后端 SSH 执行真实命令） | ✅ 可用 |

## 完整 Demo

- [HSS 最佳实践实验室（前端 + 后端）](demos/hss-best-practice/)：北京四真实 ECS、Agent 安装、企业版防护、十种受控场景、动态攻击与检测链路、实际 HSS 告警与限定资源清理。

## 架构图工具使用

调用 `$architecture-diagram-tool`，或说“使用架构图工具绘制华为云架构图”。将 `skills/architecture-diagram-tool` 完整复制到支持 `SKILL.md` 的运行环境的 Skill 目录，保留所有相对资源路径。

详细使用方式、图标来源和几何校验范围见 [架构图工具说明](skills/architecture-diagram-tool/README.md)。

## 通用 Skill 能做什么

用户说「做一个 XX 最佳实践」，Agent 读取 skill 后：

1. 查 `references/best-practices-index.md` 选型（产品组合 + 最佳实践 + 演示流程）；
2. 写一个 `manifest.json`（节点 / 连线 / 动作 / 事件）；
3. 用官方图标生成架构图；
4. 起动态 GUI（与 HSS Demo 同款效果）；
5. 用 SDK 真实创建 VPC/ECS/EIP 等资源（**必需，所有 Demo 都连真实虚拟机**）。

**新增一个领域 = 新增一个 manifest，无需改代码。**

## 内置示例

| 示例 | 领域 | 后端 |
|---|---|---|
| `skills/huawei-cloud-bestpractice-demo/examples/bigdata-demo` | 大数据（真实 ECS 数据流水线） | ssh（真实） |
| `skills/huawei-cloud-bestpractice-demo/examples/hwcloud-hss-demo` | 安全（ECS + HSS 检测） | hss（真实） |

## 快速体验

```bash
cd skills/huawei-cloud-bestpractice-demo
pip install huaweicloudsdkcore huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkeip paramiko flask
cp config.example.json config.json               # 填 AK/SK/project_id/vpc_id/subnet_id
python examples/bigdata-demo/scripts/setup.py    # 建真实 ECS + EIP
python gui/app.py --manifest examples/bigdata-demo/manifest.json --port 8899
# 打开 http://127.0.0.1:8899
```

## 约定

- 每个 skill 一个目录：`skills/<skill-name>/`；
- 每个 skill 必含 `SKILL.md`（Agent 指令）与 `README.md`（人读说明）；
- **敏感信息一律不提交**：AK/SK、密码、`config.json`、`state.json` 均在 `.gitignore` 中。

## 新增一个 Skill

```bash
mkdir -p skills/<new-skill>
# 放入 SKILL.md + 脚本 + 资源
git add skills/<new-skill>
git commit -m "feat(<new-skill>): ..."
git push
```

## 安全声明

所有 Demo 仅用于**授权环境**的演示与学习。危险命令触发仅限你自己的测试 ECS。

## License

MIT
