#!/usr/bin/env python3
"""03 开启 HSS 企业版按需防护。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, hss_client

from huaweicloudsdkhss.v5 import (SwitchHostsProtectStatusRequest,
                                  SwitchHostsProtectStatusRequestInfo, ListHostStatusRequest)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    cfg = load_config()
    st = json.load(open(os.path.join(BASE, "state.json")))
    cli = hss_client(cfg)
    host_id = st["server_id"]

    body = SwitchHostsProtectStatusRequestInfo(
        version="hss.version.enterprise",   # 专业版在部分区域无效，用企业版
        charging_mode="on_demand",
        host_id_list=[host_id])
    r = cli.switch_hosts_protect_status(SwitchHostsProtectStatusRequest(body=body))
    print("开启防护 status:", r.status_code)

    import time
    time.sleep(15)
    hr = cli.list_host_status(ListHostStatusRequest(limit=50, refresh=True))
    for h in (hr.data_list or []):
        if h.host_id == host_id:
            print("当前: version=%s protect=%s agent=%s" % (
                getattr(h, "version", None), getattr(h, "protect_status", None),
                getattr(h, "agent_status", None)))


if __name__ == "__main__":
    main()
