#!/usr/bin/env python3
"""01 建环境：安全组 + 按需 ECS + 绑定 EIP。"""
import json
import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, vpc_client, ecs_client, eip_client

from huaweicloudsdkvpc.v2 import (CreateSecurityGroupRequest, CreateSecurityGroupRequestBody,
                                  CreateSecurityGroupOption, CreateSecurityGroupRuleRequest,
                                  CreateSecurityGroupRuleRequestBody, CreateSecurityGroupRuleOption)
from huaweicloudsdkecs.v2 import (CreateServersRequest, CreateServersRequestBody, PostPaidServer,
                                  PostPaidServerNic, PostPaidServerRootVolume,
                                  PostPaidServerSecurityGroup, PostPaidServerExtendParam,
                                  ListServerInterfacesRequest)
from huaweicloudsdkeip.v2 import (CreatePublicipRequest, CreatePublicipRequestBody,
                                  CreatePublicipOption, CreatePublicipBandwidthOption)


def gen_password(n=14):
    alphabet = string.ascii_letters + string.digits + "!@#%"
    return "Hw" + "".join(secrets.choice(alphabet) for _ in range(n)) + "!"


def main():
    cfg = load_config()
    vpc = vpc_client(cfg)
    ecs = ecs_client(cfg)
    eip = eip_client(cfg)

    # 1) 安全组
    sg_name = cfg.get("security_group_name", "hss-demo-sg")
    sg = vpc.create_security_group(CreateSecurityGroupRequest(
        body=CreateSecurityGroupRequestBody(
            security_group=CreateSecurityGroupOption(name=sg_name, vpc_id=cfg["vpc_id"]))))
    sg_id = sg.security_group.id
    print("安全组:", sg_name, sg_id)

    # 2) SSH 规则
    vpc.create_security_group_rule(CreateSecurityGroupRuleRequest(
        body=CreateSecurityGroupRuleRequestBody(
            security_group_rule=CreateSecurityGroupRuleOption(
                security_group_id=sg_id, direction="ingress", ethertype="IPv4",
                protocol="tcp", port_range_min=22, port_range_max=22,
                remote_ip_prefix=cfg.get("ssh_source_cidr", "0.0.0.0/0"),
                description="SSH for demo"))))
    print("SSH 规则已添加")

    # 3) 密码
    password = gen_password()
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "demo_password.txt"), "w") as f:
        f.write(password + "\n")
    print("ECS 密码已写入 demo_password.txt")

    # 4) 按需 ECS
    server = PostPaidServer(
        name=cfg.get("server_name", "hss-demo-ecs"),
        image_ref=cfg["image_id"],
        flavor_ref=cfg.get("flavor", "s6.medium.2"),
        availability_zone=cfg.get("availability_zone", cfg["region"] + "a"),
        vpcid=cfg["vpc_id"],
        nics=[PostPaidServerNic(subnet_id=cfg["subnet_id"])],
        root_volume=PostPaidServerRootVolume(volumetype="SSD", size=cfg.get("system_disk_gb", 40)),
        security_groups=[PostPaidServerSecurityGroup(id=sg_id)],
        admin_pass=password,
        extendparam=PostPaidServerExtendParam(charging_mode="postPaid"),
    )
    resp = ecs.create_servers(CreateServersRequest(body=CreateServersRequestBody(server=server)))
    server_id = resp.server_ids[0]
    print("ECS 创建中:", server_id)

    # 5) 等 ACTIVE 并绑 EIP
    import time
    from huaweicloudsdkecs.v2 import ShowServerRequest
    for _ in range(30):
        s = ecs.show_server(ShowServerRequest(server_id=server_id)).server
        if s.status == "ACTIVE":
            break
        time.sleep(10)
    print("ECS 状态:", s.status)

    port = ecs.list_server_interfaces(ListServerInterfacesRequest(server_id=server_id)).interface_attachments[0].port_id
    eip_resp = eip.create_publicip(CreatePublicipRequest(body=CreatePublicipRequestBody(
        publicip=CreatePublicipOption(type="5_bgp", ip_version=4, port_id=port),
        bandwidth=CreatePublicipBandwidthOption(
            share_type="PER", size=cfg.get("eip_bandwidth_mbps", 1),
            charge_mode="traffic", name="eip-hss-demo"))))
    print("公网 IP:", eip_resp.publicip.public_ip_address)
    state = {"server_id": server_id, "public_ip": eip_resp.publicip.public_ip_address,
             "sg_id": sg_id, "region": cfg["region"]}
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "state.json"), "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print("状态已写入 state.json")
    print("完成。下一步：python scripts/02_install_agent.py")


if __name__ == "__main__":
    main()
