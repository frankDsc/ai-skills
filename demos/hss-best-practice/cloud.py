"""Real Huawei Cloud control plane. Secrets never enter browser responses."""
import csv
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

import paramiko
import requests
from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkcore.exceptions.exceptions import ClientRequestException
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.signer.signer import Signer
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
from huaweicloudsdkhss.v5 import (
    ListHostStatusRequest, ListSecurityEventsRequest, ListAgentInstallScriptRequest,
    SwitchHostsProtectStatusRequest, SwitchHostsProtectStatusRequestInfo,
    ListHostVulsRequest, ListRiskConfigsRequest,
    ChangeEventRequest, ChangeEventRequestInfo, OperateEventRequestInfo,
)
from huaweicloudsdkecs.v2 import (
    CreateServersRequest, CreateServersRequestBody, PostPaidServer,
    PostPaidServerNic, PostPaidServerRootVolume, PostPaidServerSecurityGroup,
    PostPaidServerExtendParam, ListFlavorsRequest, NovaListAvailabilityZonesRequest,
    ShowServerRequest, ListServerInterfacesRequest, DeleteServersRequest,
    DeleteServersRequestBody, ServerId,
)
from huaweicloudsdkims.v2 import ImsClient, ListImagesRequest

# Reuse the selected Skill's regional SDK clients, rather than a second SDK layer.
SKILL = Path(__file__).resolve().parents[2] / 'skills/huawei-cloud-bestpractice-demo'
sys.path.insert(0, str(SKILL))
from lib.common import ecs_client, hss_client  # noqa: E402
from lib.provision import gen_password  # noqa: E402
from scenarios import get_scenario, command_for, match_events, CLEANUP_COMMAND

REGION = 'cn-north-4'
DEFAULT_RUNTIME = Path.home() / '.local/state/hss-best-practice'


def error_message(exc):
    if isinstance(exc, ClientRequestException):
        return f'{exc.status_code} {exc.error_code}: {exc.error_msg}'[:500]
    if isinstance(exc, requests.RequestException):
        return '云 API 网络请求失败或超时，请重试'
    return str(exc)[:500]


class Cloud:
    def __init__(self):
        credential_path = Path(os.environ.get('HWC_CREDENTIALS_CSV', str(Path.home() / 'Downloads/credentials.csv'))).expanduser()
        with credential_path.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            raise ValueError('凭证 CSV 必须恰好包含一行凭证')
        self.ak, self.sk = (rows[0].get(k, '').strip() for k in ('Access Key Id', 'Secret Access Key'))
        if not self.ak or not self.sk:
            raise ValueError('CSV 缺少 Access Key Id 或 Secret Access Key')
        self.runtime = Path(os.environ.get('HSS_DEMO_RUNTIME', str(DEFAULT_RUNTIME))).expanduser()
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime, 0o700)
        self.path = self.runtime / 'state.json'
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'demo_id': 'hss-bp-' + time.strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:6],
            'region': REGION, 'resources': {}, 'checks': {}, 'journal': [], 'resources_released': False,
        }
        self.state.setdefault('resources_released', False)
        if self.state['region'] != REGION:
            raise ValueError('运行时区域不匹配')
        self.cfg = {'ak': self.ak, 'sk': self.sk, 'region': REGION}
        self.project_id = None
        self._save()

    def _save(self):
        # Atomic state updates retain partial-provision IDs for scoped cleanup.
        temporary = self.path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        os.replace(temporary, self.path)

    def record(self, name, detail, level='info'):
        self.state['journal'].insert(0, {'name': name, 'detail': detail, 'level': level, 'ts': int(time.time() * 1000)})
        self.state['journal'] = self.state['journal'][:100]
        self._save()

    def connect(self):
        cli = IamClient.new_builder().with_credentials(GlobalCredentials(self.ak, self.sk)).with_endpoint('https://iam.myhuaweicloud.com').build()
        projects = cli.keystone_list_projects(KeystoneListProjectsRequest(name=REGION)).projects or []
        if not projects:
            raise ValueError('账户没有可访问的北京四项目')
        self.project_id = projects[0].id
        self.cfg['project_id'] = self.project_id
        self.ecs, self.hss = ecs_client(self.cfg), hss_client(self.cfg)
        return {'connected': True, 'region': REGION}

    def api(self, service, path, method='GET', body=None, query=None):
        """Use the official SDK signer for API operations without model wrappers."""
        host = f'{service}.{REGION}.myhuaweicloud.com'
        req = SdkRequest(method=method, schema='https', host=host,
                         resource_path=path, query_params=list((query or {}).items()),
                         header_params={'Content-Type': 'application/json', 'X-Project-Id': self.project_id},
                         body=json.dumps(body) if body is not None else '')
        Signer(BasicCredentials(self.ak, self.sk)).sign(req)
        response = requests.request(method, req.url, headers=req.header_params, data=req.body, timeout=(10, 45))
        if response.status_code >= 400:
            try:
                data = response.json()
                err = data.get('error', data)
                message = err.get('message') or err.get('error_msg') or err.get('code') or err.get('error_code')
            except (ValueError, AttributeError):
                message = '请求被云端拒绝'
            raise RuntimeError(f'{service} API {response.status_code}: {str(message)[:250]}')
        return response.json() if response.content else {}

    def hss_host(self):
        sid = self.state['resources'].get('server_id')
        if not sid:
            return None
        result = self.hss.list_host_status(ListHostStatusRequest(host_id=sid, limit=100, refresh=True))
        return next((h.to_dict() for h in result.data_list or [] if h.host_id == sid), None)

    def snapshot(self):
        res = self.state['resources']
        host, errors = None, []
        server = None
        if self.project_id and res.get('server_id'):
            try:
                server = self.ecs.show_server(ShowServerRequest(server_id=res['server_id'])).server.to_dict()
            except Exception as exc:
                errors.append(error_message(exc))
            try:
                host = self.hss_host()
            except Exception as exc:
                errors.append(error_message(exc))
        return {
            'connected': bool(self.project_id), 'region': REGION, 'demo_id': self.state['demo_id'],
            'resources_released': self.state.get('resources_released', False),
            'host': {k: (host or {}).get(k) for k in ('host_id','host_name','agent_status','protect_status','version','risk_num')},
            'ecs_status': (server or {}).get('status', '未创建'),
            'resources': {k: v for k, v in res.items() if k != 'password'},
            'checks': self.state['checks'], 'journal': self.state['journal'][:30], 'errors': errors,
            'cost_note': 'ECS、系统盘、EIP、HSS 企业版按需计费。关机不等于释放，结束后请清理。',
        }

    def preflight(self):
        if not self.project_id:
            self.connect()
        zones = self.ecs.nova_list_availability_zones(NovaListAvailabilityZonesRequest()).to_json_object()
        azs = [z['zoneName'] for z in zones.get('availabilityZoneInfo', []) if z.get('zoneState', {}).get('available')]
        if not azs:
            raise RuntimeError('北京四没有可用区')
        choice = None
        for az in azs:
            flavors = self.ecs.list_flavors(ListFlavorsRequest(availability_zone=az)).to_json_object().get('flavors', [])
            candidates = [f for f in flavors if int(f.get('vcpus', 0)) <= 2 and 2048 <= int(f.get('ram', 0)) <= 4096
                          and f.get('id', '').startswith(('s6.', 's7.', 'c6.', 'c7.'))]
            candidates.sort(key=lambda f: (int(f['vcpus']), int(f['ram']), f['id']))
            if candidates:
                choice = (az, candidates[0]); break
        if not choice:
            raise RuntimeError('未找到小规格 x86 云服务器，请指定可用规格')
        ims = ImsClient.new_builder().with_credentials(BasicCredentials(self.ak, self.sk).with_project_id(self.project_id)).with_endpoint(f'https://ims.{REGION}.myhuaweicloud.com').build()
        images = ims.list_images(ListImagesRequest(imagetype='gold', os_type='Linux', platform='Ubuntu', status='active', architecture='x86_64', limit=200)).to_json_object().get('images', [])
        images = [x for x in images if '22.04' in x.get('name', '') and int(x.get('min_disk', 0)) <= 40
                  and not any(word in x.get('name','').lower() for word in ('graphic','driver','gpu','cuda','arm','aarch64'))]
        if not images:
            raise RuntimeError('没有合适的 Ubuntu 22.04 公共镜像')
        images.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        ip = os.environ.get('HSS_SSH_SOURCE_IP')
        if not ip:
            # A mainland endpoint follows the same split-proxy route as the ECS.
            text = requests.get('https://myip.ipip.net', timeout=15).text
            match = re.search(r'当前\s*IP[：:]\s*(\d+\.\d+\.\d+\.\d+)', text)
            if not match: raise ValueError('无法识别国内出口 IP，请设置 HSS_SSH_SOURCE_IP')
            ip = match.group(1)
        ipaddress.IPv4Address(ip)
        self.state['plan'] = {'availability_zone': choice[0], 'flavor': choice[1]['id'], 'image_id': images[0]['id'],
                              'image_name': images[0]['name'], 'ssh_cidr': ip + '/32', 'disk_gb': 40,
                              'eip_mbps': 1, 'hss_version': 'hss.version.enterprise'}
        self.hss.list_host_status(ListHostStatusRequest(limit=1))
        self.state['checks']['preflight'] = True
        self._save()
        return self.state['plan']

    def _resource(self, key, value):
        self.state['resources'][key] = value
        self._save()

    def provision(self):
        if not self.state.get('plan'):
            self.preflight()
        plan, res = self.state['plan'], self.state['resources']
        name, pid = self.state['demo_id'], self.project_id
        if not res.get('vpc_id'):
            self.record('创建独立 VPC', name)
            v = self.api('vpc', f'/v1/{pid}/vpcs', 'POST', {'vpc': {'name': name, 'cidr': '10.77.0.0/16', 'description': 'Owned by HSS best-practice demo ' + name}})['vpc']
            self._resource('vpc_id', v['id'])
        if not res.get('subnet_id'):
            s = self.api('vpc', f'/v1/{pid}/subnets', 'POST', {'subnet': {'name': name+'-subnet', 'vpc_id': res['vpc_id'],
                'cidr': '10.77.1.0/24', 'gateway_ip': '10.77.1.1', 'dhcp_enable': True,
                'primary_dns': '100.125.1.250', 'secondary_dns': '100.125.129.250'}})['subnet']
            self._resource('subnet_id', s['id'])
        if not res.get('sg_id'):
            sg = self.api('vpc', f'/v1/{pid}/security-groups', 'POST', {'security_group': {'name': name+'-sg', 'vpc_id': res['vpc_id'], 'description': 'Demo-only SSH /32'}})['security_group']
            self._resource('sg_id', sg['id'])
        if not res.get('ssh_rule_id') or res.get('ssh_rule_cidr') != plan['ssh_cidr']:
            previous_rule = res.get('ssh_rule_id')
            rule = self.api('vpc', f'/v1/{pid}/security-group-rules', 'POST', {'security_group_rule': {
                'security_group_id': res['sg_id'], 'direction': 'ingress', 'ethertype': 'IPv4', 'protocol': 'tcp',
                'port_range_min': 22, 'port_range_max': 22, 'remote_ip_prefix': plan['ssh_cidr'], 'description': 'Demo operator SSH only'}})['security_group_rule']
            self._resource('ssh_rule_id', rule['id'])
            self._resource('ssh_rule_cidr', plan['ssh_cidr'])
            if previous_rule:
                self.api('vpc', f'/v1/{pid}/security-group-rules/{previous_rule}', 'DELETE')
        if not res.get('server_id'):
            password = gen_password(n=18) + '7'
            self._resource('password', password)
            self.record('创建按需 ECS', plan['flavor'] + ' / ' + plan['availability_zone'])
            response = self.ecs.create_servers(CreateServersRequest(body=CreateServersRequestBody(server=PostPaidServer(
                name=name, image_ref=plan['image_id'], flavor_ref=plan['flavor'], availability_zone=plan['availability_zone'],
                vpcid=res['vpc_id'], nics=[PostPaidServerNic(subnet_id=res['subnet_id'])],
                root_volume=PostPaidServerRootVolume(volumetype='SAS', size=40),
                security_groups=[PostPaidServerSecurityGroup(id=res['sg_id'])], admin_pass=password,
                extendparam=PostPaidServerExtendParam(charging_mode='postPaid')))))
            self._resource('server_id', response.server_ids[0])
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                server = self.ecs.show_server(ShowServerRequest(server_id=res['server_id'])).server
            except ClientRequestException as exc:
                if exc.status_code == 404:
                    time.sleep(5)
                    continue
                raise
            if server.status == 'ACTIVE': break
            if server.status == 'ERROR': raise RuntimeError('ECS 创建失败，请检查作业并清理已创建资源')
            time.sleep(5)
        else:
            raise TimeoutError('ECS 创建超时，资源 ID 已记录，可以重试或清理')
        if not res.get('eip_id'):
            self.record('分配 EIP', '1 Mbps，按流量计费；SSH 仅允许 ' + plan['ssh_cidr'])
            port = self.ecs.list_server_interfaces(ListServerInterfacesRequest(server_id=res['server_id'])).interface_attachments[0].port_id
            eip = self.api('vpc', f'/v1/{pid}/publicips', 'POST', {'publicip': {'type':'5_bgp','ip_version':4},
                'bandwidth': {'name': name+'-bandwidth', 'share_type':'PER','size':1,'charge_mode':'traffic'}})['publicip']
            self._resource('eip_id', eip['id'])
            self._resource('public_ip', eip['public_ip_address'])
            self._resource('port_id', port)
        self.api('vpc', f'/v1/{pid}/publicips/{res["eip_id"]}', 'PUT', {'publicip': {'port_id': res['port_id']}})
        self.state['checks']['provision'] = True
        self._save()
        self.record('基础设施就绪', '独立 VPC / 子网 / 安全组 / ECS / EIP')
        return {'server_id': res['server_id'], 'public_ip': res['public_ip']}

    def ssh(self, command, timeout=90):
        res = self.state['resources']
        if not res.get('server_id') or not res.get('public_ip'):
            raise ValueError('请先创建专用 Demo ECS')
        actual = self.ecs.show_server(ShowServerRequest(server_id=res['server_id'])).server
        if actual.name != self.state['demo_id']:
            raise ValueError('主机归属校验失败，拒绝执行')
        c = paramiko.SSHClient()
        known = self.runtime / 'known_hosts'
        if known.exists(): c.load_host_keys(str(known))
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(res['public_ip'], username='root', password=res['password'], timeout=15, allow_agent=False, look_for_keys=False)
            c.save_host_keys(str(known))
            _, out, err = c.exec_command(command, timeout=timeout)
            stdout, stderr = out.read().decode(errors='replace'), err.read().decode(errors='replace')
            status = out.channel.recv_exit_status()
            if status: raise RuntimeError(f'远程命令退出 {status}: {stderr[-800:]}')
            return (stdout + stderr)[-6000:]
        finally:
            c.close()

    def install(self):
        script = self.hss.list_agent_install_script(ListAgentInstallScriptRequest(region=REGION, os_type='Linux', os_arch='x86_64'))
        if not script.install_script_list:
            raise ValueError('HSS 未返回 Agent 安装脚本')
        self.record('安装 HSS Agent', '使用当前区域官方安装脚本；安装令牌不展示')
        command = script.install_script_list[0].cmd
        deadline = time.time() + 180
        while True:
            try:
                self.ssh('cd /tmp && ' + command, timeout=300)
                break
            except (paramiko.SSHException, OSError):
                if time.time() > deadline: raise
                time.sleep(5)
        for _ in range(40):
            host = self.hss_host()
            if host and host.get('agent_status') == 'online':
                self.state['checks']['install'] = True
                self._save()
                self.record('Agent 已上线', self.state['resources']['server_id'])
                return {'agent_status': 'online'}
            time.sleep(5)
        raise TimeoutError('安装命令已执行，但 Agent 尚未上线；请刷新状态后重试')

    def protect(self):
        host = self.hss_host()
        if not host or host.get('agent_status') != 'online':
            raise ValueError('请先确认 Agent 在线')
        self.hss.switch_hosts_protect_status(SwitchHostsProtectStatusRequest(body=SwitchHostsProtectStatusRequestInfo(
            version='hss.version.enterprise', charging_mode='on_demand', host_id_list=[self.state['resources']['server_id']])))
        for _ in range(24):
            host = self.hss_host()
            if host and host.get('protect_status') == 'opened' and host.get('version') == 'hss.version.enterprise':
                self.state['checks']['protect'] = True
                self._save()
                self.record('HSS 企业版防护已开启', '按需计费，告警以云端查询结果为准')
                return {'version': host.get('version'), 'protect_status': 'opened'}
            time.sleep(5)
        raise TimeoutError('防护开启请求已发送，云端状态尚未就绪')

    def events(self):
        sid = self.state['resources'].get('server_id')
        if not sid or not self.project_id: return {'events': [], 'total': 0}
        result = self.hss.list_security_events(ListSecurityEventsRequest(host_id=sid, limit=100)).to_json_object()
        events = []
        for e in result.get('data_list') or []:
            events.append({k: e.get(k) for k in ('event_id','event_class_id','event_type','event_name','event_class_name','severity','occur_time','handle_status')})
        events.sort(key=lambda e: e.get('occur_time') or 0, reverse=True)
        return {'events': events, 'total': result.get('total_num', len(events))}

    def risks(self):
        sid = self.state['resources'].get('server_id')
        if not sid: return {'vulnerabilities': [], 'baseline': [], 'errors': []}
        result = {'errors': []}
        for key, method, request in [
            ('vulnerabilities',self.hss.list_host_vuls,ListHostVulsRequest(host_id=sid,limit=20)),
            ('baseline',self.hss.list_risk_configs,ListRiskConfigsRequest(host_id=sid,standard='hw_standard',limit=20)),
        ]:
            try:
                data = method(request).to_json_object()
                result[key] = data.get('data_list') or []
            except Exception as exc:
                result[key] = []
                result['errors'].append(key + ': ' + error_message(exc))
        return result

    def prepare_scenarios(self):
        output=self.ssh('export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq nmap tcpdump strace netcat-openbsd',timeout=360)
        self.record('演练依赖已准备','仅在专用 ECS 安装 nmap / tcpdump / strace / netcat-openbsd')
        self.state['checks']['scenario_tools']=True
        self._save()
        return {'output':output}

    def exercise(self,scenario_id='suid'):
        spec=get_scenario(scenario_id)
        host = self.hss_host()
        if not host or host.get('protect_status') != 'opened' or host.get('agent_status') != 'online':
            raise ValueError('请先确认 Agent 在线且 HSS 防护已开启')
        baseline=[e['event_id'] for e in self.events()['events'] if e.get('event_id')]
        token = uuid.uuid4().hex[:10]
        started = int(time.time()*1000)
        run={'started_at':started,'marker':token,'scenario_id':scenario_id,'scenario_name':spec['name'],
             'status':'executing','baseline_event_ids':baseline}
        self.state['last_exercise']=run
        self.state.setdefault('exercise_runs',[]).append(run)
        self.state['exercise_runs']=self.state['exercise_runs'][-30:]
        self.state['checks']['artifacts_clean'] = False
        self._save()
        try:
            output=self.ssh(command_for(scenario_id,token),timeout=30)
            result=json.loads(output.strip().splitlines()[-1])
            run['execution_exit_code']=result.get('exit_code',0)
            run['status']='awaiting_detection' if run['execution_exit_code']==0 else 'execution_error'
            self.record(spec['name']+'执行结束','真实执行退出码 '+str(run['execution_exit_code'])+'；告警须由 HSS 确认')
            self._save()
            return {'output':result.get('output',''),'started_at':started,'scenario_id':scenario_id,
                    'exit_code':run['execution_exit_code'],'detection':run['status']}
        except Exception:
            run['status']='execution_error'
            self._save()
            raise

    def cleanup_artifacts(self):
        output = self.ssh(CLEANUP_COMMAND)
        self.state['checks']['artifacts_clean'] = True
        self._save()
        self.record('演练产物已清理', '仅清理 Demo 标识的样本、SUID/SGID 文件、测试账号和 cron 项')
        return {'output': output}

    def acknowledge(self):
        if not self.state['checks'].get('artifacts_clean'):
            raise ValueError('请先清理演练文件，再完成告警处置')
        started = self.state.get('last_exercise',{}).get('started_at')
        if not started:
            raise ValueError('本次 Demo 尚未执行演练')
        # Query is restricted to our recorded host; never accept event IDs from the browser.
        candidates = match_events(self.state['last_exercise'],self.events()['events'])
        if not candidates:
            raise ValueError('尚未查询到与本次场景类型、时间窗口和新事件 ID 匹配的告警')
        self.hss.change_event(ChangeEventRequest(region=REGION,body=ChangeEventRequestInfo(
            operate_type='mark_as_handled', handler='Controlled demo artifact removed - '+self.state['demo_id'],
            operate_event_list=[OperateEventRequestInfo(event_class_id=event['event_class_id'],event_id=event['event_id'],
                event_type=event['event_type'],occur_time=event['occur_time'],operate_detail_list=[]) for event in candidates])))
        self.record('告警手动处置请求已提交','只标记本次场景匹配的演练事件；实际状态以 HSS 返回为准')
        return {'event_ids':[event['event_id'] for event in candidates],'requested_operation':'mark_as_handled'}

    def cleanup(self):
        """Only IDs created and persisted by this demo may be removed."""
        res, pid = self.state['resources'], self.project_id
        if res.get('server_id'):
            server = self.ecs.show_server(ShowServerRequest(server_id=res['server_id'])).server
            if server.name != self.state['demo_id']: raise ValueError('ECS 归属校验失败')
            host = self.hss_host()
            if host and host.get('protect_status') == 'opened':
                self.hss.switch_hosts_protect_status(SwitchHostsProtectStatusRequest(body=SwitchHostsProtectStatusRequestInfo(
                    version='hss.version.null', charging_mode='on_demand', host_id_list=[res['server_id']])))
                self.record('关闭按需 HSS 防护', res['server_id'])
            self.ecs.delete_servers(DeleteServersRequest(body=DeleteServersRequestBody(delete_publicip=False, delete_volume=True, servers=[ServerId(id=res['server_id'])])))
            for _ in range(60):
                try:
                    deleted_server = self.ecs.show_server(ShowServerRequest(server_id=res['server_id'])).server
                    if deleted_server.status == 'DELETED': break
                except ClientRequestException as exc:
                    if exc.status_code == 404: break
                    raise
                time.sleep(5)
            else: raise TimeoutError('ECS 删除仍在进行，停止后续资源删除，请重试')
            res.pop('server_id',None); res.pop('password',None); self._save()
        for key, path in [('eip_id','publicips'), ('sg_id','security-groups'), ('subnet_id','subnets')]:
            if res.get(key):
                self.api('vpc',f'/v1/{pid}/{path}/{res[key]}','DELETE')
                res.pop(key); self._save()
        if res.get('vpc_id'):
            for attempt in range(12):
                try:
                    self.api('vpc',f'/v1/{pid}/vpcs/{res["vpc_id"]}','DELETE');break
                except RuntimeError:
                    if attempt==11:raise
                    time.sleep(5)
            res.pop('vpc_id');self._save()
        self.state['resources'] = {}
        self.state['checks'] = {}
        self.state.pop('plan',None)
        self.state['resources_released'] = True
        self._save()
        self.record('Demo 资源清理完成', '已清理记录的 ECS / 系统盘 / EIP / 安全组 / 子网 / VPC')
        return {'released': True}
