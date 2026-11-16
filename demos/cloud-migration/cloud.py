"""Dedicated ECS lifecycle. Credentials and resource IDs stay in a private runtime."""
import csv
import json
import os
from pathlib import Path
import secrets
import time

import paramiko
from huaweicloudsdkcore.auth.credentials import BasicCredentials,GlobalCredentials
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.signer.signer import Signer
from huaweicloudsdkcore.exceptions.exceptions import ClientRequestException
from huaweicloudsdkecs.v2 import (EcsClient,ShowServerRequest,CreateServersRequest,
    CreateServersRequestBody,PostPaidServer,PostPaidServerNic,PostPaidServerRootVolume,
    PostPaidServerSecurityGroup,PostPaidServerExtendParam,ListServerInterfacesRequest)
from huaweicloudsdkecs.v2 import DeleteServersRequest,DeleteServersRequestBody,ServerId
from huaweicloudsdkiam.v3 import IamClient,KeystoneListProjectsRequest
import requests

RUNTIME=Path.home()/'.local/state/cloud-migration-lab'


class Cloud:
    def __init__(self):
        self.runtime=RUNTIME
        self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.runtime.chmod(0o700)
        self.path=self.runtime/'cloud-state.json'
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {
            'demo_id':'migration-lab-'+time.strftime('%Y%m%d')+'-'+secrets.token_hex(3),
            'region':'cn-north-4','resources':{},'journal':[]}
        self.plan=json.loads((self.runtime/'provision-plan.json').read_text())
        path=Path(os.environ.get('HWC_CREDENTIALS_CSV',str(Path.home()/'Downloads/credentials.csv')))
        with path.open(encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        if len(rows)!=1:raise ValueError('凭证 CSV 必须恰好一行')
        self.ak,self.sk=(rows[0].get(k,'').strip() for k in ('Access Key Id','Secret Access Key'))
        if not self.ak or not self.sk:raise ValueError('缺少华为云凭证')
        self.pid=self.plan['project_id']
        self.credential=BasicCredentials(self.ak,self.sk).with_project_id(self.pid)
        self.ecs=EcsClient.new_builder().with_credentials(self.credential).with_endpoint('https://ecs.cn-north-4.myhuaweicloud.com').build()

    def save(self):
        temp=self.path.with_suffix('.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:json.dump(self.state,f,ensure_ascii=False,indent=2)
        temp.replace(self.path)

    def record(self,key,value):
        self.state['resources'][key]=value
        self.save()

    def api(self,service,path,method='GET',body=None,allow_missing=False):
        host=f'{service}.cn-north-4.myhuaweicloud.com'
        req=SdkRequest(method=method,schema='https',host=host,resource_path=path,
                       query_params=[],
                       header_params={'Content-Type':'application/json','X-Project-Id':self.pid},
                       body=json.dumps(body) if body is not None else '')
        Signer(self.credential).sign(req)
        response=requests.request(method,req.url,headers=req.header_params,data=req.body,timeout=(10,45))
        if response.status_code==404 and allow_missing:return None
        if response.status_code>=400:
            raise RuntimeError(f'{service} API 返回 {response.status_code}，请检查云端状态。')
        return response.json() if response.content else {}

    def provision(self,ssh_cidr):
        if self.state.get('released'):raise ValueError('本轮环境已释放，不能自动重新购买')
        import ipaddress
        network=ipaddress.ip_network(ssh_cidr)
        if network.version!=4 or network.prefixlen!=32:raise ValueError('SSH 仅允许单一 IPv4 /32')
        p,res,name=self.plan,self.state['resources'],self.state['demo_id']
        self.save()
        if not res.get('vpc_id'):
            v=self.api('vpc',f'/v1/{self.pid}/vpcs','POST',{'vpc':{'name':name,'cidr':'10.78.0.0/16','description':'Synthetic migration test '+name}})['vpc']
            self.record('vpc_id',v['id'])
        if not res.get('subnet_id'):
            s=self.api('vpc',f'/v1/{self.pid}/subnets','POST',{'subnet':{'name':name+'-subnet','vpc_id':res['vpc_id'],
                'cidr':'10.78.1.0/24','gateway_ip':'10.78.1.1','dhcp_enable':True,
                'primary_dns':'100.125.1.250','secondary_dns':'100.125.129.250'}})['subnet']
            self.record('subnet_id',s['id'])
        if not res.get('sg_id'):
            sg=self.api('vpc',f'/v1/{self.pid}/security-groups','POST',{'security_group':{'name':name+'-sg','vpc_id':res['vpc_id'],'description':'SSH operator /32 only'}})['security_group']
            self.record('sg_id',sg['id'])
        if not res.get('ssh_rule_id'):
            rule=self.api('vpc',f'/v1/{self.pid}/security-group-rules','POST',{'security_group_rule':{
                'security_group_id':res['sg_id'],'direction':'ingress','ethertype':'IPv4','protocol':'tcp',
                'port_range_min':22,'port_range_max':22,'remote_ip_prefix':ssh_cidr}})['security_group_rule']
            self.record('ssh_rule_id',rule['id'])
            self.record('ssh_cidr',ssh_cidr)
        if not res.get('server_id'):
            password='Hw7!'+secrets.token_urlsafe(12)+'8a'
            assert 8<=len(password)<=26
            self.record('password',password)
            response=self.ecs.create_servers(CreateServersRequest(body=CreateServersRequestBody(server=PostPaidServer(
                name=name,image_ref=p['image_id'],flavor_ref=p['flavor'],availability_zone=p['availability_zone'],
                vpcid=res['vpc_id'],nics=[PostPaidServerNic(subnet_id=res['subnet_id'])],
                root_volume=PostPaidServerRootVolume(volumetype='SAS',size=40),
                security_groups=[PostPaidServerSecurityGroup(id=res['sg_id'])],admin_pass=res['password'],
                extendparam=PostPaidServerExtendParam(charging_mode='postPaid')))))
            self.record('server_id',response.server_ids[0])
            self.record('created_at',time.time())
        return self.status()

    def status(self):
        r=self.state['resources']
        try:
            server=self.ecs.show_server(ShowServerRequest(server_id=r['server_id'])).server if r.get('server_id') else None
        except ClientRequestException as exc:
            if exc.status_code==404 and time.time()-r.get('created_at',time.time())<600:
                server=None
            else:raise
        return {'demo_id':self.state['demo_id'],'ecs_status':server.status if server else ('BUILD' if r.get('server_id') else '未创建'),
                'region':'cn-north-4','flavor':self.plan['flavor'],'public_ip':r.get('public_ip'),
                'server_id':r.get('server_id')}

    def bind_eip(self):
        r=self.state['resources']
        if self.status()['ecs_status']!='ACTIVE':raise ValueError('ECS 尚未运行')
        server=self.ecs.show_server(ShowServerRequest(server_id=r['server_id'])).server.to_dict()
        roots=[v for v in server.get('os_extended_volumesvolumes_attached',[]) if str(v.get('boot_index'))=='0']
        if len(roots)==1:self.record('root_volume_id',roots[0]['id'])
        if not r.get('eip_id'):
            port=self.ecs.list_server_interfaces(ListServerInterfacesRequest(server_id=r['server_id'])).interface_attachments[0].port_id
            self.record('port_id',port)
            eip=self.api('vpc',f'/v1/{self.pid}/publicips','POST',{'publicip':{'type':'5_bgp','ip_version':4},
                'bandwidth':{'name':self.state['demo_id']+'-bw','share_type':'PER','size':5,'charge_mode':'traffic'}})['publicip']
            self.record('eip_id',eip['id'])
            self.record('public_ip',eip['public_ip_address'])
        self.api('vpc',f'/v1/{self.pid}/publicips/{r["eip_id"]}','PUT',{'publicip':{'port_id':r['port_id']}})
        return self.status()

    def ssh(self,first_connection=False):
        r=self.state['resources']
        actual=self.ecs.show_server(ShowServerRequest(server_id=r['server_id'])).server
        if actual.name!=self.state['demo_id']:raise ValueError('实例归属校验失败')
        c=paramiko.SSHClient()
        known=self.runtime/'known_hosts'
        if known.exists():c.load_host_keys(str(known))
        # TOFU is permitted only during explicit first provisioning of this new, API-verified instance.
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy() if first_connection else paramiko.RejectPolicy())
        c.connect(r['public_ip'],username='root',password=r['password'],timeout=15,auth_timeout=15,
                  allow_agent=False,look_for_keys=False)
        if first_connection:
            c.save_host_keys(str(known));known.chmod(0o600)
        return c

    def execute_engine(self,action):
        c=self.ssh()
        try:
            inp,out,err=c.exec_command(f'python3 - --root /root/.local/state/cloud-migration-lab --action {action}',timeout=90)
            inp.write((Path(__file__).parent/'engine.py').read_text());inp.channel.shutdown_write()
            payload=out.read().decode();status=out.channel.recv_exit_status()
            if status:raise RuntimeError('ECS 演练引擎执行失败')
            return json.loads(payload)
        finally:c.close()

    def release(self,confirmation):
        if confirmation!=self.state['demo_id']:raise ValueError('必须确认完整 Demo ID')
        runtime=getattr(self,'runtime',None)
        if runtime and (runtime/'sms-state.json').exists():
            sms_state=json.loads((runtime/'sms-state.json').read_text())
            if not sms_state.get('released'):
                from sms_lab import SmsLab
                SmsLab().release(confirmation)
        r=self.state['resources'];name=self.state['demo_id']
        def remove(*keys):
            for key in keys:r.pop(key,None)
            self.save()
        if r.get('server_id'):
            sid=r['server_id']
            try:server=self.ecs.show_server(ShowServerRequest(server_id=sid)).server
            except ClientRequestException as exc:
                if exc.status_code!=404:raise
                server=None
            if server:
                if server.name!=name:raise ValueError('拒绝删除：ECS 名称与本轮 Demo 不匹配')
                if any(v.id!=r.get('root_volume_id') for v in server.os_extended_volumesvolumes_attached):
                    raise ValueError('拒绝删除：源 ECS 挂载了本轮未记录的磁盘')
                self.ecs.delete_servers(DeleteServersRequest(body=DeleteServersRequestBody(
                    servers=[ServerId(id=sid)],delete_publicip=False,delete_volume=True)))
                for _ in range(60):
                    try:self.ecs.show_server(ShowServerRequest(server_id=sid))
                    except ClientRequestException as exc:
                        if exc.status_code==404:break
                        raise
                    time.sleep(2)
                else:raise TimeoutError('等待 ECS 删除超时，已保留资源 ID')
            remove('server_id','password')
        if r.get('root_volume_id'):
            path=f'/v2/{self.pid}/volumes/{r["root_volume_id"]}'
            for _ in range(30):
                volume=self.api('evs',path,allow_missing=True)
                if volume is None:break
                status=volume['volume']['status']
                if status=='available':self.api('evs',path,'DELETE',allow_missing=True)
                elif status!='deleting':raise ValueError('系统盘仍被占用，保留 ID 等待人工核查')
                time.sleep(2)
            else:raise TimeoutError('系统盘尚未删除，保留 ID 供重试')
            remove('root_volume_id')
        if r.get('eip_id'):
            path=f'/v1/{self.pid}/publicips/{r["eip_id"]}'
            actual=self.api('vpc',path,allow_missing=True)
            if actual:
                ip=actual['publicip']
                if ip.get('public_ip_address')!=r.get('public_ip') or ip.get('port_id') not in (None,'',r.get('port_id')):
                    raise ValueError('拒绝删除：EIP 归属或绑定关系已改变')
                self.api('vpc',path,'DELETE',allow_missing=True)
            remove('eip_id','public_ip','port_id')
        for key,plural,singular,suffix in [('sg_id','security-groups','security_group','-sg'),
                                           ('subnet_id','subnets','subnet','-subnet'),
                                           ('vpc_id','vpcs','vpc','')]:
            if not r.get(key):continue
            path=f'/v1/{self.pid}/{plural}/{r[key]}'
            actual=self.api('vpc',path,allow_missing=True)
            if actual:
                if actual[singular]['name']!=name+suffix:raise ValueError('拒绝删除：网络资源名称不属于本轮 Demo')
                self.api('vpc',path,'DELETE',allow_missing=True)
            remove(key)
        remove('ssh_rule_id','ssh_cidr')
        self.state.update(released=True,released_at=time.time());self.save()
        return {'released':True,'demo_id':name}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['status','provision','bind-eip','pin-host','release'])
    parser.add_argument('--ssh-cidr')
    parser.add_argument('--confirm')
    args=parser.parse_args();cloud=Cloud()
    if args.action=='provision':result=cloud.provision(args.ssh_cidr)
    elif args.action=='bind-eip':result=cloud.bind_eip()
    elif args.action=='pin-host':
        c=cloud.ssh(first_connection=True);c.close();result={'host_key_pinned':True}
    elif args.action=='release':result=cloud.release(args.confirm)
    else:result=cloud.status()
    print(json.dumps(result,ensure_ascii=False))
