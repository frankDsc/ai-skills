# 最佳实践索引（按领域）

> 用法：用户说「做 XX 最佳实践」→ 在本文件找到对应领域 → 拿到「产品组合 + 最佳实践 + Demo 流程 + 图标」→ 写 manifest。

## 一、安全（主机/数据/身份）

**产品组合**：ECS + 安全组 + EIP + HSS + IAM + CTS + KMS
**最佳实践**：
1. 安全组最小放行，SSH 只开白名单；
2. 主机装 HSS，开企业版按需防护；
3. IAM 最小权限 + MFA；
4. CTS 开启操作审计；
5. KMS 托管密钥加密敏感数据。

**Demo 流程**：攻击者 → 公网边界 → ECS（HSS Agent）→ HSS 检出 → 告警
**图标**：`ecs` `hss` `iam` `cts`；边界用空图标通用框
**后端**：`hss`（真实 HSS 检测）

## 二、大数据（数据湖 / 数仓 / BI）

**产品组合**：RDS/文件 → DIS（流式）+ OBS（数据湖）→ DataArts（集成/调度）→ DWS（数仓）→ DLV（大屏）/ BI
**最佳实践**：
1. 原始数据入 OBS 数据湖，分层（ODS/DWD/DWS/ADS）；
2. 流式用 DIS，批用 CDM/OBS；
3. DataArts 做统一调度与数据治理；
4. DWS 做分析型数仓，冷热分层；
5. DLV/BI 做可视化，行级权限。

**Demo 流程**：数据源 → DIS/OBS → DataArts → DWS → DLV；点「触发 ETL」看数据流动
**图标**：`rds` `dis` `obs` `dataarts` `dws` `dlv` `bi` `mrs` `dli`
**后端**：`ssh`（真实 ECS 执行命令）

## 三、数据库

**产品组合**：RDS（MySQL/PG）主备 + DCS（Redis）缓存 + DDS（MongoDB）+ 只读副本
**最佳实践**：
1. 主备高可用 + 跨 AZ；
2. 读写分离，只读副本扛查询；
3. Redis 做热点缓存；
4. 开启备份与审计（DBSS）；
5. 连接池 + 慢 SQL 治理。

**Demo 流程**：应用 → ELB → RDS 主备 + DCS 缓存；压测看主备切换
**图标**：`rds` `dcs` `dds` `elb` `ecs`

## 四、AI / 机器学习

**产品组合**：OBS（数据/模型）+ ModelArts（训练/推理）+ FunctionGraph（推理 API）+ APIG
**最佳实践**：
1. 数据/模型放 OBS，版本化；
2. 训练用专属资源池，推理用按需；
3. 模型服务化，APIG 统一入口；
4. 推理结果缓存 + 限流；
5. 监控与成本看板。

**Demo 流程**：数据 → 训练 → 模型 → 推理 API → 应用
**图标**：`obs` `functiongraph` `apig` `ecs`（ModelArts 无图标，用通用框）

## 五、容器 / 微服务

**产品组合**：CCE（K8s）+ ELB + OBS/SWR + LTS + APM
**最佳实践**：
1. 多可用区节点池；
2. 镜像扫描后入库；
3. HPA 弹性伸缩；
4. Service Mesh / Ingress 统一入口；
5. 日志 LTS + 监控。

**Demo 流程**：用户 → ELB → CCE 服务 → 数据库/缓存
**图标**：`cce` `elb` `obs` `lts` `ecs`

## 六、网络

**产品组合**：VPC + 子网 + 安全组 + EIP + NAT + 对等连接
**最佳实践**：
1. 按业务划分子网；
2. 安全组最小权限；
3. 公网入口统一走 ELB/WAF；
4. 跨 VPC 用对等连接；
5. 开启 VPC 流日志。

**Demo 流程**：公网 → EIP → 安全组 → 子网内 ECS
**图标**：`vpc` `elb` `ecs`；EIP/安全组用通用框

## 七、存储 / 备份

**产品组合**：OBS（对象）+ EVS（块）+ CBR（备份）+ SDRS（容灾）
**最佳实践**：
1. 冷热分层，生命周期转归档；
2. 跨区域复制；
3. 定期备份 + 恢复演练；
4. 加密（KMS）。

**Demo 流程**：应用 → OBS/EVS → CBR 备份 → 恢复
**图标**：`obs` `ecs`

## 八、迁移 / 上云

**产品组合**：SMS（主机迁移）+ OMS（对象迁移）+ CDM（数据迁移）+ DRS（数据库迁移）
**最佳实践**：
1. 先评估再迁移；
2. 增量同步 + 割接演练；
3. 迁移后校验一致性。

**Demo 流程**：源端 → 迁移服务 → 目标端
**图标**：`cdm` `ecs` `obs` `rds`

## 九、运维 / 可观测

**产品组合**：CES（监控）+ LTS（日志）+ CTS（审计）+ SMN（告警）
**最佳实践**：
1. 关键指标设告警；
2. 日志集中采集；
3. 审计留痕；
4. 告警分级 + 值班。

**Demo 流程**：资源 → CES/LTS → SMN 告警
**图标**：`lts` `smn` `cts`

---

> 每个领域都能用同一套 manifest + GUI 复现；差异只在「节点/连线/动作/事件」。
> 所有 Demo 都用 `backend: "ssh"` 连真实 ECS 执行命令；`hss` 额外接 HSS 真实检测。
