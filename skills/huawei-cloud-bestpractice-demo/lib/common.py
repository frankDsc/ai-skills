#!/usr/bin/env python3
"""配置加载：华为云凭证 + 通用参数。"""
import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_ROOT, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit("缺少 config.json：请先 `cp config.example.json config.json` 并填写 ak/sk/project_id/vpc_id/subnet_id")
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    return cfg


def basic_cred(cfg):
    from huaweicloudsdkcore.auth.credentials import BasicCredentials
    return BasicCredentials(cfg["ak"], cfg["sk"]).with_project_id(cfg["project_id"])


def global_cred(cfg):
    from huaweicloudsdkcore.auth.credentials import GlobalCredentials
    return GlobalCredentials(cfg["ak"], cfg["sk"])


def _client(cls, cfg, service, region=None):
    return cls.new_builder().with_credentials(basic_cred(cfg)).with_endpoint(
        f"https://{service}.{region or cfg['region']}.myhuaweicloud.com").build()


def ecs_client(cfg):
    from huaweicloudsdkecs.v2 import EcsClient
    return _client(EcsClient, cfg, "ecs")


def vpc_client(cfg):
    from huaweicloudsdkvpc.v2 import VpcClient
    return _client(VpcClient, cfg, "vpc")


def eip_client(cfg):
    from huaweicloudsdkeip.v2 import EipClient
    return _client(EipClient, cfg, "vpc")


def hss_client(cfg):
    from huaweicloudsdkhss.v5 import HssClient
    return _client(HssClient, cfg, "hss")


def ssh_exec(ip, password, cmd, timeout=60):
    """SSH 到真实 VM 执行命令，返回 stdout（或 stderr）。"""
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username="root", password=password, timeout=15,
              allow_agent=False, look_for_keys=False)
    try:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        return (o.read().decode("utf-8", "replace").strip()
                or e.read().decode("utf-8", "replace").strip())
    finally:
        c.close()
