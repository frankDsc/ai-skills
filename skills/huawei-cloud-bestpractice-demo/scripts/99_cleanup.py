#!/usr/bin/env python3
"""99 清理：删除 Demo 创建的真实资源（ECS + EIP + 安全组），停止计费。

依赖 state.json（server_id / public_ip / sg_id）。
"""
import json
import os
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_ROOT)

from lib.common import load_config, ecs_client, eip_client, vpc_client
from huaweicloudsdkecs.v2 import (DeleteServersRequest, DeleteServersRequestBody, ServerId,
                                  ListServersDetailsRequest)
from huaweicloudsdkeip.v2 import ListPublicipsRequest, DeletePublicipRequest
from huaweicloudsdkvpc.v2 import ListSecurityGroupsRequest, DeleteSecurityGroupRequest


def main():
    cfg = load_config()
    st_path = os.path.join(SKILL_ROOT, "state.json")
    st = json.load(open(st_path, encoding="utf-8")) if os.path.exists(st_path) else {}
    ecs = ecs_client(cfg)
    eip = eip_client(cfg)
    vpc = vpc_client(cfg)

    sid = st.get("server_id")
    sg_name = "hss-demo-sg"

    # 1) 删除 ECS（连带公网 IP + 系统盘）
    if sid:
        print("删除 ECS:", sid)
        try:
            ecs.delete_servers(DeleteServersRequest(body=DeleteServersRequestBody(
                delete_publicip=True, delete_volume=True, servers=[ServerId(id=sid)])))
        except Exception as e:
            print("  ECS 删除报错（可能已删）:", str(e)[:150])
        for i in range(30):
            left = [x for x in (ecs.list_servers_details(ListServersDetailsRequest()).servers or [])
                    if x.id == sid]
            if not left:
                print("  ECS 已删除")
                break
            time.sleep(5)

    # 2) 释放残留 EIP
    for e in (eip.list_publicips(ListPublicipsRequest()).publicips or []):
        print("释放 EIP:", e.public_ip_address)
        try:
            eip.delete_publicip(DeletePublicipRequest(publicip_id=e.id))
        except Exception as ex:
            print("  EIP 删除报错:", str(ex)[:150])

    # 3) 删除自建安全组
    time.sleep(3)
    for g in (vpc.list_security_groups(ListSecurityGroupsRequest()).security_groups or []):
        if g.name == sg_name:
            print("删除安全组:", g.name)
            try:
                vpc.delete_security_group(DeleteSecurityGroupRequest(security_group_id=g.id))
            except Exception as ex:
                print("  安全组删除报错:", str(ex)[:150])

    print("清理完成。请到控制台确认 ECS/EIP 已释放。")


if __name__ == "__main__":
    main()
