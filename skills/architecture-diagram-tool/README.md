# 架构图工具

绘制、审视和优化华为云及其他云厂商架构图。华为云默认红白配色，服务图标保留原色；优先采用清晰的分层布局、正交连线和充分留白。

## 调用

将此文件夹复制到运行环境支持的 Skill 目录。Codex 个人目录通常为 `~/.codex/skills/`。

```text
$architecture-diagram-tool
绘制一个华为云防勒索架构图，使用内置彩色图标和红白配色，方框不重叠、连线不交叉，保留可编辑源文件。
```

入口为 [SKILL.md](SKILL.md)，布局规则在 [references/layout-rules.md](references/layout-rules.md)。`agents/openai.yaml` 为 Codex 界面元数据，其他运行环境可忽略。

## 图标资源

内置 15 个彩色库、12 个旧版线性库；默认使用彩色库。来源为 [huaweicloud-latam/drawio-libraries](https://github.com/huaweicloud-latam/drawio-libraries) `v3.2`，详见 [来源说明](references/huawei-icon-source.md)。图标及品牌权利归原权利人，遵循来源项目和品牌方的使用要求。

## 几何校验

需要 Python 3.9+，无第三方依赖。在此 Skill 目录执行：

```bash
python3 scripts/validate_geometry.py layout.json
```

输入使用 `nodes: [{id, x, y, w, h}]` 与 `edges: [{id, points: [[x, y], ...]}]`。可检测节点面积重叠、正交线段穿框、斜线、零长度线段，以及部分线线交叉或重叠。文字溢出、服务能力、端点相交等仍需结合渲染结果人工审视。

## 兼容性

采用标准 `SKILL.md` 与相对资源路径。已完成本地结构和资源检查；码道等其他客户端尚未实测，具体导入方式以目标环境为准。
