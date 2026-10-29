#!/usr/bin/env python3
"""HSS Demo：开启企业版按需防护。"""
import json
import os
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config, hss_client
from huaweicloudsdkhss.v5 import (SwitchHostsProtectStatusRequest,
                                  SwitchHostsProtectStatusRequestInfo, ListHostStatusRequest)


def main():
    cfg = load_config()
    st = json.load(open(os.path.join(SKILL_ROOT, "state.json"), encoding="utf-8"))
    cli = hss_client(cfg)
    body = SwitchHostsProtectStatusRequestInfo(
        version="hss.version.enterprise", charging_mode="on_demand",
        host_id_list=[st["server_id"]])
    r = cli.switch_hosts_protect_status(SwitchHostsProtectStatusRequest(body=body))
    print("开启防护 status:", r.status_code)
    time.sleep(15)
    hr = cli.list_host_status(ListHostStatusRequest(limit=50, refresh=True))
    for h in (hr.data_list or []):
        if h.host_id == st["server_id"]:
            print("当前: version=%s protect=%s agent=%s" % (
                getattr(h, "version", None), getattr(h, "protect_status", None),
                getattr(h, "agent_status", None)))


if __name__ == "__main__":
    main()
