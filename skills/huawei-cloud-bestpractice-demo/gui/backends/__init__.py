"""后端选择器：所有 Demo 都连接真实资源。

- `ssh`（默认）：SSH 到真实 ECS 执行动作命令。
- `hss`：SSH 执行 + 查询 HSS 真实安全事件。
"""


def get_backend(manifest):
    name = manifest.get("backend", "ssh")
    if name == "hss":
        from .hss import HssBackend
        return HssBackend(manifest)
    from .ssh import SshBackend
    return SshBackend(manifest)
