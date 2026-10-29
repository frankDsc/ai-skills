#!/usr/bin/env python3
"""HSS Demo：取官方安装命令并通过 SSH 装到真实 ECS，等待 Agent 上线。"""
import json
import os
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config, hss_client, ssh_exec
from huaweicloudsdkhss.v5 import ListAgentInstallScriptRequest, ListHostStatusRequest


def main():
    cfg = load_config()
    st = json.load(open(os.path.join(SKILL_ROOT, "state.json"), encoding="utf-8"))
    cli = hss_client(cfg)

    r = cli.list_agent_install_script(
        ListAgentInstallScriptRequest(region=cfg["region"], os_type="Linux", os_arch="x86_64"))
    cmd = r.install_script_list[0].cmd
    print("安装命令:", cmd)

    pw = open(os.path.join(SKILL_ROOT, "demo_password.txt")).read().strip()
    out = ssh_exec(st["public_ip"], pw, "cd /tmp && " + cmd, timeout=300)
    print(out[-1500:])

    for i in range(18):
        hr = cli.list_host_status(ListHostStatusRequest(limit=50, refresh=True))
        for h in (hr.data_list or []):
            if h.host_id == st["server_id"] and getattr(h, "agent_status", None) == "online":
                print("Agent 已上线:", h.host_name)
                return
        print(f"[{i}] 等待 agent 上报…")
        time.sleep(10)
    print("警告：仍未 online，请稍后重试。")


if __name__ == "__main__":
    main()
