"""后端选择器：根据 manifest.backend 返回对应实现。"""


def get_backend(manifest):
    name = manifest.get("backend", "mock")
    if name == "hss":
        from .hss import HssBackend
        return HssBackend(manifest)
    from .mock import MockBackend
    return MockBackend(manifest)
