---
name: huawei-cloud-hss-security-demo
description: 端到端搭建华为云 HSS 主机安全演示环境，并做可对客户展示的动态 GUI Demo。覆盖：安全组 + 按需 ECS + EIP + HSS Agent 安装 + 按需防护开启 + 危险命令触发 + 检出验证 + 官方图标架构图 + 攻击链动态前端。
---

# 华为云 HSS 主机安全 Demo（可复用 Skill）

一句话：**用华为云 HSS 把「危险命令 → 实时检出」这条安全链路跑通，并做成能对客户演示的动态页面。**

## 适用场景

- 给客户演示华为云主机安全（HSS）的检测能力；
- 快速搭建一个「可攻击、可检出、可直播」的安全 Demo 环境；
- 沉淀一套「立即可复现」的 ECS + HSS + GUI 流水线。

## 目录结构

```
.
├── SKILL.md                 # 本文件
├── README.md                # GitHub 说明
├── config.example.json      # 配置模板（复制为 config.json 并填 AK/SK）
├── scripts/
│   ├── common.py            # 公共：配置加载、SDK 客户端
│   ├── 01_setup_env.py      # 建安全组 + 按需 ECS + 绑定 EIP
│   ├── 02_install_agent.py  # 取官方安装命令并 SSH 安装 HSS Agent
│   ├── 03_enable_protect.py # 开启企业版按需防护
│   ├── 04_trigger_verify.py # 触发危险命令 + 查询检出
│   └── 05_gen_arch.py       # 用官方图标生成架构图 SVG
├── gui/
│   └── app.py               # 动态 Demo GUI（Flask，红白主题 + 攻击链动画）
├── assets/
│   ├── icons/               # 华为云官方图标（ECS/HSS/IAM/CTS/VPC）
│   └── arch_diagram.svg     # 生成好的示例架构图
├── references/
│   ├── hss-detection-rules.md   # 实测：哪些命令触发哪类事件
│   ├── pricing.md               # 按需费用估算
│   └── gotchas.md               # 踩坑记录（最有价值）
└── examples/
    └── arch_preview.png     # 架构图预览
```

## 前置条件

1. 华为云账号，子账号具备 **Tenant Administrator**（或 ECS/VPC/EIP/HSS 管理权限）；
2. 子账号 AK/SK；
3. 目标区域（默认 `cn-north-4` 华北-北京四）；
4. 一个已有的 VPC + 子网（默认 VPC 即可）；
5. Python 3.9+，可 `pip install huaweicloudsdkcore huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkeip huaweicloudsdkhss paramiko flask`。

## 快速开始

### 0. 配置

```bash
cp config.example.json config.json
# 编辑 config.json，填入 ak / sk / project_id / vpc_id / subnet_id
```

### 1. 建环境（安全组 + 按需 ECS + EIP）

```bash
python scripts/01_setup_env.py
```

产出：安全组 `hss-demo-sg`、ECS `hss-demo-ecs`（EulerOS 3.0，1核2GB，按需）、公网 EIP。
**注意**：ECS 默认不带公网 IP；脚本会绑定 1Mbps 按流量 EIP，并打印公网 IP。

### 2. 安装 HSS Agent

```bash
python scripts/02_install_agent.py
```

原理：调 `list_agent_install_script(os_type="Linux", os_arch="x86_64")` 取官方安装命令，
再通过 paramiko SSH 到 ECS 执行。安装后约 1–3 分钟 HSS 里主机状态变为 `online`。

### 3. 开启按需防护

```bash
python scripts/03_enable_protect.py
```

调用 `switch_hosts_protect_status(version="hss.version.enterprise", charging_mode="on_demand", host_id_list=[...])`。

### 4. 触发 + 验证

```bash
python scripts/04_trigger_verify.py
```

依次执行内置危险命令，并轮询 `list_security_events` 打印检出结果。

### 5. 起 Demo GUI

```bash
python gui/app.py 8899
# 打开 http://127.0.0.1:8899
```

### 6. 生成架构图

```bash
python scripts/05_gen_arch.py
# 产出 assets/arch_diagram.svg（官方图标 + 红白主题）
```

## 关键坑与解法（必读）

> 这些是实际踩过、且官方文档不显眼的点。

1. **HSS Agent 安装命令的 `os_type` 必须首字母大写 `Linux`**，`os_arch` 用 `x86_64`；否则 `list_agent_install_script` 报 `HSS.0002 Failed to parse the request`。
2. **`hss.version.professional`（专业版）在部分区域返回 `HSS.0001 Invalid parameter`**，改用 `hss.version.enterprise`（企业版）可正常开启按需防护。企业版功能更全，演示效果更好。
3. **`create_quotas_order` 是包年包月接口**（需要 `period_type/period_num`），按需**不要**走它；按需直接用 `switch_hosts_protect_status`。
4. **`batch_start_protection` 是「勒索病毒防护」**，不是通用「开启防护」；别用错。
5. **`/tmp` 下新建文件设 SUID 不会被 HSS 检出**；要在 `/usr/bin` 下新建文件再 `chmod u+s` 才会触发「File Privilege Escalation」。同一二进制反复 toggle 也只认第一次。
6. **HSS 检出有 30–90 秒延迟**，前端/脚本要留足等待。
7. **华为云 APIG 的 canonical URI 需要结尾带 `/`**（手写 AK/SK 签名时）；最省事是直接用官方 SDK。
8. **ECS 默认无公网 IP**，装 Agent 前必须先绑 EIP；安全组 SSH 规则要放行你的来源 IP。
9. **VPC 删除前要先删子网**（`Router contains subnets`）；子网删除后路由器关联是异步释放的，重试即可。
10. **`list_customer_bills_monthly` / 余额接口可能需要额外 BSS 权限**，Tenant Administrator 不一定含余额查询。

## 费用参考（按需，约 8–12 元/天）

| 资源 | 单价（约） |
|---|---|
| ECS s6.medium.2（1核2GB） | 0.1–0.2 元/小时 |
| EIP 1Mbps（按流量） | 0.02 元/小时 + 流量费 |
| HSS 企业版按需 | ~0.12 元/小时 |

用完记得关机/释放，详见 `references/pricing.md`。

## 安全注意

- **不要把 `config.json`、`demo_password.txt` 提交到 Git**（`.gitignore` 已排除）。
- AK/SK 建议用临时子账号，演示结束即删除/停用。
- Demo 用密码登录 ECS，仅限演示；生产请用密钥对 + 堡垒机。
