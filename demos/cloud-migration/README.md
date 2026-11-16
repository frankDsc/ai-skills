# 华为云搬迁实践实验室

100% 合成数据的可操作演练：生成源数据 → 全量复制 → 生成增量 → 差异补迁 → 冻结写入 → 全内容校验 → 逻辑割接 → 只读窗口回退。

2026-11-16 最初完成**真实 ECS 实测**：北京四 c6.large.2（2 核 4GB）、Ubuntu 22.04、40GB 高 IO 系统盘、5Mbps 按流量 EIP、独立 VPC/子网及只允许操作者 `/32` 的 SSH 安全组。前端包含本机 → SFTP → ECS 的 128 MiB 合成文件实传。原七步订单演练在同一真实 ECS 的逻辑隔离目录内执行。

随后扩展为**真实双 ECS 的 SMS 主机迁移测试**：源端安装官方 SMS Agent，目标端为同 VPC 新建、无公网 IP 的空白 ECS，迁移系统、应用与磁盘文件。前端的 SMS 区独立展示云端任务进度、Mbit/s 速率曲线、阶段、原始错误、数据验收和实际订单 HTTP 接口。三种测试分别记录；没有使用 DRS / OMS，也没有修改真实 DNS / ELB。SMS 持续同步遇到 Agent `SMS.0007 / NoneType vols_map` 异常，未通过；随后停写全量主机迁移已成功并通过独立启动及数据验收，详见 [VERIFICATION.md](VERIFICATION.md)。

实测记录见 [VERIFICATION.md](VERIFICATION.md)。旧 `frontend-preview.jpg` 为最初本机预演版本的历史外观；当前实时版本以运行页面为准。

复用已有华为云最佳实践 Demo 的声明式清单、官方 SVG 图标与动作/事件布局；图标直接内联，防止 WebView 中 SVG 图片引用失效。架构图遵循红白配色、正交连线及管理面/数据面分离规范。`manifest.json` 是从固定引擎动作及架构模型导出的演练清单；执行逻辑在 `engine.py`，并非通用 GUI 可直接加载的 SSH manifest。

## 启动

Python 3.9+。本机预演仅需 Flask；真实 ECS 还需 `requirements-cloud.txt` 中的官方 SDK 与 Paramiko：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py --port 8901
```

打开 `http://127.0.0.1:8901/`。有本轮真实资源状态时自动使用云端引擎，无资源时明确标为本机预演。顶部“开始真实传输”生成 128 MiB 随机合成文件，通过 SFTP 上传到专属 ECS，速率按实际字节与单调时钟计算，每秒刷新；目标长度和 SHA-256 一致后才验收。原七步订单演练和事件位于下方。割接后可执行只读回退；测试目标新写入后，后端会阻止简单回切。

前端支持按业务方向逐段流动、到达节点响应、0.5×/1×/2× 调速、暂停/继续、纯视觉重播、五秒无缓存状态刷新、JSON 记录导出和窄屏布局。重播不会请求执行接口。

运行时默认位于 `~/.local/state/cloud-migration-lab`。`MIGRATION_RUNTIME` 仅改变本机目录演练路径，不购买新云资源。云资源由既有私有状态管理，用户已授权本轮四小时后自动清理，主机配置云端到期删除；随后由本地自动化核验并清理网络及迁移资源。本地自动化要求电脑开机且应用可运行。保留运行时即可保留证据，不要并发运行多个修改任务。

## SMS 主机迁移

`sms_lab.py` 复用既有 `Cloud` 实例和已批准的专用源机，新建一台目标机；创建资源和格式化目标盘前必须取得用户的配置、预算、测试数据范围授权，并由用户确认 SMS 服务声明。不得对生产机器运行。

- 目标机仅向源端私网 `/32` 开放迁移端口 22 / 8900 与订单服务 8080，不创建第二个 EIP。
- 源端 `/opt/sms-migration-lab` 中部署 `order_service.py` 与 `sms-orders.service`，初始 10,000 笔合成订单和 2 GiB 随机文件。额外写入器不设置自启动，避免迁移后双写。
- Agent 从控制台的官方 OBS 下载入口获取，执行 SHA-256、CMS、CRL 检查后安装。既有 AK/SK 经加密 SSH 的 stdin 提供给授权的测试源机 Agent，不进入命令参数、源码、前端或导出。Agent 自身管理认证数据；迁移后停止 Agent 并移除测试安装目录，两台测试主机到期释放。生产应使用专用最小权限迁移账号。
- `sms_lab.py create-task` / `start` 调用真实 SMS API，`sms_watch.py` 每五秒只读采样，不调用伪造进度的 Agent 上报接口。
- `sms_lab.py freeze` 停止本次合成写入器并检查数据库；`create-task --cold` 仅允许停写后创建全量任务。是否成功由 SMS 状态与 `validate` 的独立实例身份、启动服务、SQLite 完整性、订单内容摘要和目标实际文件 SHA-256 共同判断。
- 前端“切到目标机”必须经过验收，实际读取对应主机的订单 HTTP 接口；这只是演示客户端访问路由，不更改 DNS / ELB。回切仅限本次无目标写入的只读演示。
- 私有 `sms-state.json` 保存资源/动作和验收，`sms-telemetry.json` 保存只读采样，避免采样覆盖操作状态。失败任务与日志证据保存在本机，不提交云资源标识。
- `cloud.py release --confirm <完整 Demo ID>` 会先清理 SMS 任务、目标机和辅助资源，再清理源机与网络；归属改变或挂载未知磁盘时拒绝删除。失败保留 ID 供重试。

## 合成数据及验证

- 初始：1,200 笔虚构订单、12 个文本附件和 1 个应用配置；不含真实身份、客户或业务数据。
- 增量：新增 25 笔、更新 10 笔、删除 5 笔，净订单数为 1,220；附件新增/修改/删除各 1 个。
- 全量：SQLite backup API 复制数据库，文件复制保留源端。
- 差异补迁：订单按主键比对全部列并 upsert/delete，文件按 SHA-256 比对；这是教学用差异补迁，**不是数据库日志 CDC**。
- 校验：对全部排序订单和文件摘要计算统一 SHA-256；逐项比较内容、删除与新增；目标执行只读 COUNT/SUM 业务探针。
- 割接：源端必须冻结、最新校验通过且当前内容仍一致；仅切换实验引擎逻辑路由，不修改外部业务入口。
- 回退：仅允许目标未产生新写入且两端仍一致的只读窗口回切。写后回退需要另行设计反向同步/合并，本实验会拦截，不做丢弃目标写入的演示。

## 真实 ECS 与只读询价

`cloud_plan.py` 查询北京四当前规格、可用区、Ubuntu 镜像和 BSS 按需价格，不创建资源；计划保存在仓库外私有运行时。价格确认后，`cloud.py provision --ssh-cidr <IPv4/32>` 创建并逐项记录专属资源；实例 ACTIVE 后用 `cloud.py bind-eip` 绑定 EIP。首次 `cloud.py pin-host` 仅对 API 核验名称匹配的本轮新实例固定 SSH 主机指纹（TOFU），后续拒绝未知/变更指纹。通过独立通道核对首个指纹可进一步加强首次连接信任。

资源状态、随机密码和 known_hosts 都在私有运行时，前端只返回必要信息。`cloud.py release --confirm <完整 Demo ID>` 仅释放本次记录且归属校验匹配的资源，先确认实例删除，再核对系统盘、EIP、安全组、子网与 VPC。逐项持久化移除 ID，失败保留剩余项。释放后前端显示历史实测并禁用云端动作，不自动重新购买或回退成模拟云连接。

### 可选：既有 ECS 的 SSH 配置别名

云资源创建与费用确认完成后，可复用同一引擎经 SSH 在指定测试 ECS 上运行。执行器通过 stdin 向远端 Python 发送固定引擎代码，远端使用专属路径 `.local/state/cloud-migration-lab`。

在仓库之外的 `~/.ssh/config` 配置 `migration-lab-ecs`，使用专门测试账号、私钥与已经验证的 `known_hosts`。安全组只放行操作者出口 `/32` 的 SSH，不开放演示 Web 端口。先人工核验主机指纹，再启动：

```sh
MIGRATION_SSH_HOST=migration-lab-ecs .venv/bin/python app.py --port 8901
```

自定义别名使用 `BatchMode=yes` 与 `StrictHostKeyChecking=yes`，指纹异常不会降级。前端与控制后端在本机，订单演练的源/目标为单 ECS 内不同目录，不能代表托管迁移服务性能。另有独立 SFTP 面板测量真正的本机到 ECS 网络传输。本轮已验收托管状态下的 Paramiko 路径，自定义 SSH 别名路径未单独验收。

只读账号检查使用 `cloud_check.py`；先安装 `requirements-cloud.txt`，通过 `HWC_CREDENTIALS_CSV` 读取既有凭证文件。CSV 列为 `Access Key Id` / `Secret Access Key`，恰好一行。只读检查中的 AK/SK 仅驻留进程内存，不写入仓库、前端或证据；SMS Agent 的授权认证另见上节。检查结果写入私有运行时的 `cloud-check.json`；页面显示“已核对”及时间，而非实时连接承诺。

## 架构约束与取舍

| 维度 | 本演练 | 生产迁移需验证 |
| --- | --- | --- |
| 业务与规模 | 同目录小样本练习 + 双主机 SMS 测试；10,000 笔初始订单、2 GiB 随机文件，源端系统占用另计 | 真实应用依赖、变更率、峰值 TPS、数据体量与停机窗 |
| 数据与合规 | 纯合成数据，无个人信息；区域假设北京四 | 数据驻留、跨境、加密、审计保留和许可证要求 |
| 安全与 IAM | 本机绑定、Host/Origin/令牌校验、固定动作、运行时 0700；Agent 使用已授权凭证，只安装于专用测试源机 | 最小权限迁移账号、时限授权、凭证轮换；存储加密及审计 |
| 网络 | 本机回环；可选 SSH 固定主机指纹、只放行操作者 `/32` | 地址不重叠、路由/DNS、专线/VPN/公网吞吐；分别验证控制与数据通道 |
| 可靠性 | SQLite 事务、原子状态文件、操作互斥、保留源端 | 多 AZ 的应用与托管数据库、重试、断点续传、兼容性及业务验收 |
| 性能 | 展示实测动作毫秒数与实际记录/文件差异 | 峰值压测、迁移限速、端到端带宽与源端负载；小样本不可外推 |
| 可观测性 | 实际动作事件、错误/拦截、校验摘要、JSON 导出 | CES/LTS/CTS，错误率与延迟门槛、复制积压和告警 |
| 灾备 / RTO / RPO | 割接条件为零内容差异；只读窗回退，不承诺生产 RTO/RPO | 业务假设 RTO≤30 分钟、割接 RPO=0，需停写/最后同步与恢复实测；目标写后回退单独设计 |
| 成本 | 源机含 EIP ¥0.4996/h；新增目标机与盘 ¥0.4796/h，另有 SMS 临时盘；本轮批准 ¥10，四小时后清理 | 重新询价后确认预算；释放全部相关资源后才停止对应计费 |

未引入多云、多区域、Kubernetes、队列或自建数据库集群。生产目标优先托管服务，但本实验使用 SQLite 把数据一致性过程做成可重复观察的最小练习。

## 生产方案映射

- MgC：资源发现、评估与迁移旅程编排，不是所有数据统一经过的传输节点。[官方迁移工具说明](https://support.huaweicloud.com/intl/zh-cn/usermanual-caf/caf_01_0154.html)
- SMS → ECS：核对 OS/磁盘/驱动，执行全量、增量与隔离启动验证。[SMS 最佳实践](https://support.huaweicloud.com/intl/zh-cn/bestpractice-sms/sms_12_0001.html)
- DRS → RDS：核对源目标版本、拓扑和对象支持，验证增量延迟与关键业务交易。[DRS 流程](https://support.huaweicloud.com/intl/en-us/qs-drs/drs_qs_0001.html)
- OMS → OBS：核对存储类型、对象数、元数据、归档及增量策略，OBS 不画进 VPC 子网。[MgC 存储迁移实践](https://support.huaweicloud.com/intl/zh-cn/bestpractice-oms/oms_05_5710.html)

## 检查

```sh
.venv/bin/python -m unittest -v test_lab.py test_transfer.py test_cloud.py test_sms.py
python3 diagram.py
python3 ../../skills/architecture-diagram-tool/scripts/validate_geometry.py geometry.json
node --check static/app.js
node --check static/transfer.js
node --check static/sms.js
```

当前共 15 项测试，覆盖订单完整性、过期门禁、写后回退拦截、HTTP 边界、状态读取不阻塞动作、速率计算、摘要失败不验收、证据恢复及资源归属检查。SMS 新增检查包括拒绝删除非本轮任务、拒绝删除挂有未知磁盘的目标机、拒绝删除父盘不匹配的快照、未验收目标不能接收演示流量；真实云端结果见实测记录。DRS / OMS 未集成。

## 速率与费用口径

SFTP 回调记录客户端已发送字节，当前速率采用约 1 秒滑动窗口，平均值为总发送量除以完整 SFTP 传输阶段耗时。目标接收长度和摘要独立确认后才验收。曲线保留最近 240 个采样点，约一分钟；生成文件、建连与摘要计算不混入传输速率。不将动画或短窗口峰值解释为公网性能承诺。

上传属于入云方向，5Mbps 配置对应出云方向。华为云文档说明，所购带宽不超过 10Mbit/s 时，常规区域入云限速为 10Mbit/s（部分区域例外）；短窗口还受客户端缓冲与突发影响。参见[入云与出云带宽](https://support.huaweicloud.com/eip_faq/faq_bandwidth_0007.html)和[EIP 按流量计费](https://support.huaweicloud.com/price-eip/eip_billing_0005.html)。
