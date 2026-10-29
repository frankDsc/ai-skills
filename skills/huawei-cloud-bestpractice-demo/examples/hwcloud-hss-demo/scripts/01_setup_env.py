#!/usr/bin/env python3
"""HSS Demo：创建真实 ECS + EIP，产出 state.json / demo_password.txt（skill 根目录）。"""
import json
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config
from lib.provision import setup_vm


def main():
    cfg = load_config()
    st = setup_vm(cfg, "hss-demo-ecs")
    with open(os.path.join(SKILL_ROOT, "state.json"), "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    p = os.path.join(SKILL_ROOT, "demo_password.txt")
    with open(p, "w") as f:
        f.write(st["password"] + "\n")
    os.chmod(p, 0o600)
    print("ECS:", st["server_id"])
    print("公网 IP:", st["public_ip"])
    print("下一步：python examples/hwcloud-hss-demo/scripts/02_install_agent.py")


if __name__ == "__main__":
    main()
