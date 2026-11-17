# 费用估算（按需，参考价）

> 价格为参考值，**以 [华为云价格详情页](https://www.huaweicloud.com/price_detail.html) 为准**。

## 1 天 Demo 组合（ECS + EIP + HSS 企业版）

| 资源 | 规格 | 单价（约） | 1 天（24h） |
|---|---|---|---|
| ECS | s6.medium.2（1核2GB） | 0.1–0.2 元/小时 | 2.4–4.8 元 |
| EIP | 1Mbps，按流量 | 0.02 元/小时 + 流量费 | ~0.5 元 |
| HSS | 企业版，按需 | ~0.12 元/小时 | ~2.9 元 |
| **合计** | | | **约 6–8 元/天** |

> 若用 2核4GB 规格，ECS 部分约翻倍。

## 免费 / 极低成本项

| 项 | 费用 |
|---|---|
| IAM、安全组、VPC、CTS（追踪器） | 0 元 |
| KMS 基础版（免费额度内） | 0 元 |
| HSS 基础版 | 0 元 |
| VSS 漏洞扫描（免费额度内） | 0 元 |

## 只支持包年包月、不能按天算的产品

WAF（云模式）、DBSS、DSC、SecMaster、CBH、AAD 高防、CCM —— 具体版本及区域的计费方式需以当前购买页核验，不将此表当作实时资格。

## CFW 专业版按需（2026-11 核验）

CFW 专业版在部分区域支持按需，按实例时长和实际处理流量计费。必须同时核验控制台入口、`ListFirewallList.is_support_postpaid` 和 BSS 询价；报价成功不代表当前项目可购买。不得因按需不可选自动改买月付。

本次已验证中国香港可用，CFW 报价 ¥2.6712/小时 + ¥0.4452/GB；双 2核4GB ECS、40GB 高 IO 盘与 5Mbps 流量型 EIP 合计固定约 ¥4.11912/小时，两小时加处理/出云各 1GB 约 ¥9.73。仅为 2026-11-16 账户报价快照，其他账号、区域和日期需重新询价。代码与实际验收见 [CFW 双机最佳实践](../../../demos/cfw-best-practice/README.md)。

官方说明：[按需开通与区域限制](https://support.huaweicloud.com/usermanual-cfw/cfw_01_0265.html)、[CFW 计费规则](https://support.huaweicloud.com/price-cfw/cfw_03_0005.html)。CFW 需删除实例才停止持续计费，不能以 ECS 关机代替清理。

## 清理提示

- ECS 关机：按需计费关机后仅收少量存储费；
- 释放 ECS / 解绑并删除 EIP / 关闭 HSS 防护 → 完全停止计费。
