"""Actual SMS orchestration. All identifiers and evidence remain in private runtime."""
import json
import os
import time

from cloud import Cloud
from huaweicloudsdkecs.v2 import (ShowServerRequest, CreateServersRequest,
    CreateServersRequestBody, PostPaidServer, PostPaidServerNic,
    PostPaidServerRootVolume, PostPaidServerSecurityGroup, PostPaidServerExtendParam)
from huaweicloudsdksms.v3 import (SmsClient, ShowTaskRequest,
    ShowServerRequest as SmsShowServerRequest, UpdateTaskStatusRequest, UpdateTaskStatusReq,
    DeleteTaskRequest, DeleteServerRequest as SmsDeleteServerRequest)
from huaweicloudsdkcore.exceptions.exceptions import ClientRequestException
from huaweicloudsdkecs.v2 import DeleteServersRequest, DeleteServersRequestBody, ServerId


class SmsLab:
    def __init__(self):
        self.cloud = Cloud()
        self.path = self.cloud.runtime / 'sms-state.json'
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'demo_id': self.cloud.state['demo_id'], 'events': [], 'samples': []}
        if self.state['demo_id'] != self.cloud.state['demo_id']:
            raise ValueError('SMS state belongs to a different demo')
        self.state.setdefault('task_name',self.state['demo_id'].replace('migration-lab-','sms-'))
        self.client = SmsClient.new_builder().with_credentials(self.cloud.credential).with_endpoint(
            'https://sms.cn-north-4.myhuaweicloud.com').build()

    def save(self):
        temp = self.path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        temp.replace(self.path)

    def event(self, message):
        self.state['events'].append({'time': time.time(), 'message': message})
        self.save()

    def provision_target(self):
        c = self.cloud
        r = c.state['resources']
        source = c.ecs.show_server(ShowServerRequest(server_id=r['server_id'])).server
        if source.name != self.state['demo_id']:
            raise ValueError('Source ownership changed')
        ip = next(a.addr for items in source.addresses.values()
                  for a in items if a.os_ext_ip_stype == 'fixed')
        self.state['source_ip'] = ip
        name = self.state['demo_id'] + '-sms-target'
        self.state['target_name'] = name
        if not self.state.get('target_sg_id'):
            group = c.api('vpc', f'/v1/{c.pid}/security-groups', 'POST', {
                'security_group': {'name': name + '-sg', 'vpc_id': r['vpc_id'],
                                   'description': 'SMS target: only dedicated source host'}})['security_group']
            self.state['target_sg_id'] = group['id']; self.save()
            for port in (22, 8900, 8080):
                c.api('vpc', f'/v1/{c.pid}/security-group-rules', 'POST', {'security_group_rule': {
                    'security_group_id': group['id'], 'direction': 'ingress', 'ethertype': 'IPv4',
                    'protocol': 'tcp', 'port_range_min': port, 'port_range_max': port,
                    'remote_ip_prefix': ip + '/32'}})
        if not self.state.get('target_id'):
            p = c.plan
            response = c.ecs.create_servers(CreateServersRequest(body=CreateServersRequestBody(server=PostPaidServer(
                name=name, image_ref=p['image_id'], flavor_ref=p['flavor'],
                availability_zone=p['availability_zone'], vpcid=r['vpc_id'],
                nics=[PostPaidServerNic(subnet_id=r['subnet_id'])],
                root_volume=PostPaidServerRootVolume(volumetype='SAS', size=40),
                security_groups=[PostPaidServerSecurityGroup(id=self.state['target_sg_id'])],
                admin_pass=r['password'], extendparam=PostPaidServerExtendParam(charging_mode='postPaid')))))
            self.state.update(target_id=response.server_ids[0], target_name=name, created_at=time.time())
            self.save(); self.event('Target ECS creation accepted; no public IP allocated')
        return {'target_id': self.state['target_id']}

    def target_ready(self):
        if self.state.get('task_id'):
            raise ValueError('Do not alter target configuration while an SMS task exists')
        c = self.cloud
        server = c.ecs.show_server(ShowServerRequest(server_id=self.state['target_id'])).server
        if server.name != self.state['target_name']:
            raise ValueError('Target ownership changed')
        if server.status != 'ACTIVE':
            return {'status': server.status}
        self.state['target_ip'] = next(a.addr for items in server.addresses.values()
            for a in items if a.os_ext_ip_stype == 'fixed')
        self.state['target_root_volume_id'] = next(v.id for v in server.os_extended_volumesvolumes_attached
            if str(v.boot_index) == '0')
        c.api('ecs', f'/v1/{c.pid}/cloudservers/{self.state["target_id"]}/actions/update-auto-terminate-time',
              'POST', {'auto_terminate_time': c.state['auto_release_at']})
        self.save()
        return {'status': server.status, 'target_ip': self.state['target_ip'],
                'auto_release_at': c.state['auto_release_at']}

    def observe(self):
        if self.state.get('task_id') and not self.state.get('released'):
            telemetry_path = self.path.with_name('sms-telemetry.json')
            telemetry = json.loads(telemetry_path.read_text()) if telemetry_path.exists() else {'samples':[]}
            task = self.client.show_task(ShowTaskRequest(task_id=self.state['task_id']))
            fields = ('id','name','state','migrate_speed','remain_seconds','compress_rate','create_date',
                      'start_date','finish_date','total_time','sub_tasks','subtask_info','error_json')
            self.state['task'] = {k: task.to_dict()[k] for k in fields}
            # SDK's to_dict does not recursively serialize every nested collection.
            from huaweicloudsdkcore.utils.http_utils import sanitize_for_serialization
            self.state['task'] = sanitize_for_serialization(self.state['task'])
            source = self.client.show_server(SmsShowServerRequest(source_id=self.state['source_sms_id']))
            self.state['source_progress'] = {'replicatesize':source.replicatesize,'totalsize':source.totalsize,
                'state':source.state,'migration_cycle':source.migration_cycle}
            sample = {'time': time.time(), 'migrate_speed_mbps': task.migrate_speed,
                      **self.state['source_progress'],'task_state':task.state,
                      'subtask_info':task.subtask_info,'task_id':task.id}
            self.state['samples'] = telemetry['samples'] + [sample]
            self.state['observed_at'] = sample['time']
            target = task.target_server
            if target and target.image_disk_id:
                self.state['image_disk_id'] = target.image_disk_id
            evidence = {k:self.state[k] for k in ('task','samples','source_progress','observed_at')}
            if self.state.get('image_disk_id'): evidence['image_disk_id'] = self.state['image_disk_id']
            temp = telemetry_path.with_suffix('.tmp')
            fd = os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f: json.dump(evidence,f,ensure_ascii=False)
            temp.replace(telemetry_path)
        return {k:v for k,v in self.state.items() if k not in ('credentials','agent_session')}

    def create_task(self, continuous=True):
        if self.state.get('task_id'): return {'task_id':self.state['task_id']}
        if not continuous and not self.state.get('frozen_at'):
            raise ValueError('Cold migration requires source writes to be frozen')
        source = self.client.show_server(SmsShowServerRequest(source_id=self.state['source_sms_id']))
        if source.name != self.state['demo_id'] or source.ip != self.state['source_ip'] or not source.connected:
            raise ValueError('Source registration does not match the dedicated host')
        self.target_ready()
        data = json.loads(source.to_str())
        disks = data['init_target_server']['disks']
        if len(disks) != 1 or disks[0]['size'] > 40*1024**3:
            raise ValueError('Only the approved single 40 GiB disk is supported')
        disks[0]['disk_id'] = self.state['target_root_volume_id']
        body = {'name':self.state['task_name'],'type':'MIGRATE_FILE','os_type':'LINUX',
            'source_server':{'id':self.state['source_sms_id']},
            'target_server':{'vm_id':self.state['target_id'],'name':self.state['target_name'],
                'disks':disks,'volume_groups':data['volume_groups'],'btrfs_list':data['btrfs_list']},
            'migration_ip':self.state['target_ip'],'region_id':'cn-north-4','region_name':'华北-北京四',
            'project_id':self.cloud.pid,'project_name':'cn-north-4','use_public_ip':False,'use_ipv6':False,
            'exist_server':True,'auto_start':False,'syncing':continuous,'start_target_server':not continuous,
            'start_network_check':False,'is_need_consistency_check':False,'need_migration_test':False}
        from huaweicloudsdksms.v3 import CreateTaskRequest
        result = self.client.create_task(CreateTaskRequest(body=body)).to_dict()
        self.state['task_id'] = result['id'];self.state['continuous_sync']=continuous;self.save()
        self.event('已创建 SMS 私网主机迁移任务；'+('启用持续同步' if continuous else '源端停写，全量后自动启动目标机'))
        return result

    def task_action(self, operation):
        if operation not in ('start','stop','cutover'): raise ValueError('Unsupported SMS operation')
        if operation == 'cutover' and not self.state.get('frozen_at'):
            raise ValueError('Freeze source writes before cutover')
        task = self.client.show_task(ShowTaskRequest(task_id=self.state['task_id']))
        if task.name != self.state['task_name'] or task.target_server.vm_id != self.state['target_id']:
            raise ValueError('SMS task ownership changed')
        result = self.client.update_task_status(UpdateTaskStatusRequest(task_id=self.state['task_id'],
            body=UpdateTaskStatusReq(operation=operation)))
        self.event('SMS operation accepted: '+operation)
        return {'operation':operation,'status_code':result.status_code}

    def freeze(self):
        ssh = self.cloud.ssh()
        script = '''import os,signal,json,subprocess,urllib.request
from pathlib import Path
stopped=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  args=(p/'cmdline').read_bytes().split(b'\\0')
  if args[:3]==[b'python3',b'order_service.py',b'write'] and os.readlink(str(p/'cwd'))=='/opt/sms-migration-lab':
   os.kill(int(p.name),signal.SIGTERM);stopped.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
subprocess.run(['python3','/opt/sms-migration-lab/order_service.py','checkpoint'],check=True)
with urllib.request.urlopen('http://127.0.0.1:8080/health') as r:health=json.load(r)
print(json.dumps({'stopped':stopped,'health':health}))
'''
        try:
            inp,out,err = ssh.exec_command('python3 -',timeout=60)
            inp.write(script);inp.channel.shutdown_write()
            result = json.loads(out.read())
            if out.channel.recv_exit_status(): raise RuntimeError('Source freeze failed')
        finally: ssh.close()
        self.state.update(source_health=result['health'],frozen_at=time.time())
        self.event('源端已停写并检查数据库；最终订单数 '+str(result['health']['orders']))
        return result

    def validate(self):
        import paramiko
        if not self.state.get('frozen_at'): raise ValueError('Freeze source writes before final validation')
        c = self.cloud
        target = c.ecs.show_server(ShowServerRequest(server_id=self.state['target_id'])).server
        if target.name != self.state['target_name'] or target.status != 'ACTIVE':
            raise ValueError('Target ownership/status invalid')
        jump = c.ssh(); ssh = paramiko.SSHClient()
        known = c.runtime/'sms-known-hosts'
        if known.exists(): ssh.load_host_keys(str(known))
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy() if known.exists() else paramiko.AutoAddPolicy())
        try:
            sock = jump.get_transport().open_channel('direct-tcpip',(self.state['target_ip'],22),('127.0.0.1',0))
            ssh.connect(self.state['target_ip'],username='root',password=c.state['resources']['password'],
                sock=sock,timeout=15,auth_timeout=15,allow_agent=False,look_for_keys=False)
            if not known.exists(): ssh.save_host_keys(str(known));known.chmod(0o600)
            script = '''import hashlib,json,subprocess,urllib.request
from pathlib import Path
with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=5) as r:health=json.load(r)
h=hashlib.sha256()
with open('/opt/sms-migration-lab/payload.bin','rb') as f:
 for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
health['actual_payload_sha256']=h.hexdigest()
health['systemd_active']=subprocess.check_output(['systemctl','is-active','sms-orders.service'],text=True).strip()
health['systemd_enabled']=subprocess.check_output(['systemctl','is-enabled','sms-orders.service'],text=True).strip()
health['sqlite_integrity']=subprocess.check_output(['python3','-c',"import sqlite3;print(sqlite3.connect('/opt/sms-migration-lab/orders.sqlite').execute('PRAGMA integrity_check').fetchone()[0])"],text=True).strip()
print(json.dumps(health))
'''
            inp,out,err = ssh.exec_command('python3 -',timeout=120)
            inp.write(script);inp.channel.shutdown_write()
            health = json.loads(out.read())
            if out.channel.recv_exit_status(): raise RuntimeError('Target health verification failed')
        finally: ssh.close();jump.close()
        src = self.state['source_health']
        checks = {'distinct_instances': src['instance_id'] != health['instance_id'] == self.state['target_id'],
            'distinct_boots':src['boot_id'] != health['boot_id'],
            'orders_equal':src['orders']==health['orders'] and src['orders_sha256']==health['orders_sha256'],
            'file_sha256_equal':src['payload_sha256']==health['actual_payload_sha256'],
            'app_started_at_boot':health['systemd_active']=='active' and health['systemd_enabled']=='enabled',
            'database_integrity':health['sqlite_integrity']=='ok',
            'generated_orders_preserved':health['orders']>10000}
        self.state.update(target_health=health,validation={'checks':checks,'passed':all(checks.values()),
            'verified_at':time.time()})
        self.event('目标主机独立启动、订单与文件验收：'+('通过' if all(checks.values()) else '未通过'))
        return self.state['validation']

    def orders(self, side=None):
        side = side or self.state.get('active_side','source')
        if side not in ('source','target'): raise ValueError('Unknown order service')
        if side == 'target' and not self.state.get('validation',{}).get('passed'):
            raise ValueError('Target has not passed migration validation')
        import ipaddress
        ip = self.state[side+'_ip']
        if ipaddress.ip_address(ip) not in ipaddress.ip_network('10.78.1.0/24'):
            raise ValueError('Service address outside the dedicated subnet')
        ssh = self.cloud.ssh()
        try:
            inp,out,err = ssh.exec_command('curl -fsS --connect-timeout 5 --max-time 10 http://'+ip+':8080/orders',timeout=20)
            result = json.loads(out.read())
            if out.channel.recv_exit_status(): raise RuntimeError('Order service unavailable')
        finally: ssh.close()
        if result.get('synthetic') is not True: raise ValueError('Expected synthetic order application')
        return {'side':side,'ip':ip,**result}

    def route(self, side):
        result = self.orders(side)
        self.state['active_side'] = side
        self.event('演示访问路由切至 '+side+'；实际读取该主机订单接口（未修改 DNS / ELB）')
        return result

    def cleanup_snapshots(self):
        c = self.cloud
        for sid in list(self.state.get('snapshot_ids',[])):
            path = f'/v2/{c.pid}/snapshots/{sid}'
            for _ in range(60):
                actual = c.api('evs',path,allow_missing=True)
                if actual is None: break
                snapshot = actual['snapshot']
                if snapshot['volume_id'] != self.state.get('target_root_volume_id'):
                    raise ValueError('Snapshot does not belong to the dedicated target disk')
                if snapshot['status'] == 'available': c.api('evs',path,'DELETE',allow_missing=True)
                elif snapshot['status'] != 'deleting': raise ValueError('Snapshot is not deletable')
                time.sleep(2)
            else: raise TimeoutError('Snapshot deletion not confirmed')
            self.state['snapshot_ids'].remove(sid);self.save()

    def release(self, confirmation):
        if confirmation != self.state['demo_id']:
            raise ValueError('Full Demo ID confirmation required')
        c = self.cloud
        def remove(key):
            self.state.pop(key, None); self.save()
        if self.state.get('task_id'):
            tid = self.state['task_id']
            try:
                task = self.client.show_task(ShowTaskRequest(task_id=tid))
                if task.name != self.state['task_name']:
                    raise ValueError('SMS task ownership changed')
                if task.target_server.vm_id != self.state.get('target_id'):
                    raise ValueError('SMS target ownership changed')
                if task.target_server.image_disk_id:
                    self.state['image_disk_id'] = task.target_server.image_disk_id; self.save()
                if task.target_server.cutovered_snapshot_ids:
                    self.state['snapshot_ids'] = list(set(self.state.get('snapshot_ids',[]) +
                        task.target_server.cutovered_snapshot_ids.split(',')))
                    self.save()
                terminal = ('READY','MIGRATE_SUCCESS','SYNC_SUCCESS','MIGRATE_FAIL','SYNC_FAIL','ABORT')
                if task.state not in terminal:
                    self.client.update_task_status(UpdateTaskStatusRequest(task_id=tid,
                        body=UpdateTaskStatusReq(operation='stop')))
                    for _ in range(60):
                        current = self.client.show_task(ShowTaskRequest(task_id=tid))
                        if current.state in terminal: break
                        time.sleep(2)
                    else: raise TimeoutError('SMS task has not stopped')
                self.client.delete_task(DeleteTaskRequest(task_id=tid))
                for _ in range(60):
                    try: self.client.show_task(ShowTaskRequest(task_id=tid))
                    except ClientRequestException as exc:
                        if exc.status_code == 404: break
                        raise
                    time.sleep(2)
                else: raise TimeoutError('SMS task deletion not confirmed')
            except ClientRequestException as exc:
                if exc.status_code != 404: raise
            remove('task_id')
        if self.state.get('source_sms_id'):
            sid = self.state['source_sms_id']
            try:
                source = self.client.show_server(SmsShowServerRequest(source_id=sid))
                if source.name != self.state['demo_id']:
                    raise ValueError('SMS source ownership changed')
                self.client.delete_server(SmsDeleteServerRequest(source_id=sid))
            except ClientRequestException as exc:
                if exc.status_code != 404: raise
            remove('source_sms_id')
        self.cleanup_snapshots()
        if self.state.get('target_id'):
            sid = self.state['target_id']
            try:
                server = c.ecs.show_server(ShowServerRequest(server_id=sid)).server
                if server.name != self.state['target_name']:
                    raise ValueError('Target ECS ownership changed')
                attached = {v.id for v in server.os_extended_volumesvolumes_attached}
                owned = {self.state.get('target_root_volume_id'),self.state.get('image_disk_id')}
                if not attached.issubset(owned):
                    raise ValueError('Target has an unrecognized disk; refusing deletion')
                self.state['target_volume_ids'] = list(attached)
                self.save()
                c.ecs.delete_servers(DeleteServersRequest(body=DeleteServersRequestBody(
                    servers=[ServerId(id=sid)], delete_publicip=False, delete_volume=True)))
                for _ in range(60):
                    try: c.ecs.show_server(ShowServerRequest(server_id=sid))
                    except ClientRequestException as exc:
                        if exc.status_code == 404: break
                        raise
                    time.sleep(2)
                else: raise TimeoutError('Target ECS deletion not confirmed')
            except ClientRequestException as exc:
                if exc.status_code != 404: raise
            remove('target_id')
        volumes = set(self.state.get('target_volume_ids',[]))
        if self.state.get('target_root_volume_id'): volumes.add(self.state['target_root_volume_id'])
        if self.state.get('image_disk_id'): volumes.add(self.state['image_disk_id'])
        if self.state.get('old_image_disk_id'): volumes.add(self.state['old_image_disk_id'])
        for vid in list(volumes):
            path = f'/v2/{c.pid}/volumes/{vid}'
            for _ in range(40):
                actual = c.api('evs',path,allow_missing=True)
                if actual is None: break
                volume = actual['volume']
                if volume['attachments']: raise ValueError('Refusing to delete an attached SMS disk')
                if volume['status'] == 'available': c.api('evs',path,'DELETE',allow_missing=True)
                elif volume['status'] != 'deleting': raise ValueError('SMS disk not deletable')
                time.sleep(2)
            else: raise TimeoutError('SMS disk deletion not confirmed')
            volumes.remove(vid); self.state['target_volume_ids'] = list(volumes)
            for key in ('target_root_volume_id','image_disk_id','old_image_disk_id'):
                if self.state.get(key) == vid: self.state.pop(key)
            self.save()
        if self.state.get('target_sg_id'):
            path = f'/v1/{c.pid}/security-groups/{self.state["target_sg_id"]}'
            actual = c.api('vpc',path,allow_missing=True)
            if actual:
                if actual['security_group']['name'] != self.state['target_name'] + '-sg':
                    raise ValueError('Target security group ownership changed')
                c.api('vpc',path,'DELETE',allow_missing=True)
            remove('target_sg_id')
        self.state['released'] = True; self.save()
        return {'sms_released':True}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['provision-target', 'target-ready','create-task','start','stop','cutover','freeze','validate','status','release'])
    parser.add_argument('--confirm')
    parser.add_argument('--cold',action='store_true')
    args = parser.parse_args()
    lab = SmsLab()
    if args.action == 'provision-target': result = lab.provision_target()
    elif args.action == 'target-ready': result = lab.target_ready()
    elif args.action == 'release': result = lab.release(args.confirm)
    elif args.action == 'create-task': result = lab.create_task(continuous=not args.cold)
    elif args.action in ('start','stop','cutover'): result = lab.task_action(args.action)
    elif args.action == 'freeze': result = lab.freeze()
    elif args.action == 'validate': result = lab.validate()
    else: result = lab.observe()
    print(json.dumps(result,ensure_ascii=False))
