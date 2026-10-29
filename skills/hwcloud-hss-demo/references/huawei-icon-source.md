# 华为云官方图标来源

本 Skill `assets/icons/` 下的图标来自华为云官方图标库：

- 仓库：[huaweicloud-latam/drawio-libraries](https://github.com/huaweicloud-latam/drawio-libraries)
- 版本：`v3.2`
- 使用的是 **color 版**（当前官方彩色图标）；`line` 版为旧版单色，仅兼容用。

## 已提取的图标

| 文件 | 服务 | 来源分类 |
|---|---|---|
| `ecs.svg` | Elastic Cloud Server (ECS) | Compute and Containers |
| `hss.svg` | Host Security Service (HSS) | Security and Compliance |
| `iam.svg` | Identity and Access Management (IAM) | Management and Governance |
| `cts.svg` | Cloud Trace Service (CTS) | Management and Governance |
| `vpc.svg` | Virtual Private Cloud (VPC) | Networking |

> **安全组（Security Group）** 在官方库中只有空的分组形状、没有独立图标，因此架构图中用「带标签的通用边界」表示。

## 再提取更多图标

`assets-huawei-cloud-color/*.xml` 是 Draw.io `mxlibrary` 文件，结构为：

```json
{"data":"data:image/svg+xml;base64,<BASE64_SVG>","w":40,"h":40,"title":"<服务名>","aspect":"fixed"}
```

用 `scripts/05_gen_arch.py` 里同样的方式（base64 解码 `data` 字段）即可提取任意服务图标。
