# HSS 检测能力与触发命令对照

> 基于实测（cn-north-4，HSS 企业版按需）。事件查询接口：`list_security_events(host_id=..., limit=50)`。

## 实测可稳定触发的事件

| 模拟攻击 | 命令（安全版，不会真破坏） | HSS 事件名 | 严重级别 |
|---|---|---|---|
| 文件提权 | `f=/usr/bin/demo_$(date +%s%N); cp /bin/true "$f" && chmod u+s "$f"` | `File Privilege Escalation` | High |
| Webshell | `f=/tmp/shell_$(date +%s%N).php; echo '<?php @eval($_POST[c]);?>' > "$f"` | `Webshell` / `Web Shell` | High |
| 弱口令爆破 | 对 ECS 22 端口尝试多次错误密码 | `Brute-force Attack Attempt` | Low/Medium |

## 不可靠 / 需额外条件

| 模拟攻击 | 说明 |
|---|---|
| 反弹 Shell | 需真实外连成功才可能检出；`/dev/tcp` 连不通时通常不产生事件 |
| 挖矿 | 需真实挖矿进程特征；单纯下载文件不一定检出 |
| 危险命令（改权限） | 依赖 HSS 规则库，不一定触发 |

## 事件字段

`list_security_events` 返回的 `data_list[]` 中常用字段：

- `event_name`：事件名（如 `File Privilege Escalation`）
- `severity`：`High` / `Medium` / `Low`
- `occur_time`：毫秒时间戳
- `host_id`：主机 ID（= ECS 实例 ID）

## 其他相关接口

- 主机状态：`list_host_status(refresh=True)` → `agent_status`（`online` / `not_installed`）、`protect_status`（`opened` / `closed`）、`version`
- 主机漏洞：`list_host_vuls(host_id=...)`
- 基线检查：`list_host_check_rules(...)`
