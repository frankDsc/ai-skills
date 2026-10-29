#!/usr/bin/env python3
"""大数据 Demo：创建真实 ECS（执行节点）+ EIP，产出 state.json / demo_password.txt。"""
import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config
from lib.provision import setup_vm


def main():
    cfg = load_config()
    st = setup_vm(cfg, "bigdata-demo-ecs")
    with open(os.path.join(SKILL_ROOT, "state.json"), "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    with open(os.path.join(SKILL_ROOT, "demo_password.txt"), "w") as f:
        f.write(st["password"] + "\n")
    os.chmod(os.path.join(SKILL_ROOT, "demo_password.txt"), 0o600)
    print("ECS:", st["server_id"])
    print("公网 IP:", st["public_ip"])
    print("下一步：python gui/app.py --manifest examples/bigdata-demo/manifest.json --port 8899")


if __name__ == "__main__":
    main()
