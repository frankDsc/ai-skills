# 华为云服务目录（选型参考）

> 图标名 = `assets/icons/<name>.svg` 的文件名。表中「图标」列可直接填进 manifest 的 `node.icon`。

## 计算

| 服务 | 图标 | 说明 |
|---|---|---|
| 弹性云服务器 ECS | `ecs` | 通用虚拟机 |
| 云容器引擎 CCE | `cce` | Kubernetes 托管 |
| 函数工作流 FunctionGraph | `functiongraph` | Serverless |
| 弹性负载均衡 ELB | `elb` | 四层/七层负载 |

## 存储

| 服务 | 图标 | 说明 |
|---|---|---|
| 对象存储 OBS | `obs` | 数据湖 / 静态资源 |
| 云硬盘 EVS | — | 块存储（无独立图标，用 `ecs` 或通用） |

## 数据库

| 服务 | 图标 | 说明 |
|---|---|---|
| 关系型数据库 RDS | `rds` | MySQL/PostgreSQL/SQLServer |
| 文档数据库 DDS | `dds` | MongoDB 兼容 |
| 分布式缓存 DCS | `dcs` | Redis |
| 数据仓库 DWS | `dws` | GaussDB(DWS) |
| 数据湖探索 DLI | `dli` | Serverless SQL/Spark |
| 数据接入 DIS | `dis` | 流式数据接入 |
| MapReduce 服务 MRS | `mrs` | 大数据集群 |
| 云搜索服务 CSS | `css` | Elasticsearch |

## 大数据 / 数据分析

| 服务 | 图标 | 说明 |
|---|---|---|
| DataArts Studio | `dataarts` | 数据集成 / 开发 / 调度 / 治理 |
| 数据湖可视化 DLV | `dlv` | 大屏 / 报表 |
| DataArts Insight（BI） | `bi` | 自助 BI |
| 云数据迁移 CDM | `cdm` | 批量数据搬迁 |

## 网络

| 服务 | 图标 | 说明 |
|---|---|---|
| 虚拟私有云 VPC | `vpc` | 网络隔离 |
| 弹性公网 IP EIP | — | 公网访问（用通用边界表示） |
| 安全组 | — | 实例级防火墙（用通用边界表示） |

## 安全

| 服务 | 图标 | 说明 |
|---|---|---|
| 企业主机安全 HSS | `hss` | 主机/容器安全 |
| 统一身份认证 IAM | `iam` | 身份与权限 |
| 云审计 CTS | `cts` | 操作审计 |
| 日志服务 LTS | `lts` | 日志采集 |
| 消息通知 SMN | `smn` | 告警通知 |
| API 网关 APIG | `apig` | API 托管 |

## 没有独立图标的服务

官方图标库未收录的（如 EVS、EIP、安全组、部分 AI 服务），按 Skill 规范用**带标签的通用边界**表示：

```json
{"id": "boundary", "label": "公网 EIP + 安全组", "sub": "SSH 白名单", "icon": "", "col": 1, "row": 1}
```

`icon` 留空时架构图只画框和文字，不画图标。

## 再补充图标

官方图标库（`huaweicloud-latam/drawio-libraries` v3.2 color 版）的 XML 里还有大量服务图标。
提取方式：解析 `mxlibrary` 的 JSON，按 `title` 找到条目，base64 解码 `data` 字段写成 `.svg`（见 `references/huawei-icon-source.md`）。
