#!/usr/bin/env python3
"""02 安装 HSS Agent：取官方安装命令 + SSH 执行 + 等待上线。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, hss_client, ssh_exec

from huaweicloudsdkhss.v5 import (ListAgentInstallScriptRequest, ListHostStatusRequest)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_state():
    p = os.path.join(BASE, "state.json")
    if not os.path.exists(p):
        sys.exit("缺少 state.json，请先运行 01_setup_env.py")
    return json.load(open(p))


def main():
    cfg = load_config()
    st = load_state()
    cli = hss_client(cfg)

    # 1) 取官方安装命令（os_type 必须 "Linux" 首字母大写）
    r = cli.list_agent_install_script(
        ListAgentInstallScriptRequest(region=cfg["region"], os_type="Linux", os_arch="x86_64"))
    cmd = r.install_script_list[0].cmd
    print("安装命令:", cmd)

    # 2) SSH 执行
    password = open(os.path.join(BASE, "demo_password.txt")).read().strip()
    out = ssh_exec(st["public_ip"], password, "cd /tmp && " + cmd, timeout=300)
    print(out[-1500:])

    # 3) 等待 HSS 主机上线
    host_id = st["server_id"]
    for i in range(18):
        hr = cli.list_host_status(ListHostStatusRequest(limit=50, refresh=True))
        found = None
        for h in (hr.data_list or []):
            if h.host_id == host_id:
                found = h
                break
        if found and getattr(found, "agent_status", None) == "online":
            print("Agent 已上线:", found.host_name)
            return
        print(f"[{i}] 等待 agent 上报…")
        time.sleep(10)
    print("警告：仍未检测到 online，请稍后重试或检查网络。")


if __name__ == "__main__":
    main()
