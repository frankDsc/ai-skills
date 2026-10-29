#!/usr/bin/env python3
"""通用资源创建：安全组 + 按需 ECS + EIP（真实资源）。

所有 Demo 至少需要一台真实 ECS 作为执行节点；本模块提供可复用的创建流程。
"""
import secrets
import string
import sys
import time

from .common import vpc_client, ecs_client, eip_client

from huaweicloudsdkvpc.v2 import (CreateSecurityGroupRequest, CreateSecurityGroupRequestBody,
                                  CreateSecurityGroupOption, CreateSecurityGroupRuleRequest,
                                  CreateSecurityGroupRuleRequestBody, CreateSecurityGroupRuleOption)
from huaweicloudsdkecs.v2 import (CreateServersRequest, CreateServersRequestBody, PostPaidServer,
                                  PostPaidServerNic, PostPaidServerRootVolume,
                                  PostPaidServerSecurityGroup, PostPaidServerExtendParam,
                                  ListServerInterfacesRequest, ShowServerRequest)
from huaweicloudsdkeip.v2 import (CreatePublicipRequest, CreatePublicipRequestBody,
                                  CreatePublicipOption, CreatePublicipBandwidthOption)


def gen_password(n=14):
    alphabet = string.ascii_letters + string.digits + "!@#%"
    return "Hw" + "".join(secrets.choice(alphabet) for _ in range(n)) + "!"


def setup_vm(cfg, name, sg_name=None, flavor=None, image_id=None, disk_gb=None,
             ssh_source_cidr=None):
    """创建安全组 + 按需 ECS + 绑定 EIP，返回 {server_id, public_ip, sg_id, password}。"""
    vpc = vpc_client(cfg)
    ecs = ecs_client(cfg)
    eip = eip_client(cfg)

    sg_name = sg_name or (name + "-sg")
    sg = vpc.create_security_group(CreateSecurityGroupRequest(
        body=CreateSecurityGroupRequestBody(
            security_group=CreateSecurityGroupOption(name=sg_name, vpc_id=cfg["vpc_id"]))))
    sg_id = sg.security_group.id

    vpc.create_security_group_rule(CreateSecurityGroupRuleRequest(
        body=CreateSecurityGroupRuleRequestBody(
            security_group_rule=CreateSecurityGroupRuleOption(
                security_group_id=sg_id, direction="ingress", ethertype="IPv4",
                protocol="tcp", port_range_min=22, port_range_max=22,
                remote_ip_prefix=ssh_source_cidr or cfg.get("ssh_source_cidr", "0.0.0.0/0"),
                description="SSH"))))

    password = gen_password()
    server = PostPaidServer(
        name=name,
        image_ref=image_id or cfg["image_id"],
        flavor_ref=flavor or cfg.get("flavor", "s6.medium.2"),
        availability_zone=cfg.get("availability_zone", cfg["region"] + "a"),
        vpcid=cfg["vpc_id"],
        nics=[PostPaidServerNic(subnet_id=cfg["subnet_id"])],
        root_volume=PostPaidServerRootVolume(volumetype="SSD", size=disk_gb or cfg.get("system_disk_gb", 40)),
        security_groups=[PostPaidServerSecurityGroup(id=sg_id)],
        admin_pass=password,
        extendparam=PostPaidServerExtendParam(charging_mode="postPaid"),
    )
    resp = ecs.create_servers(CreateServersRequest(body=CreateServersRequestBody(server=server)))
    server_id = resp.server_ids[0]

    for _ in range(30):
        s = ecs.show_server(ShowServerRequest(server_id=server_id)).server
        if s.status == "ACTIVE":
            break
        time.sleep(10)

    port = ecs.list_server_interfaces(
        ListServerInterfacesRequest(server_id=server_id)).interface_attachments[0].port_id
    eip_resp = eip.create_publicip(CreatePublicipRequest(body=CreatePublicipRequestBody(
        publicip=CreatePublicipOption(type="5_bgp", ip_version=4, port_id=port),
        bandwidth=CreatePublicipBandwidthOption(
            share_type="PER", size=cfg.get("eip_bandwidth_mbps", 1),
            charge_mode="traffic", name="eip-" + name))))

    return {
        "server_id": server_id,
        "public_ip": eip_resp.publicip.public_ip_address,
        "sg_id": sg_id,
        "password": password,
        "region": cfg["region"],
    }
