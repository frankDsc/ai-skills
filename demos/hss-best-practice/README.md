# HSS 最佳实践实验室

北京四（`cn-north-4`）的真实 HSS 演示：独立测试 ECS + 官方 HSS Agent + 企业版防护 + 实际告警查询，包含 Flask 后端和红白配色前端。

复用仓库中两个 Skill：

- [华为云最佳实践生成器](../../skills/huawei-cloud-bestpractice-demo/SKILL.md)：SDK 客户端、资源规格与 HSS 接入流程。
- [架构图工具](../../skills/architecture-diagram-tool/SKILL.md)：官方图标、分层布局和正交连线检查。

## 启动

Python 3.10+。安装依赖并启动：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export HWC_CREDENTIALS_CSV="$HOME/Downloads/credentials.csv"
.venv/bin/python app.py
```

访问 `http://127.0.0.1:8899`。控制台只绑定本机，不对公网开放。云端 ECS 是演练目标，页面与持有 AK/SK 的控制后端运行在操作者本机。

凭证 CSV 应恰好一行，列名为 `User Name`、`Access Key Id`、`Secret Access Key`。AK/SK 仅从原 CSV 读入内存，不复制进仓库或返回前端。

默认运行时目录为 `~/.local/state/hss-best-practice`，可用 `HSS_DEMO_RUNTIME` 指定仓库之外的目录。运行时 `state.json` 保存资源 ID 和随机主机密码，权限为 0600；目录应保持私有，不能上传。`known_hosts` 固定首次 SSH 主机指纹，后续密钥变化会报错。

预检通过国内 IP 回显服务识别 SSH 出口；分流代理下，国外 IP 回显结果可能与连接北京 ECS 的真实出口不同。可设置 `HSS_SSH_SOURCE_IP` 显式指定单个 IPv4 地址。重新预检后执行“创建环境”会校准本 Demo 的 SSH 规则。

## 演示流程

1. **预检**：校验 IAM 项目、HSS 权限、x86 Ubuntu 22.04 镜像、小规格 ECS 和当前公网 SSH 来源。
2. **创建环境**：独立 VPC、子网、安全组，按需小规格 ECS、40 GB SAS 系统盘、1 Mbps 按流量 EIP。22 端口只允许操作者出口 `/32`。
3. **安装 Agent**：获取北京四官方安装命令，安装后轮询 HSS，直到 Agent 在线。安装令牌不展示。
4. **开启企业版**：使用 `hss.version.enterprise` 和 `on_demand`，等待云端防护状态确认。
5. **受控演练**：在专用 ECS 创建只会立即退出的 `/usr/bin/true` 副本，设置 SUID。不会建立反弹连接、投放 Webshell 或运行挖矿程序。
6. **验证**：每 5 秒读取当前主机真实 HSS 事件；执行成功与检出成功分别展示。超过 180 秒未出现匹配告警时明确提示待排查。事件匹配按主机、发生时间和提权事件类型，不声称是绝对精确的事件关联。
7. **复核与处置**：查询主机漏洞及基线报告。空列表、扫描尚未上报与接口错误分开处理，不自动修复系统。清理测试文件后，可将本次主机时间窗口内的文件提权事件手动标为已处理，并复核云端实际状态。
8. **清理**：先撤销并删除测试文件；完成演示后关闭 HSS，并删除本次记录的 ECS、系统盘、EIP、安全组、子网和 VPC。输入完整 Demo ID 后才允许释放。

当前版本不自动开通 CTS、CBR、SMN 或多区域容灾；架构图将 CTS 明确标为可选目标。主机入侵告警来自 HSS，而不是 CTS。

## 后端接口

| 接口 | 作用 |
| --- | --- |
| `GET /api/health` | 本机服务与认证状态 |
| `GET /api/status` | 当前 ECS、Agent、防护、资源、计划及异步任务 |
| `GET /api/events` | 当前 Demo 主机的真实 HSS 安全事件 |
| `GET /api/actions` | 固定的后端动作清单 |
| `POST /api/execute` | 执行允许的动作 ID，返回异步任务 ID |

写操作必须由本机页面携带启动时生成的 `X-Demo-Token`；服务检查 Host、Origin 并拒绝并发云操作。没有任意命令执行接口。

CLI 可用于重复部署或清理：

```bash
.venv/bin/python app.py --action preflight
.venv/bin/python app.py --action provision
.venv/bin/python app.py --action install
.venv/bin/python app.py --action protect
.venv/bin/python app.py --action exercise
.venv/bin/python app.py --action cleanup_artifacts
.venv/bin/python app.py --action acknowledge
.venv/bin/python app.py --action cleanup --confirm '<demo-id>'
```

不要同时运行 CLI 写操作与界面写操作；Web 锁仅保护同一服务进程。公网出口变化时须重新预检并更新 Demo 安全组规则后再 SSH。

## 检查

```bash
.venv/bin/python -m unittest -v test_app.py
.venv/bin/python diagram.py
.venv/bin/python ../../skills/architecture-diagram-tool/scripts/validate_geometry.py geometry.json
node --check static/app.js
```

HTTP 边界单测使用隔离替身，不会创建云资源；实际 Demo 不使用模拟后端。几何校验覆盖节点与连接线，VPC / Agent 防护边界是有意嵌套，需额外进行视觉检查。

## 费用、恢复与边界

ECS、系统盘、EIP、公网流量和 HSS 按需防护会产生费用，以华为云控制台账单和价格页为准。关机不等于释放，磁盘和 EIP 可能继续计费；没有设置自动销毁。

每创建一个资源即记录 ID，失败后可继续执行或按记录清理。清理流程不会枚举释放其他 EIP 或处理默认 VPC。CLI 或 API 超时不一定表示云端没有执行，请先查看资源状态，避免重复购买。

这是单主机、单可用区演示，不提供生产可用性 SLA 或数据灾备承诺。演示数据不包含生产业务，重建环境即可恢复；需要生产部署时另行定义 RTO/RPO、备份、IAM 最小权限和运维访问方式。

## 官方参考

- [HSS 查询主机状态](https://support.huaweicloud.com/intl/zh-cn/api-hss2.0/ListHostStatus.html)
- [切换主机防护](https://support.huaweicloud.com/eu/api-hss2.0/SwitchHostsProtectStatus.html)
- [护网或重保场景下的告警处置](https://support.huaweicloud.com/bestpractice-hss2.0/hss_06_0040.html)
- [华为云价格详情](https://www.huaweicloud.com/price_detail.html)
