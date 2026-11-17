"""Scoped real CFW lab. All identifiers/secrets live outside the repository."""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import secrets
import shlex
import time
import uuid

import requests
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.signer.signer import Signer
from huaweicloudsdkcfw.v1 import (CfwClient, CreateFirewallRequest, CreateFirewallReq,
    CreateFirewallReqFlavor, CreateFirewallReqChargeInfo, CreateFirewallReqTags,
    ListFirewallListRequest, QueryFireWallInstanceDto, ListJobRequest, DeleteFirewallRequest)
from huaweicloudsdkcore.exceptions.exceptions import ClientRequestException
from huaweicloudsdkecs.v2 import (EcsClient, ShowServerRequest, CreateServersRequest,
    CreateServersRequestBody, PostPaidServer, PostPaidServerNic, PostPaidServerRootVolume,
    PostPaidServerSecurityGroup, PostPaidServerExtendParam, ListServerInterfacesRequest,
    DeleteServersRequest, DeleteServersRequestBody, ServerId)

RUNTIME = Path.home() / '.local/state/cfw-best-practice-lab'


def save(path, value):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def owned_firewall(record, name):
    return (record.get('fw_instance_name') == name or record.get('name') == name) and record.get('charge_mode') == 1


def matches_deny(run, record):
    """Unique rule, five-tuple and request time window must all match."""
    if record.get('rule_id') != run.get('deny_rule_id') or str(record.get('action')).lower() not in ('deny', '1'):
        return False
    protocol = str(record.get('protocol', '')).upper()
    if protocol not in ('TCP', '6'): return False
    try:
        import ipaddress
        def plain(value):
            return str(ipaddress.ip_address(str(value).split('(',1)[0].strip()))
        hit = int(record['hit_time'])
        if hit < 10**12: hit *= 1000
        for sample in run.get('measurements', {}).get('deny', []):
            if (plain(sample['src_ip']) == plain(record.get('src_ip')) and plain(sample['dst_ip']) == plain(record.get('dst_ip'))
                and int(sample['src_port']) == int(record['src_port']) and int(sample['dst_port']) == int(record['dst_port'])
                and sample['started_at']-5000 <= hit <= sample['finished_at']+5000):
                return True
    except (ValueError, TypeError, KeyError):
        return False
    return False


class Lab:
    def __init__(self):
        self.runtime = RUNTIME
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runtime.chmod(0o700)
        self.path = self.runtime / 'live-state.json'
        self.plan = json.loads((self.runtime / 'hongkong-plan.json').read_text())
        self.region, self.pid = self.plan['region'], self.plan['project_id']
        with Path(os.environ.get('HWC_CREDENTIALS_CSV', str(Path.home() / 'Downloads/credentials.csv'))).open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            raise ValueError('凭证文件必须恰好一行')
        self.ak, self.sk = (rows[0][k].strip() for k in ('Access Key Id', 'Secret Access Key'))
        self.cred = BasicCredentials(self.ak, self.sk).with_project_id(self.pid)
        config = HttpConfig.get_default_config(); config.timeout = (10, 25)
        self.cfw = CfwClient.new_builder().with_credentials(self.cred).with_http_config(config).with_endpoint(f'https://cfw.{self.region}.myhuaweicloud.com').build()
        self.ecs = EcsClient.new_builder().with_credentials(self.cred).with_http_config(config).with_endpoint(f'https://ecs.{self.region}.myhuaweicloud.com').build()
        existing = self.path.exists()
        self.state = json.loads(self.path.read_text()) if existing else {
            'demo_id': 'cfw-lab-' + time.strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:6],
            'region': self.region, 'resources': {}, 'journal': [], 'checks': {}, 'runs': [], 'released': False,
        }
        if self.state['region'] != self.region:
            raise ValueError('区域不匹配')
        if not existing:
            self.write()

    def write(self):
        save(self.path, self.state)

    def record(self, message, detail=''):
        self.state['journal'].insert(0, {'time': int(time.time()*1000), 'message': message, 'detail': detail})
        self.state['journal'] = self.state['journal'][:100]
        self.write()

    def remember(self, key, value):
        self.state['resources'][key] = value
        self.write()

    def api(self, service, path, method='GET', body=None, query=None, allow_missing=False):
        req = SdkRequest(method=method, schema='https', host=f'{service}.{self.region}.myhuaweicloud.com',
                         resource_path=path, query_params=list((query or {}).items()),
                         header_params={'Content-Type': 'application/json', 'X-Project-Id': self.pid},
                         body=json.dumps(body) if body is not None else '')
        Signer(self.cred).sign(req)
        response = requests.request(method, req.url, headers=req.header_params, data=req.body, timeout=(10, 35))
        if response.status_code == 404 and allow_missing:
            return None
        if response.status_code >= 400:
            # No signed headers/URLs or raw response bodies enter the frontend.
            try:
                d = response.json(); d = d.get('error', d)
                code = d.get('code') or d.get('error_code') or 'UNKNOWN'
                message = d.get('message') or d.get('error_msg') or ''
            except (ValueError, AttributeError):
                code, message = 'UNKNOWN', ''
            raise RuntimeError(f'{service} API {response.status_code} {code}: {str(message)[:180]}')
        return response.json() if response.content else {}

    def firewalls(self):
        d = self.cfw.list_firewall_list(ListFirewallListRequest(body=QueryFireWallInstanceDto(limit=100, offset=0))).to_dict()
        return d, (d.get('data') or {}).get('records') or []

    def firewall(self):
        _, records = self.firewalls()
        known = self.state['resources'].get('firewall_id')
        candidates = [r for r in records if (r.get('fw_instance_id') == known if known else owned_firewall(r, self.state['demo_id']))]
        if len(candidates) > 1:
            raise ValueError('发现多个同名资源，停止自动处理')
        if not candidates:
            return None
        record = candidates[0]
        if not owned_firewall(record, self.state['demo_id']):
            raise ValueError('CFW 归属或按需计费校验失败')
        if not known:
            self.remember('firewall_id', record['fw_instance_id'])
        return record

    def open_cfw(self):
        if self.state.get('released'):
            raise ValueError('本轮已释放，不允许重新创建')
        if self.plan['two_hour_estimate_cny'] > 10:
            raise ValueError('实时配置报价超出已批准预算')
        d, _ = self.firewalls()
        if d.get('is_support_postpaid') is not True:
            raise ValueError('当前区域不支持按需，未创建')
        actual = self.firewall()
        if actual:
            return {'status': actual.get('status'), 'created': False}
        if self.state.get('cfw_create_attempted'):
            raise ValueError('已有创建请求；先核对异步作业，禁止重复采购')
        self.state.update(cfw_create_attempted=True, started_at=int(time.time()*1000), cleanup_due_at=int((time.time()+7200)*1000))
        self.write()
        result = self.cfw.create_firewall(CreateFirewallRequest(body=CreateFirewallReq(
            name=self.state['demo_id'], enterprise_project_id='0',
            tags=[CreateFirewallReqTags(key='demo', value=self.state['demo_id'])],
            flavor=CreateFirewallReqFlavor(version='Professional'),
            charge_info=CreateFirewallReqChargeInfo(charge_mode='postPaid', is_auto_renew=False, is_auto_pay=False)))).to_dict()
        self.state['cfw_create_result'] = result
        self.record('已提交 CFW 专业版按需开通', '仅 postPaid，无自动续费；等待云端实例创建成功')
        return {'submitted': True, 'job_id': result.get('job_id'), 'cleanup_due_at': self.state['cleanup_due_at']}

    def status(self):
        actual = self.firewall()
        if self.state.get('cfw_create_result', {}).get('job_id') and not actual:
            job = self.cfw.list_job(ListJobRequest(job_id=self.state['cfw_create_result']['job_id'])).to_dict()
            self.state['last_create_job'] = job; self.write()
        return {'demo_id': self.state['demo_id'], 'region': self.region, 'firewall': actual,
                'cleanup_due_at': self.state.get('cleanup_due_at'),
                'resources': {k: ({a:b for a,b in v.items() if a not in ('password','tls_token')} if isinstance(v,dict) else v) for k,v in self.state['resources'].items()},
                'released': self.state['released'], 'job': self.state.get('last_create_job')}

    def guard_active(self):
        if self.state.get('released') or time.time()*1000 >= self.state.get('cleanup_due_at', 0):
            raise ValueError('演练已到清理时间或已释放，禁止创建和测试')

    def host_remember(self, role, key, value):
        self.state['resources'].setdefault(role, {})[key] = value
        self.write()

    def host_name(self, role):
        if role not in ('probe', 'business'):
            raise ValueError('未知主机角色')
        return self.state['demo_id'] + '-' + role

    def server(self, role):
        sid = self.state['resources'].get(role, {}).get('server_id')
        if not sid:
            return None
        try:
            server = self.ecs.show_server(ShowServerRequest(server_id=sid)).server
        except ClientRequestException as e:
            if e.status_code == 404:
                return None
            raise
        if server.name != self.host_name(role):
            raise ValueError('主机归属校验失败')
        return server

    def create_hosts(self):
        self.guard_active()
        fw = self.firewall()
        if not fw or fw.get('status') != 2:
            raise ValueError('CFW 尚未运行，不创建付费主机')
        if not self.state.get('operator_cidrs'):
            import ipaddress
            # Determine actual operator egress over the same system route, not a broad SSH CIDR.
            session = requests.Session(); session.trust_env = False
            ip = session.get('https://api.ipify.org', timeout=15).text.strip()
            ipaddress.IPv4Address(ip)
            self.state['operator_cidrs'] = [ip + '/32']; self.write()
        for i, role in enumerate(('probe', 'business')):
            self.guard_active()
            res = self.state['resources'].setdefault(role, {})
            name, pid = self.host_name(role), self.pid
            if not res.get('vpc_id'):
                v = self.api('vpc', f'/v1/{pid}/vpcs', 'POST', {'vpc': {'name': name, 'cidr': f'10.{86+i}.0.0/16', 'description': 'Synthetic CFW lab ' + self.state['demo_id']}})['vpc']
                self.host_remember(role, 'vpc_id', v['id'])
            if not res.get('subnet_id'):
                s = self.api('vpc', f'/v1/{pid}/subnets', 'POST', {'subnet': {'name': name+'-subnet', 'vpc_id': res['vpc_id'], 'cidr': f'10.{86+i}.1.0/24', 'gateway_ip': f'10.{86+i}.1.1', 'dhcp_enable': True}})['subnet']
                self.host_remember(role, 'subnet_id', s['id'])
            if not res.get('sg_id'):
                s = self.api('vpc', f'/v1/{pid}/security-groups', 'POST', {'security_group': {'name': name+'-sg', 'vpc_id': res['vpc_id'], 'description': 'Owned CFW demo; operator and peer /32 only'}})['security_group']
                self.host_remember(role, 'sg_id', s['id'])
            if not res.get('ssh_rules'):
                ids = []
                for cidr in self.state['operator_cidrs']:
                    rule = self.api('vpc', f'/v1/{pid}/security-group-rules', 'POST', {'security_group_rule': {'security_group_id': res['sg_id'], 'direction': 'ingress', 'ethertype': 'IPv4', 'protocol': 'tcp', 'port_range_min': 22, 'port_range_max': 22, 'remote_ip_prefix': cidr, 'description': self.state['demo_id']}})['security_group_rule']
                    ids.append(rule['id']); self.host_remember(role, 'ssh_rules', ids)
            if not res.get('server_id'):
                if res.get('create_attempted'):
                    raise ValueError('已有 ECS 创建请求，先核对作业，不重复创建')
                self.host_remember(role, 'password', 'Cfw7!'+secrets.token_hex(8)+'a')
                self.host_remember(role, 'create_attempted', True)
                ttl = datetime.fromtimestamp(self.state['cleanup_due_at']/1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                r = self.ecs.create_servers(CreateServersRequest(body=CreateServersRequestBody(server=PostPaidServer(
                    name=name, description='Synthetic data only; '+self.state['demo_id'],
                    image_ref=self.plan['image_id'], flavor_ref=self.plan['flavor'], availability_zone=self.plan['availability_zone'],
                    vpcid=res['vpc_id'], nics=[PostPaidServerNic(subnet_id=res['subnet_id'])],
                    root_volume=PostPaidServerRootVolume(volumetype='SAS', size=40),
                    security_groups=[PostPaidServerSecurityGroup(id=res['sg_id'])], admin_pass=res['password'],
                    auto_terminate_time=ttl, tags=['cfw-lab'],
                    extendparam=PostPaidServerExtendParam(charging_mode='postPaid')))))
                self.host_remember(role, 'server_id', r.server_ids[0]); self.host_remember(role, 'created_at', int(time.time()*1000))
                self.record('已创建 '+role+' ECS', '按需 2核4GB / 40GB；已设置原生定时删除')
        return self.bind_hosts()

    def bind_hosts(self):
        self.guard_active()
        for role in ('probe', 'business'):
            res = self.state['resources'][role]
            server = self.server(role)
            if not server or server.status != 'ACTIVE':
                return {'pending': role+' ECS 尚未运行'}
            volumes = server.to_dict().get('os_extended_volumesvolumes_attached', [])
            roots = [v['id'] for v in volumes if str(v.get('boot_index')) == '0']
            if len(roots) != 1:
                raise ValueError('无法唯一识别本轮系统盘')
            self.host_remember(role, 'root_volume_id', roots[0])
            if not res.get('port_id'):
                ports = self.ecs.list_server_interfaces(ListServerInterfacesRequest(server_id=res['server_id'])).interface_attachments
                if len(ports) != 1:
                    raise ValueError('主机网卡数量不符合本轮配置')
                self.host_remember(role, 'port_id', ports[0].port_id)
            if not res.get('eip_id'):
                eip = self.api('vpc', f'/v1/{self.pid}/publicips', 'POST', {'publicip': {'type': '5_bgp', 'ip_version': 4}, 'bandwidth': {'name': self.host_name(role)+'-bw', 'share_type': 'PER', 'size': 5, 'charge_mode': 'traffic'}})['publicip']
                self.host_remember(role, 'eip_id', eip['id']); self.host_remember(role, 'public_ip', eip['public_ip_address'])
                if eip.get('bandwidth_id'):
                    self.host_remember(role, 'bandwidth_id', eip['bandwidth_id'])
            self.api('vpc', f'/v1/{self.pid}/publicips/{res["eip_id"]}', 'PUT', {'publicip': {'port_id': res['port_id']}})
            self.host_remember(role, 'bound', True)
        for role, peer, port in (('probe', 'business', 18080), ('business', 'probe', 8080)):
            r = self.state['resources'][role]
            if not r.get('peer_rule_id'):
                rule = self.api('vpc', f'/v1/{self.pid}/security-group-rules', 'POST', {'security_group_rule': {'security_group_id': r['sg_id'], 'direction': 'ingress', 'ethertype': 'IPv4', 'protocol': 'tcp', 'port_range_min': port, 'port_range_max': port, 'remote_ip_prefix': self.state['resources'][peer]['public_ip']+'/32', 'description': 'Owned peer only '+self.state['demo_id']}})['security_group_rule']
                self.host_remember(role, 'peer_rule_id', rule['id'])
        self.state['checks']['hosts'] = True; self.write()
        return {'hosts_ready': True}

    def ssh(self, role, command, stdin=None, first=False, timeout=40):
        import paramiko
        res = self.state['resources'][role]
        server = self.server(role)
        if not server or server.status != 'ACTIVE':
            raise ValueError('专用 ECS 未运行')
        client = paramiko.SSHClient(); known = self.runtime / 'known_hosts'
        if known.exists(): client.load_host_keys(str(known))
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy() if first and not res.get('host_key_pinned') else paramiko.RejectPolicy())
        try:
            transport = self.tls_socket(role) if res.get('tls_ready') else None
            client.connect(res['public_ip'], username='root', password=res['password'], timeout=12, banner_timeout=20, auth_timeout=12, allow_agent=False, look_for_keys=False, sock=transport)
            if first and not res.get('host_key_pinned'):
                client.save_host_keys(str(known)); known.chmod(0o600); self.host_remember(role, 'host_key_pinned', True)
            inp, out, err = client.exec_command(command, timeout=timeout)
            if stdin is not None:
                inp.write(stdin); inp.channel.shutdown_write()
            stdout, stderr = out.read().decode(errors='replace'), err.read().decode(errors='replace')
            if out.channel.recv_exit_status() != 0:
                raise RuntimeError('专用 ECS 固定动作执行失败：'+stderr[-300:])
            return stdout
        finally:
            client.close()

    def tls_socket(self, role):
        import socket, ssl, urllib.request, urllib.parse
        r=self.state['resources'][role];ip=r['public_ip']
        proxy=urllib.request.getproxies().get('https')
        if proxy:
            p=urllib.parse.urlsplit(proxy)
            if p.hostname not in ('127.0.0.1','localhost') or p.username:raise ValueError('仅使用本机既有无认证代理')
            raw=socket.create_connection((p.hostname,p.port),timeout=12)
            raw.sendall(f'CONNECT {ip}:443 HTTP/1.1\r\nHost: {ip}:443\r\n\r\n'.encode())
            header=b''
            while b'\r\n\r\n' not in header:
                piece=raw.recv(1)
                if not piece:raise OSError('本机代理未建立连接')
                header+=piece
                if len(header)>8192:raise OSError('代理响应异常')
            if b' 200 ' not in header.split(b'\r\n')[0]:raise OSError('代理拒绝 TLS 连接')
        else:raw=socket.create_connection((ip,443),timeout=12)
        context=ssl.create_default_context(cafile=str(self.runtime/(role+'-tls.crt')))
        tls=context.wrap_socket(raw,server_hostname=ip)
        tls.sendall(('CONNECT /ssh HTTP/1.1\r\nHost: '+ip+'\r\nAuthorization: Bearer '+r['tls_token']+'\r\n\r\n').encode())
        header=b''
        while b'\r\n\r\n' not in header:
            piece=tls.recv(1)
            if not piece:raise OSError('管理通道未连接')
            header+=piece
            if len(header)>8192:raise OSError('管理响应异常')
        if b' 200 ' not in header.split(b'\r\n')[0]:tls.close();raise OSError('管理通道认证失败')
        return tls

    def initialize_tls(self):
        import base64, ipaddress
        from datetime import timedelta
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from huaweicloudsdkecs.v2 import (ReinstallServerWithCloudInitRequest,ReinstallServerWithCloudInitRequestBody,ReinstallServerWithCloudInitOption,ReinstallSeverMetadata)
        self.guard_active()
        if self.state['checks'].get('bootstrap'):raise ValueError('已有业务服务，不自动重装')
        for role in ('probe','business'):
            r=self.state['resources'][role]
            self.server(role)
            if not r.get('tls_sg_rules'):
                ids=[]
                for cidr in self.state['operator_cidrs']:
                    rule=self.api('vpc',f'/v1/{self.pid}/security-group-rules','POST',{'security_group_rule':{'security_group_id':r['sg_id'],'direction':'ingress','ethertype':'IPv4','protocol':'tcp','port_range_min':443,'port_range_max':443,'remote_ip_prefix':cidr,'description':'Pinned TLS operator management only'}})['security_group_rule']
                    ids.append(rule['id']);self.host_remember(role,'tls_sg_rules',ids)
            if role=='business':
                for index,cidr in enumerate(self.state['operator_cidrs']):self.add_rule('tls-management-'+str(index),0,cidr,r['public_ip']+'/32',443,0)
            if r.get('tls_reinstall_attempted'):continue
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,self.host_name(role))])
            cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=5)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(r['public_ip']))]),critical=False).sign(key,hashes.SHA256())
            pem=cert.public_bytes(serialization.Encoding.PEM).decode();private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
            path=self.runtime/(role+'-tls.crt');path.write_text(pem);path.chmod(0o600)
            token=secrets.token_urlsafe(32);self.host_remember(role,'tls_token',token)
            files=[('/opt/cfw-lab/tls_ssh.py',(Path(__file__).parent/'tls_ssh.py').read_text(),'0700'),('/opt/cfw-lab/workload.py',(Path(__file__).parent/'workload.py').read_text(),'0700'),('/opt/cfw-lab/tls.crt',pem,'0600'),('/opt/cfw-lab/tls.key',private,'0600'),('/opt/cfw-lab/tls-token',token,'0600')]
            for service,command in [('cfw-tls-ssh','/usr/bin/python3 /opt/cfw-lab/tls_ssh.py'),('cfw-lab','/usr/bin/python3 /opt/cfw-lab/workload.py --port '+('18080' if role=='probe' else '8080'))]:
                files.append(('/etc/systemd/system/'+service+'.service','[Unit]\nAfter=network.target\n[Service]\nExecStart='+command+'\nRestart=on-failure\n[Install]\nWantedBy=multi-user.target\n','0644'))
            files.append(('/etc/ssh/sshd_config.d/90-cfw-lab.conf','PermitRootLogin yes\nPasswordAuthentication yes\n','0600'))
            config={'ssh_pwauth':True,'disable_root':False,'chpasswd':{'expire':False,'list':'root:'+r['password']},'write_files':[{'path':p,'content':base64.b64encode(c.encode()).decode(),'encoding':'b64','permissions':per} for p,c,per in files],'runcmd':[['systemctl','daemon-reload'],['systemctl','restart','ssh'],['systemctl','enable','--now','cfw-tls-ssh'],['systemctl','enable','--now','cfw-lab']]}
            userdata=base64.b64encode(('#cloud-config\n'+json.dumps(config)).encode()).decode()
            if len(userdata)>32768:raise ValueError('Cloud-Init 数据过大')
            self.host_remember(role,'tls_reinstall_attempted',True)
            response=self.ecs.reinstall_server_with_cloud_init(ReinstallServerWithCloudInitRequest(server_id=r['server_id'],body=ReinstallServerWithCloudInitRequestBody(os_reinstall=ReinstallServerWithCloudInitOption(adminpass=r['password'],mode='withStopServer',metadata=ReinstallSeverMetadata(user_data=userdata))))).to_dict()
            self.host_remember(role,'tls_reinstall_job',response);self.host_remember(role,'host_key_pinned',False)
            self.record(role+' 空白演练机已提交初始化','仅本轮无业务数据主机；固定证书 TLS 管理，清理时间保持不变')
        return {'initialization_submitted':True}

    def verify_tls(self):
        for role in ('probe','business'):
            s=self.tls_socket(role);banner=s.recv(128);s.close()
            if not banner.startswith(b'SSH-'):raise ValueError('TLS 内未返回真实 SSH 服务')
            self.host_remember(role,'tls_ready',True)
        return self.bootstrap()

    def bootstrap(self):
        self.guard_active()
        if not self.state['checks'].get('hosts'):
            raise ValueError('双机网络尚未就绪')
        for role, port in (('probe', 18080), ('business', 8080)):
            source = (Path(__file__).parent/'workload.py').read_text()
            unit = f'[Unit]\nDescription=Owned CFW synthetic workload\nAfter=network.target\n[Service]\nExecStart=/usr/bin/python3 /opt/cfw-lab/workload.py --port {port}\nRestart=on-failure\n[Install]\nWantedBy=multi-user.target\n'
            script = 'from pathlib import Path\nimport subprocess\np=Path("/opt/cfw-lab");p.mkdir(exist_ok=True)\n(p/"workload.py").write_text('+repr(source)+')\nPath("/etc/systemd/system/cfw-lab.service").write_text('+repr(unit)+')\nsubprocess.run(["systemctl","daemon-reload"],check=True)\nsubprocess.run(["systemctl","enable","--now","cfw-lab.service"],check=True)\nprint("synthetic workload ready")\n'
            self.ssh(role, 'python3 -', script, first=True)
            self.host_remember(role, 'workload_ready', True)
        self.state['checks']['bootstrap'] = True; self.record('双机合成订单服务已部署', '仅自有端点；Python 标准库，无外部软件下载')
        return {'workloads_ready': True}

    def object_id(self):
        from huaweicloudsdkcfw.v1 import ListFirewallDetailRequest
        if self.state.get('object_id'): return self.state['object_id']
        fw = self.firewall()
        if not fw or fw['status'] != 2: raise ValueError('CFW 尚未运行')
        data = self.cfw.list_firewall_detail(ListFirewallDetailRequest(offset=0, limit=10, service_type=0, fw_instance_id=fw['fw_instance_id'])).to_dict()
        records = (data.get('data') or {}).get('records') or []
        objects = [o['object_id'] for r in records if r.get('fw_instance_id') == fw['fw_instance_id'] for o in r.get('protect_objects', []) if o.get('type') == 0]
        if len(objects) != 1: raise ValueError('无法唯一识别互联网防护对象')
        self.state['object_id'] = objects[0]; self.write()
        return objects[0]

    def rules(self):
        from huaweicloudsdkcfw.v1 import ListAclRulesRequest
        d = self.cfw.list_acl_rules(ListAclRulesRequest(object_id=self.object_id(), type=0, limit=100, offset=0, fw_instance_id=self.state['resources']['firewall_id'])).to_dict()
        return (d.get('data') or {}).get('records') or []

    def add_rule(self, suffix, direction, source, destination, port, action):
        from huaweicloudsdkcfw.v1 import (AddAclRuleRequest, AddRuleAclDto, AddRuleAclDtoRules, OrderRuleAclDto, RuleAddressDtoForRequest, RuleServiceDto)
        name = self.state['demo_id']+'-'+suffix
        existing = [r for r in self.rules() if r.get('name') == name]
        if len(existing) > 1: raise ValueError('重复规则名称')
        if existing: return existing[0]['rule_id']
        self.cfw.add_acl_rule(AddAclRuleRequest(fw_instance_id=self.state['resources']['firewall_id'], body=AddRuleAclDto(object_id=self.object_id(), type=0, rules=[AddRuleAclDtoRules(
            name=name, sequence=OrderRuleAclDto(top=1), address_type=0, action_type=action, status=1,
            applications=['ANY'], long_connect_enable=0, long_connect_time=180,
            long_connect_time_hour=0, long_connect_time_minute=3, long_connect_time_second=0,
            description='Owned fixed CFW lab '+self.state['demo_id'], direction=direction,
            source=RuleAddressDtoForRequest(type=0, address_type=0, address=source),
            destination=RuleAddressDtoForRequest(type=0, address_type=0, address=destination),
            service=RuleServiceDto(type=0, protocol=6 if port else -1, source_port='1-65535', dest_port=str(port) if port else '1-65535'))])))
        found = [r for r in self.rules() if r.get('name') == name]
        if len(found) != 1: raise ValueError('规则已提交但未确认 ID；禁止重复创建')
        self.state.setdefault('rule_ids', {})[suffix] = found[0]['rule_id']; self.write()
        return found[0]['rule_id']

    def delete_rule(self, rule_id):
        from huaweicloudsdkcfw.v1 import DeleteAclRuleRequest
        record = next((r for r in self.rules() if r['rule_id'] == rule_id), None)
        if record is None: return
        if not record.get('name', '').startswith(self.state['demo_id']+'-'):
            raise ValueError('拒绝删除非本轮 CFW 规则')
        self.cfw.delete_acl_rule(DeleteAclRuleRequest(acl_rule_id=rule_id, fw_instance_id=self.state['resources']['firewall_id']))

    def eip(self, sync=0):
        from huaweicloudsdkcfw.v1 import ListEipsRequest
        r = self.state['resources']['business']
        d = self.cfw.list_eips(ListEipsRequest(object_id=self.object_id(), fw_instance_id=self.state['resources']['firewall_id'], sync=sync, limit=100, offset=0)).to_dict()
        records = (d.get('data') or {}).get('records') or []
        return next((i for i in records if i.get('id') == r['eip_id'] and i.get('public_ip') == r['public_ip']), None)

    def connect_services(self):
        from huaweicloudsdkcfw.v1 import ChangeEipStatusRequest, EipOperateProtectReq, EipOperateProtectReqIpInfos
        self.guard_active()
        if not self.state['checks'].get('hosts'): raise ValueError('双机网络尚未就绪')
        a, b = (self.state['resources'][k]['public_ip']+'/32' for k in ('probe', 'business'))
        self.state.setdefault('original_rules', self.rules()); self.write()
        # Deny defaults first; each following exact allow is inserted above them.
        self.add_rule('default-in-deny', 0, '0.0.0.0/0', b, None, 1)
        self.add_rule('default-out-deny', 1, b, '0.0.0.0/0', None, 1)
        for index, cidr in enumerate(self.state['operator_cidrs']):
            self.add_rule('management-'+str(index), 0, cidr, b, 22, 0)
        self.add_rule('test-in-allow', 0, a, b, 8080, 0)
        self.add_rule('test-out-allow', 1, b, a, 18080, 0)
        r = self.state['resources']['business']
        found = self.eip(sync=1)
        if not found: return {'pending': 'EIP 资产同步中；规则已保存'}
        if found.get('status') != 0:
            self.cfw.change_eip_status(ChangeEipStatusRequest(fw_instance_id=self.state['resources']['firewall_id'], body=EipOperateProtectReq(object_id=self.object_id(), status=0, ip_infos=[EipOperateProtectReqIpInfos(id=r['eip_id'], public_ip=r['public_ip'])])))
            self.state['protection_requested'] = True; self.write()
        found = self.eip()
        if not found or found.get('status') != 0: return {'pending': '等待 EIP 防护生效'}
        self.state['checks']['protected'] = True; self.record('业务 EIP 已接入真实 CFW', '仅本轮业务 EIP；管理与测试放行，其他流量默认拒绝')
        return {'protected': True, 'rule_count': len(self.rules())}

    def probe(self, scenario, marker):
        if scenario not in ('ingress', 'egress', 'priority'): raise ValueError('不支持的实际测试场景')
        role, destination, port = ('business','probe',18080) if scenario == 'egress' else ('probe','business',8080)
        r = self.state['resources']
        source = (Path(__file__).parent/'probe.py').read_text()
        source += '\nprint(json.dumps(run('+repr(r[destination]['public_ip'])+','+str(port)+','+repr(r[role]['public_ip'])+','+repr(marker)+')))\n'
        return json.loads(self.ssh(role, 'python3 -', source, timeout=30))

    def exercise(self, scenario):
        self.guard_active()
        if scenario not in ('ingress', 'egress', 'priority'): raise ValueError('该场景未接入实际执行器')
        if not self.state['checks'].get('bootstrap'): raise ValueError('合成服务尚未部署，禁止实测')
        if not self.state['checks'].get('protected') or not self.eip() or self.eip()['status'] != 0:
            raise ValueError('真实 EIP 防护尚未确认')
        if len(self.state['runs']) >= 20: raise ValueError('本轮已达到 20 次演练限额')
        run = {'id': uuid.uuid4().hex[:10], 'scenario': scenario, 'started_at': int(time.time()*1000), 'status': 'running', 'phase': 'baseline', 'measurements': {}, 'matched_logs': []}
        self.state['runs'].append(run); self.write()
        self.record('开始真实 '+scenario+' 演练', '固定自有目标；每阶段 3 个 HTTP 请求')
        deny_id = None; broad_id = None
        try:
            run['measurements']['baseline'] = self.probe(scenario, run['id']+'-baseline'); self.write()
            if not all(m['http_status'] == 200 and m['synthetic'] for m in run['measurements']['baseline']):
                raise ValueError('基线请求失败，不能继续或据此判断 CFW 阻断')
            a, b = (self.state['resources'][k]['public_ip']+'/32' for k in ('probe', 'business'))
            if scenario == 'priority':
                broad_id = self.add_rule('broad-'+run['id'], 0, '0.0.0.0/0', b, 8080, 0)
                run['broad_allow_rule_id'] = broad_id
            run['phase'] = 'deny'; self.write()
            deny_id = self.add_rule('deny-'+run['id'], 1 if scenario == 'egress' else 0, b if scenario == 'egress' else a, a if scenario == 'egress' else b, 18080 if scenario == 'egress' else 8080, 1)
            run['deny_rule_id'] = deny_id
            run['rule_order'] = [{'rule_id':r['rule_id'],'name':r.get('name'),'order_id':r.get('order_id')} for r in self.rules()]
            self.write(); time.sleep(3)
            run['measurements']['deny'] = self.probe(scenario, run['id']+'-deny'); self.write()
        except Exception as e:
            run['error'] = str(e)[:250]
            run['status'] = 'error'
        finally:
            run['phase'] = 'restore'; self.write()
            for rule_id in (deny_id, broad_id):
                if rule_id:
                    try: self.delete_rule(rule_id)
                    except Exception: run.setdefault('restore_errors', []).append('演练规则删除失败：'+rule_id)
            time.sleep(3)
            try: run['measurements']['restored'] = self.probe(scenario, run['id']+'-restored')
            except Exception: run['measurements']['restored'] = []; run.setdefault('restore_errors', []).append('恢复验证请求异常')
            restored = bool(run['measurements']['restored']) and all(m['http_status'] == 200 and m['synthetic'] for m in run['measurements']['restored'])
            run['network_behavior_passed'] = bool(restored and run['measurements'].get('deny') and all(m['http_status'] is None for m in run['measurements']['deny']) and not run.get('error') and not run.get('restore_errors'))
            run['finished_at'] = int(time.time()*1000); run['phase'] = 'completed'
            run['status'] = 'awaiting_logs' if run['network_behavior_passed'] else 'failed'
            self.write()
        self.refresh_logs()
        self.record('真实 '+scenario+' 请求与恢复验证结束', '网络行为通过；等待原生拒绝日志' if run['network_behavior_passed'] else '有未通过项，见真实请求记录')
        return run

    def refresh_logs(self):
        from huaweicloudsdkcfw.v1 import ListAccessControlLogsRequest
        for run in self.state['runs'][-10:]:
            if not run.get('deny_rule_id') or not run.get('finished_at'): continue
            if time.time()*1000-run['finished_at'] > 30*60*1000 and run.get('status') == 'passed': continue
            try:
                d = self.cfw.list_access_control_logs(ListAccessControlLogsRequest(fw_instance_id=self.state['resources']['firewall_id'], rule_id=run['deny_rule_id'], start_time=run['started_at']-5000, end_time=int(time.time()*1000), limit=100, log_type='internet')).to_dict()
                run.pop('logs_error', None)
            except Exception:
                run['logs_error'] = '原生日志查询失败，不能判断是否匹配'; continue
            records = (d.get('data') or {}).get('records') or []
            known = run.get('matched_logs', []) + [r for r in records if matches_deny(run, r)]
            unique = {(r.get('rule_id'), r.get('log_id'), r.get('hit_time'), r.get('src_port')):r for r in known}
            run['matched_logs'] = list(unique.values())
            denied = run.get('measurements', {}).get('deny', [])
            run['matched_request_count'] = sum(any(matches_deny({**run, 'measurements': {'deny':[sample]}}, r) for r in run['matched_logs']) for sample in denied)
            run['logs_checked_at'] = int(time.time()*1000)
            if denied and run['matched_request_count'] == len(denied) and run.get('network_behavior_passed'): run['status'] = 'passed'
        self.write()
        return {'runs': len(self.state['runs']), 'matched_log_count': sum(len(r.get('matched_logs', [])) for r in self.state['runs'])}

    def cleanup_host(self, role):
        r = self.state['resources'].get(role)
        if not r: return
        def remove(*keys):
            for k in keys: r.pop(k, None)
            self.write()
        if r.get('server_id'):
            server = self.server(role)
            if server and server.status != 'DELETED':
                volumes = server.to_dict().get('os_extended_volumesvolumes_attached', [])
                if not r.get('root_volume_id') and len(volumes) == 1 and str(volumes[0].get('boot_index')) == '0':
                    self.host_remember(role, 'root_volume_id', volumes[0]['id'])
                if any(v['id'] != r.get('root_volume_id') for v in volumes):
                    raise ValueError('主机挂载了本轮未记录磁盘，停止删除')
                self.ecs.delete_servers(DeleteServersRequest(body=DeleteServersRequestBody(servers=[ServerId(id=r['server_id'])], delete_publicip=False, delete_volume=True)))
                for _ in range(25):
                    current = self.server(role)
                    if not current or current.status == 'DELETED': break
                    time.sleep(2)
                else: return False
            remove('server_id', 'password')
        if r.get('root_volume_id'):
            path = f'/v2/{self.pid}/volumes/{r["root_volume_id"]}'
            for _ in range(15):
                actual = self.api('evs', path, allow_missing=True)
                if actual is None: break
                v = actual['volume']
                if v.get('attachments'):
                    raise ValueError('系统盘被其他主机挂载，停止清理')
                if v['status'] == 'available': self.api('evs', path, 'DELETE', allow_missing=True)
                elif v['status'] != 'deleting': raise ValueError('系统盘状态异常，保留 ID')
                time.sleep(2)
            else: return False
            remove('root_volume_id')
        if r.get('eip_id'):
            path = f'/v1/{self.pid}/publicips/{r["eip_id"]}'
            actual = self.api('vpc', path, allow_missing=True)
            if actual:
                ip = actual['publicip']
                if ip.get('public_ip_address') != r.get('public_ip') or ip.get('port_id') not in ('', None, r.get('port_id')):
                    raise ValueError('EIP 地址或绑定已改变，停止删除')
                self.api('vpc', path, 'DELETE', allow_missing=True)
            if self.api('vpc', path, allow_missing=True) is not None: return False
            remove('eip_id', 'public_ip', 'port_id')
        if r.get('bandwidth_id'):
            path = f'/v1/{self.pid}/bandwidths/{r["bandwidth_id"]}'
            actual = self.api('vpc', path, allow_missing=True)
            if actual:
                b = actual['bandwidth']
                if b.get('name') != self.host_name(role)+'-bw' or b.get('publicip_info'):
                    raise ValueError('带宽名称或关联已改变，停止删除')
                if b.get('share_type') != 'PER':
                    raise ValueError('带宽已变更为共享，停止自动删除')
                # Dedicated bandwidth is released with its EIP; only shared bandwidth has a delete API.
                return False
            remove('bandwidth_id')
        for key, plural, singular, suffix in (('sg_id','security-groups','security_group','-sg'),('subnet_id','subnets','subnet','-subnet'),('vpc_id','vpcs','vpc','')):
            if not r.get(key): continue
            path = f'/v1/{self.pid}/{plural}/{r[key]}'
            actual = self.api('vpc', path, allow_missing=True)
            if actual:
                if actual[singular]['name'] != self.host_name(role)+suffix:
                    raise ValueError('网络资源归属校验失败')
                self.api('vpc', path, 'DELETE', allow_missing=True)
            if self.api('vpc', path, allow_missing=True) is not None: return False
            remove(key)
        self.state['resources'].pop(role, None); self.write()
        return True

    def cleanup(self):
        if self.state.get('released') and not self.state['resources']:
            return {'released': True}
        actual = self.firewall()
        if actual and actual.get('status') != 4:
            if self.state['checks'].get('protected') or self.state.get('protection_requested'):
                from huaweicloudsdkcfw.v1 import ChangeEipStatusRequest, EipOperateProtectReq, EipOperateProtectReqIpInfos
                r = self.state['resources']['business']
                self.cfw.change_eip_status(ChangeEipStatusRequest(fw_instance_id=actual['fw_instance_id'], body=EipOperateProtectReq(object_id=self.state['object_id'], status=1, ip_infos=[EipOperateProtectReqIpInfos(id=r['eip_id'], public_ip=r['public_ip'])])))
                self.state['checks']['protected'] = False; self.state['protection_requested'] = False; self.write()
            if actual.get('status') == 1:
                return {'released': False, 'pending': 'CFW 删除中'}
            result = self.cfw.delete_firewall(DeleteFirewallRequest(resource_id=actual['fw_instance_id'])).to_dict()
            self.state['cfw_delete_result'] = result; self.record('已提交删除本轮 CFW', '等待云端确认删除')
            return {'released': False, 'pending': 'CFW 删除已提交'}
        self.state['resources'].pop('firewall_id', None)
        for role in ('probe', 'business'):
            if self.cleanup_host(role) is False:
                return {'released': False, 'pending': role+' 删除中'}
        if self.state['resources']:
            raise ValueError('仍有未识别资源记录，未标记释放成功')
        self.state['released'] = True; self.write()
        return {'released': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['open-cfw', 'status', 'cleanup', 'create-hosts', 'bind-hosts', 'bootstrap', 'connect-services', 'refresh-logs', 'exercise', 'initialize-tls', 'verify-tls'])
    parser.add_argument('--scenario', choices=['ingress', 'egress', 'priority'])
    parser.add_argument('--confirm')
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (RUNTIME / 'action.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lab = Lab()
        if args.action == 'cleanup' and args.confirm != lab.state['demo_id']:
            raise ValueError('清理需要完整本轮 Demo ID')
        result = lab.exercise(args.scenario) if args.action == 'exercise' else getattr(lab, args.action.replace('-', '_'))()
        # status CLI is local/private; password fields are removed before display.
        print(json.dumps(result, ensure_ascii=False, indent=2))
