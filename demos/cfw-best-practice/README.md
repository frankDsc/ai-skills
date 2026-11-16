# CFW 云防火墙最佳实践 · 方案预览

当前交付为 **HSS 风格本地前端 + 官方图标架构图 + 只读账号核验 + 策略方案推演**。
真实 CFW 和双 ECS 测试环境未创建，也没有真实请求、吞吐或安全告警结果。

2026-11-16，北京四项目的官方 `ListFirewallList` 返回 `is_support_postpaid=false`、实例总数为 0；专业版购买页也仅提供包年/包月（¥9,600/月）。虽然 BSS 能返回按需报价，报价不代表当前账号可以购买。用户仅批准按需、预算 ¥10，并明确按需不可选时保留预览，因此未提交订单、未创建计费资源。没有使用主机 iptables 冒充 CFW。

## 本地运行

沿用 HSS 示例的 Flask 结构与红白视觉，不部署外部网站。凭证仅由本机后端在点击核验时读取。

```bash
python -m pip install -r requirements.txt
python app.py --preflight    # 只读 IAM 项目查询 + CFW ListFirewallList
python app.py                # http://127.0.0.1:8902/
python -m unittest -v test_app
```

默认凭证为 `~/Downloads/credentials.csv`（恰好一行，列名 `Access Key Id` / `Secret Access Key`）；可用 `HWC_CREDENTIALS_CSV` 改为其他本机路径。不要把文件放入 Git。运行快照保存在 `~/.local/state/cfw-best-practice-lab/account-check.json`，文件权限 0600；`CFW_DEMO_RUNTIME` 可改保存目录。账号 ID、原始响应、凭证不进入页面或导出文件。

浏览器每 5 秒刷新**本地快照**；只有“重新核验按需资格”发起新的云端查询，页面分别展示两个时间。无云资源写入执行器，任何 `/api/execute` 请求都返回 409，即使将来核验为支持按需，也不会自行采购。

## 最小目标架构与验收

两个独立 VPC，各有 ECS、40GB 高 IO 盘、流量型 5Mbps EIP 和安全组。一侧运行固定探测服务（18080），另一侧运行仅含合成订单的测试应用（8080）。两侧不做私网互联，固定请求走 EIP；CFW 仅保护本轮业务 EIP。CFW 是托管的透明互联网边界防护，不安装在业务 ECS 内。管理 SSH 仅允许操作端 /32，测试端口仅允许对端 /32。

| 场景 | 真实验收要求 |
|---|---|
| 入站 ACL | 基线 HTTP 成功 → 精确拒绝 → 真实入站拒绝日志命中本轮五元组/规则 ID → 恢复成功 |
| 出站 ACL | 业务机到自有探测端基线成功 → 出站拒绝 → 独立关联出站日志 → 恢复成功 |
| 优先级 | 保存策略顺序，使用固定测试流调整精确规则优先级；核对实际命中规则 ID，恢复原策略 |
| IPS（可选） | 固定无破坏输入只针对自有应用；实际攻击日志匹配本轮资产/时间/特征才标记检出；未命中如实记录 |

前端的“播放方案推演”只展示上述**预期**步骤和逻辑流向，不发送请求、不生成模拟云日志、不增加实测计数。动画速度和暂停只影响展示。

网络与安全以最小权限为先：不接入其他账号资产、不修改既有 IAM 权限、不开放任意目标或原始 shell 命令。真实接入时需先保存策略和允许管理 SSH，再加入拒绝规则；API 回退路径必须不依赖 SSH。

单区域、单业务机用于低成本教学，不提供生产 HA 或跨区灾备。仅合成数据，本轮不设生产 RTO/RPO 承诺；恢复用撤销演练规则 + 请求复测验收。实际观测应包含响应耗时/成功率、五元组、云端访问日志与匹配规则 ID，IPS 告警单独存放。5Mbps EIP 会限制演练流量，不能用其结果推导 CFW 的产品吞吐上限。不额外购买 HSS、WAF、ER、LTS。

## 费用与生命周期

`plan.json` 保留 2026-11-16 账户 BSS 按需询价快照（CNY，无折扣）。CFW 询价资源为 `hws.resource.type.cfw` / `cfw.professional` / `usage_duration`；流量为 `hws.resource.type.cfw.exp.trafficflow` / `cfw.expack.trafficflow.professional` / `megabyte`。

| 项目 | 费率 | 2 小时估算 |
|---|---:|---:|
| 1 个 CFW 专业版 | ¥2.16/小时 | ¥4.32 |
| 2 台 2核4GB ECS | ¥0.46/台·小时 | ¥1.84 |
| 2 块 40GB 高 IO 盘 | ¥0.0196/块·小时 | ¥0.0784 |
| 2 个流量型 EIP | ¥0.02/个·小时 | ¥0.08 |
| CFW 处理流量，总计 1GB | ¥0.36/GB | ¥0.36 |
| EIP 出云流量，总计 1GB | ¥0.80/GB | ¥0.80 |
| 合计 | 固定 ¥3.1592/小时 | **¥7.4784，约 ¥7.48** |

预算 ¥10 为执行约束与估算，不是云平台硬扣费上限。未部署，本轮新增费用为 ¥0，无需清理，也**没有启动自动清理任务**。不以本轮费用替代账户总账单。真实部署后应从首个资源创建成功起安排约 2 小时释放；该本机方案要求电脑在线。仅关机不能停止磁盘/EIP/CFW 等费用，需删除并逐项核验。

## 资格开通后的后续工作（尚未执行）

1. 向华为云确认当前账号、北京四项目的专业版按需资格；不扩大 IAM 权限，不自动改区域或月付。重新查询资格和价格；若超出已批准范围，先给出新方案。
2. 接入真实 CFW 执行器，采购明确使用 `postPaid`；先确认开通成功，再创建专用双机网络。每次写入立即保存本轮资源 ID / 标签，失败时保留可清理状态。
3. 从首个资源成功创建起建立 2 小时清理任务；给 ECS 配置原生定时删除作为补充。CFW/EIP/磁盘仍需独立释放。清理必须对每个 ID 做归属校验，禁止账号级批量删除。
4. 部署固定的合成订单与探测服务，管理规则先行，接入单个业务 EIP。按表执行并持久化真实证据；对日志匹配使用时间窗 + 五元组 + 方向 + 规则 ID。
5. 导出真实结果，释放本轮 CFW、ECS、盘、EIP、带宽及网络；逐个查询确认删除。部分失败应重试并通知，不把“已发起删除”当作停止计费。

## 架构图与来源

语义模型 `manifest.json` 与渲染器 `diagram.py` 分离；`architecture.svg` 是可编辑文本 SVG，官方服务图标以 data URI 内嵌，离线可用。`geometry.json` 记录卡片、外部标签与正交路径，使用 `architecture-diagram-tool/scripts/validate_geometry.py` 校验。

图标来自 [huaweicloud-latam/drawio-libraries](https://github.com/huaweicloud-latam/drawio-libraries)，color v3.2，提交 `52c33aa12fb816a5de403da85067e1c0f039b5be`；使用 ECS / CFW / IAM 的精确服务图标，未改画。日志卡为 CFW 原生功能，未冒用独立云服务图标。

官方说明：[按需开通](https://support.huaweicloud.com/usermanual-cfw/cfw_01_0265.html)、[按需计费](https://support.huaweicloud.com/price-cfw/cfw_03_0005.html)、[列表 API](https://support.huaweicloud.com/api-cfw/ListFirewallList.html)、[规则与流量排查](https://support.huaweicloud.com/intl/zh-cn/cfw_faq/cfw_01_0320.html)。
