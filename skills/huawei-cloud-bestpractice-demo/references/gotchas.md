# 踩坑记录（Gotchas）

> 这些是实际跑通过程中遇到、且官方文档不显眼的问题。按重要性排序。

## 1. HSS Agent 安装命令参数大小写

`list_agent_install_script` 的 `os_type` 必须是 **`Linux`（首字母大写）**，`os_arch` 用 `x86_64`。

- ❌ `os_type="linux"` → `HSS.0002 Failed to parse the request`
- ✅ `os_type="Linux", os_arch="x86_64"` → 返回 `install_script_list[0].cmd`

## 2. 按需防护的版本参数

`switch_hosts_protect_status`：

- `hss.version.professional`（专业版）在部分区域返回 `HSS.0001 Invalid parameter`
- ✅ 用 `hss.version.enterprise`（企业版）可正常开启
- `charging_mode` 用 **`on_demand`**（不是 `demand`/`packet_cycle`）

## 3. 不要用错接口

- `create_quotas_order` = **包年包月**订购（需要 `period_type/period_num`）；
- `batch_start_protection` = **勒索病毒防护**，不是通用「开启防护」；
- 按需开启防护 = `switch_hosts_protect_status`。

## 4. 危险命令触发规律（实测）

| 命令 | 是否触发 | 事件名 |
|---|---|---|
| 在 `/usr/bin` 新建文件 + `chmod u+s` | ✅ 稳定 | File Privilege Escalation (High) |
| 在 `/tmp` 新建文件 + `chmod u+s` | ❌ 不触发 | — |
| 对同一二进制 `chmod u-s` 再 `u+s` | ❌ 只认第一次 | — |
| 写 `/tmp/*.php` 一句话木马 | ✅ 稳定 | Webshell / Web Shell (High) |
| 连接 `/dev/tcp/8.8.8.8/53` 反弹 | 不稳定 | 取决于是否真实外连 |
| `chmod -R 777 /tmp/xxx` | 不稳定 | — |

## 5. HSS 检出延迟

安全事件从命令执行到出现在 `list_security_events` 中，通常需要 **30–90 秒**。
前端轮询间隔建议 ≤ 5 秒，并给用户「检测中」的明确提示。

## 6. ECS 默认无公网 IP

装 Agent 需要 ECS 能访问外网（HSS 服务端）。两条路：

- 绑定 EIP（本 Skill 采用）；
- 配置 NAT 网关（更复杂）。

## 7. 华为云 APIG 签名 canonical URI

手写 AK/SK 签名时，canonical URI **需要结尾带 `/`**（网关会规范化）。最省事直接用官方 SDK。

## 8. VPC / 子网删除顺序

先删子网，再删 VPC；子网删除后路由器关联是**异步释放**的，VPC 删除失败（`Router contains subnets`）时等几秒重试即可。

## 9. BSS 余额接口权限

`list_customers_balances_detail` 等余额接口可能需要额外 BSS 权限，`Tenant Administrator` 不一定包含。

## 10. 费用与清理

按需资源（ECS/EIP/HSS）关机/释放即停止计费；演示结束务必清理，详见 `pricing.md`。

## 12. 图标必须内联成 SVG `<g>`，不要用 `<image>`

**现象**：用 `<image href="data:image/svg+xml;base64,...">` 嵌 SVG 图标时，Chrome 正常，但部分 WebView（macOS WKWebView / 内嵌浏览器）会「部分图标显示、部分空白」。
**最终修复**：`lib/arch.py` 的 `_icon_group()` 把图标 svg 的 `<defs>` + `<g>` **内联**进主 SVG（重命名 `clipPath` id 防冲突），用 `transform="translate(x,y) scale(s)"` 定位；**不再使用 `<image>`**。
**备用**：`assets/icons_png/`（144×144 PNG）+ `scripts/rasterize_icons.py` 可作兜底。

## 13. 嵌套分组 + 逐段震动

- 分组框的 `children` 可以是另一个 `group`，实现嵌套（`VPC > HSS > ECS`）；`lib/arch.py` 按面积从大到小渲染，外层先画。
- 动画：后端为每个 action 按节点间生成 `flow-<id>-<i>` 分段路径；前端逐段播放红点，**红点到达哪个节点才震动哪个节点**（不要一次性全震）。
- `gui/app.py` 已加 `no-store` 响应头，避免浏览器缓存旧页面。
