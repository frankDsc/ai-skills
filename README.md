# ai-skills

> AI Agent 可复用的 Skills 集合：华为云安全 Demo、架构图、自动化脚本等。
> 每个 skill 都是「可被 Agent 直接执行」的完整包（含 `SKILL.md` 指令 + 脚本 + 资源）。

## Skills 索引

| Skill | 说明 | 状态 |
|---|---|---|
| [**hwcloud-hss-demo**](skills/hwcloud-hss-demo/) | 华为云 HSS 主机安全 Demo 全流程：安全组 + 按需 ECS + EIP + HSS Agent + 按需防护 + 危险命令触发 + 检出验证 + 红白动态 GUI + 官方图标架构图 | ✅ 可用 |

## 目录结构

```
.
├── README.md                     # 本文件
├── skills/
│   └── hwcloud-hss-demo/         # 华为云 HSS 安全 Demo skill
│       ├── SKILL.md              # Agent 指令（工作流 + 关键坑）
│       ├── README.md             # 人读说明
│       ├── config.example.json   # 配置模板
│       ├── scripts/              # 01-05 自动化脚本
│       ├── gui/                  # 动态 Demo GUI
│       ├── assets/               # 官方图标 + 架构图
│       ├── references/           # 踩坑 / 检测规则 / 费用
│       └── examples/             # 预览图
└── ...
```

## 快速使用（以 hwcloud-hss-demo 为例）

```bash
cd skills/hwcloud-hss-demo
pip install huaweicloudsdkcore huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkeip huaweicloudsdkhss paramiko flask
cp config.example.json config.json   # 填 ak/sk/project_id/vpc_id/subnet_id
python scripts/01_setup_env.py
python scripts/02_install_agent.py
python scripts/03_enable_protect.py
python scripts/04_trigger_verify.py
python gui/app.py 8899               # http://127.0.0.1:8899
python scripts/05_gen_arch.py
```

## 约定

- 每个 skill 一个目录：`skills/<skill-name>/`；
- 每个 skill 必含 `SKILL.md`（Agent 指令）与 `README.md`（人读说明）；
- **敏感信息一律不提交**：AK/SK、密码、`config.json`、`state.json` 等均在 `.gitignore` 中。

## 新增一个 Skill

```bash
mkdir -p skills/<new-skill>
# 放入 SKILL.md + 脚本 + 资源，然后
git add skills/<new-skill>
git commit -m "feat(<new-skill>): ..."
git push
```

## 安全声明

本仓库所有 Demo 仅用于**授权环境**的演示与学习。危险命令触发仅限你自己的测试 ECS，切勿用于生产或他人系统。

## License

MIT
