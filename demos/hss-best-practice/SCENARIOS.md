# 十种 HSS 演练场景与攻击链路

这些脚本是根据华为云官方检测能力设计的受控演练样式，不是对官方“保证检出测试脚本”的转录。主机版本、策略开关、扫描范围、规则和上报延迟都会影响结果；正常的账号或计划任务变化可能不会告警。

当前只执行在本 Demo 创建且通过归属校验的 Ubuntu ECS 上。浏览器不能指定目标 IP 或传入命令。工具类场景的网络目标固定为 `127.0.0.1`。

| ID | 演示样式 | 对应 HSS 能力 | 限定与条件 |
| --- | --- | --- | --- |
| `suid` | SUID 文件提权 | 文件提权 / HIPS | true 的一次性副本，不生成高权限 Shell |
| `sgid` | SGID 文件提权 | 文件提权 / HIPS | 独立副本，仅切换组权限位 |
| `shell_copy` | 异常 Shell 副本 | 异常 Shell | 私有目录，固定 printf 后退出；需相应策略 |
| `webshell` | Webshell 特征文件 | Webshell / 恶意文件 | 样本不提供 HTTP、不解释执行；需覆盖扫描目录 |
| `account` | 测试账号变更 | 账号异常 / HIPS | 密码锁定、nologin、无 home、非管理员；良性变更可能不告警 |
| `cron` | 计划任务观测 | Crontab 可疑任务 | 仅 true，设置不存在的日历日期，不实际调度 |
| `port_scan` | 本机端口探测 | 高危命令 / 端口扫描 | nmap 回环 8 个固定端口，限速限时；回环可能被扫描规则排除 |
| `tcpdump` | 回环流量采集 | 高危命令 | 只采专用 UDP 测试端口，最多 1 包，3 秒超时 |
| `strace` | 测试进程跟踪 | 高危命令 | 只跟踪新启动的 true，不附加系统或凭据进程 |
| `netcat` | 回环端口连接 | 高危命令 | 仅测试字符串，不带 Shell、不建立外部回连 |

## 演示步骤

1. 在场景库点击卡片，或在架构图上方选择场景。
2. 工具类场景首次运行前，点击“准备工具依赖”，会在专用主机安装固定的 nmap、tcpdump、strace、netcat-openbsd 包。
3. 点击“开始选定场景”。红色光点沿授权演练端 → 安全组入口 → ECS 逐段移动，节点在到达时响应。
4. 主机执行完后，进入等待检测阶段。查询失败或动作异常有单独状态，不显示为检出或阻断成功。
5. 只有 HSS 返回与当前主机、场景类型、开始时间和新事件 ID 匹配的告警，才播放绿色 ECS → HSS → 告警 → 证据链路。
6. “重播链路”只重播当前已有状态，不再次执行攻击。“暂停动画”不暂停后端任务或告警查询。可切换慢速、标准、快速。
7. 点击“清理演练产物”撤销 Demo 权限文件、样本、测试账号及 cron 项；再按需要标记本次匹配告警已处理。

关联方式是同主机、同时间窗口和事件类型匹配，并排除执行前已存在的事件 ID；兼容 HSS 事件时间的整秒精度。不是对告警根因的绝对证明。如果在同一主机同时开展其他工作，仍需检查云端告警详情。不要连续切换场景后把上一场景延迟上报的事件作为新场景证据；现场演示建议一次执行、等待结果后再切换。

## 本次实测与演示顺序

2026-10-30 北京四专用 Ubuntu ECS、HSS 企业版：十种动作逐项真实执行，退出码均为 0。SGID、异常 Shell 副本、Webshell、回环 nmap 分别观察到 `File Privilege Escalation`、`Shell Change`、`Webshell` / `Web Shell`、`Suspicious scan`。SUID 在早先单场景验证中已观察到文件提权告警，本次批量重复时没有新的匹配事件。账号、cron、tcpdump、strace、nc 在本次观察窗口内未确认匹配告警；不能展示为检出成功。

现场建议先选 Webshell、异常 Shell、SGID、端口探测，再展示其余场景的策略条件。重复相同行为可能被 HSS 合并告警或抑制重复上报，历史告警不会被动画当作本次新检出。绿色链路已用第二次独立 Webshell 演练产生的新云端事件验证。

## CLI

```bash
.venv/bin/python app.py --action prepare_scenarios
.venv/bin/python app.py --action exercise --scenario strace
```

CLI 与 Web 服务不要同时执行写操作。演练依赖、运行记录、样本与凭证不进入 GitHub；源码里的样本生成逻辑可审查。

## 官方依据

- [护网或重保：及时处理告警](https://support.huaweicloud.com/bestpractice-hss2.0/hss_06_0040.html)：高危命令、提权、恶意软件等处置思路。
- [主机安全告警事件概述](https://support.huaweicloud.com/usermanual-hss2.0/hss_01_0277.html)：异常 Shell、Webshell、账号、计划任务等检测含义。
- [查询安全告警事件 API](https://support.huaweicloud.com/api-hss2.0/ListSecurityEvents.html)：告警类型及事件分类映射。
- [关联告警事件 API](https://support.huaweicloud.com/api-hss2.0/ListRelatedEvents.html)：`6002` 端口扫描、`6003` 主机扫描与 `hips_0011` 可疑扫描的分类；回环 nmap 实测返回后者。

反弹 Shell 和勒索软件也属于 HSS 能力，但此演示没有提供外部回连、真实勒索加密或真实恶意软件投放。
