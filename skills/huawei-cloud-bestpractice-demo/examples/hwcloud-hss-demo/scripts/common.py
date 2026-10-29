#!/usr/bin/env python3
"""公共模块：配置加载 + 华为云 SDK 客户端。"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit("缺少 config.json：请先 `cp config.example.json config.json` 并填写 ak/sk/project_id/vpc_id/subnet_id")
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    required = ["ak", "sk", "region", "project_id", "vpc_id", "subnet_id"]
    missing = [k for k in required if not cfg.get(k) or str(cfg[k]).startswith("YOUR_")]
    if missing:
        sys.exit(f"config.json 缺少必填项：{missing}")
    return cfg


def basic_cred(cfg):
    from huaweicloudsdkcore.auth.credentials import BasicCredentials
    return BasicCredentials(cfg["ak"], cfg["sk"]).with_project_id(cfg["project_id"])


def global_cred(cfg):
    from huaweicloudsdkcore.auth.credentials import GlobalCredentials
    return GlobalCredentials(cfg["ak"], cfg["sk"])


def ecs_client(cfg):
    from huaweicloudsdkecs.v2 import EcsClient
    return EcsClient.new_builder().with_credentials(basic_cred(cfg)).with_endpoint(
        f"https://ecs.{cfg['region']}.myhuaweicloud.com").build()


def vpc_client(cfg):
    from huaweicloudsdkvpc.v2 import VpcClient
    return VpcClient.new_builder().with_credentials(basic_cred(cfg)).with_endpoint(
        f"https://vpc.{cfg['region']}.myhuaweicloud.com").build()


def eip_client(cfg):
    from huaweicloudsdkeip.v2 import EipClient
    return EipClient.new_builder().with_credentials(basic_cred(cfg)).with_endpoint(
        f"https://vpc.{cfg['region']}.myhuaweicloud.com").build()


def hss_client(cfg):
    from huaweicloudsdkhss.v5 import HssClient
    return HssClient.new_builder().with_credentials(basic_cred(cfg)).with_endpoint(
        f"https://hss.{cfg['region']}.myhuaweicloud.com").build()


def ssh_exec(ip, password, cmd, timeout=60):
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
