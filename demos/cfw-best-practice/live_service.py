"""Local UI bridge: fixed asynchronous actions and real control-plane polling."""
import fcntl
import base64
import json
from pathlib import Path
import threading
import time
import uuid

from live import Lab, RUNTIME, save
from cloud import estimate


def ips_evidence(state):
    """Read-only evidence from the scoped backend IPS experiment; never expose packets."""
    path = RUNTIME/'ips-events.json'
    evidence = json.loads(path.read_text()) if path.exists() else {}
    if evidence.get('demo_id') != state['demo_id']: return []
    result = []
    for run in evidence.get('runs', []):
        name = run.get('name', '')
        if not name.startswith(state['demo_id']+'-ips-'): continue
        matched = []
        for log in run.get('logs', []):
            rule_id = run.get('rule', {}).get('ips_id')
            if not rule_id or log.get('attack_rule') != name or str(log.get('attack_rule_id')) != str(rule_id): continue
            try:
                packet = base64.b64decode(log.get('packet', ''), validate=True).decode('ascii')
                if not run.get('marker') or run['marker'] not in packet: continue
                if str(log.get('protocol')).upper() != 'TCP': continue
                for sample in run.get('measurements', []):
                    if (all(str(log.get(k, '')).split('(',1)[0] == str(sample.get(k)) for k in ('src_ip','dst_ip','src_port','dst_port'))
                        and sample['started_at']-5000 <= log['event_time'] <= sample['finished_at']+5000):
                        matched.append(log); break
            except (ValueError, TypeError, KeyError, UnicodeDecodeError): continue
        action = run.get('action_type')
        ms = run.get('measurements', [])
        normal = all(len(run.get(k, [])) == 3 and all(x.get('http_status') == 200 for x in run[k]) for k in ('baseline','restored'))
        behavior = len(ms) == 3 and action in (0,1) and all(x.get('http_status') == 200 if action == 0 else x.get('http_status') is None and bool(x.get('error')) for x in ms)
        logs = [{k:log.get(k) for k in ('event_time','action','attack_rule','attack_rule_id','level','src_ip','dst_ip','src_port','dst_port','log_id')} for log in matched]
        passed = bool(normal and behavior and run.get('rule_removed') and any(log.get('action') == ('permit' if action == 0 else 'deny') for log in matched))
        result.append({'name':name, 'action_type':action, 'started_at':run.get('started_at'), 'status':'passed' if passed else 'awaiting_verification',
                       'request_count':len(ms), 'http_200_count':sum(x.get('http_status') == 200 for x in ms), 'rule_removed':run.get('rule_removed',False), 'logs':logs})
    return result


class LiveService:
    def __init__(self):
        self.jobs = []
        self.mutex = threading.Lock()
        threading.Thread(target=self.poll, daemon=True).start()

    def state(self):
        return json.loads((RUNTIME/'live-state.json').read_text())

    def plan(self, base):
        private = json.loads((RUNTIME/'hongkong-plan.json').read_text())
        return {**base, 'region': private['region'], 'rates': private['rates'], 'quote_date': private.get('quoted_at',base['quote_date'])[:10]}

    def snapshot(self, base):
        state = self.state()
        cloud_file = RUNTIME/'live-cloud.json'
        raw = json.loads(cloud_file.read_text()) if cloud_file.exists() else {}
        cloud = {k:raw.get(k) for k in ('checked_at','firewall_status','charge_mode','version','ecs','rules','error') if k in raw}
        eip = raw.get('eip')
        if eip: cloud['eip'] = {k:eip.get(k) for k in ('id','public_ip','status','fw_instance_id')}
        resources = {}
        for k, v in state['resources'].items():
            if isinstance(v, dict):
                resources[k] = {a: v.get(a) for a in ('server_id','public_ip','eip_id','vpc_id','root_volume_id','workload_ready')}
            elif k == 'firewall_id': resources[k] = v
        count = int(bool(resources.get('firewall_id'))) + sum(sum(bool(v.get(k)) for k in ('vpc_id','subnet_id','sg_id','server_id','root_volume_id','eip_id','bandwidth_id')) for v in state['resources'].values() if isinstance(v,dict))
        proof_file = RUNTIME/'release-verification.json'
        proof = json.loads(proof_file.read_text()) if proof_file.exists() else {}
        verified = {k:proof.get(k) for k in ('checked_at','direct_checks')} if proof.get('demo_id') == state['demo_id'] else {}
        bill_file = RUNTIME/'billing-summary.json'
        bill = json.loads(bill_file.read_text()) if bill_file.exists() else {}
        billing = {k:bill.get(k) for k in ('checked_at','currency','amount','record_count','by_type')} if bill.get('demo_id') == state['demo_id'] else {}
        return {'mode': 'live', 'demo_id': state['demo_id'], 'region': state['region'], 'resources': resources,
                'resources_created': count, 'checks': state['checks'], 'runs': state['runs'], 'journal': state['journal'][:30],
                'cleanup_due_at': state.get('cleanup_due_at'), 'started_at': state.get('started_at'),
                'cleanup_scheduled': bool(state.get('cleanup_automation_id')) and not state.get('released'),
                'released': state.get('released',False), 'release_verification': verified, 'billing_summary': billing,
                'cloud': cloud, 'plan': self.plan(base), 'estimate': estimate(self.plan(base)), 'ips_events': ips_evidence(state),
                'busy': self.mutex.locked(), 'jobs': self.jobs[-20:], 'tests_executed': len(state['runs']),
                'logs': [record for run in state['runs'] for record in run.get('matched_logs',[])]}

    def execute(self, data):
        if not isinstance(data,dict): raise ValueError('请求必须是对象')
        action = data.get('id')
        if action not in ('exercise','refresh','restore','cleanup'): raise ValueError('未知固定动作')
        scenario = data.get('scenario_id')
        if action == 'exercise' and scenario not in ('ingress','egress','priority'): raise ValueError('该场景未接入真实执行器')
        if action == 'cleanup' and data.get('confirmation') != self.state()['demo_id']: raise ValueError('清理须确认完整 Demo ID')
        if not self.mutex.acquire(timeout=5): raise BlockingIOError('已有操作或云端查询进行中')
        fd = (RUNTIME/'action.lock').open('a')
        try: fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            fd.close(); self.mutex.release(); raise
        job = {'id': uuid.uuid4().hex[:8], 'action': action, 'scenario': scenario, 'status': 'running', 'started_at': int(time.time()*1000)}
        self.jobs.append(job)
        def run():
            try:
                lab = Lab()
                if action == 'exercise': result = lab.exercise(scenario)
                elif action == 'cleanup': result = lab.cleanup()
                elif action == 'restore':
                    for r in lab.rules():
                        if r.get('name','').startswith((lab.state['demo_id']+'-deny-', lab.state['demo_id']+'-broad-')): lab.delete_rule(r['rule_id'])
                    result = {'restored': True}
                else: result = lab.refresh_logs()
                job['status'] = 'success'
                job['result'] = {'run_id': result.get('id'), 'result_status': result.get('status'), 'released': result.get('released')}
            except Exception as e:
                job['status'] = 'error'; job['error'] = '云端动作未完成（'+type(e).__name__+'），请检查执行记录和实际状态。'
            finally:
                job['finished_at'] = int(time.time()*1000); fd.close(); self.mutex.release()
        threading.Thread(target=run,daemon=True).start()
        return job['id']

    def poll(self):
        while True:
            if self.mutex.acquire(blocking=False):
                try:
                    with (RUNTIME/'action.lock').open('a') as fd:
                        fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                        lab = Lab()
                        if not lab.state.get('released') and time.time()*1000 >= lab.state.get('cleanup_due_at', float('inf')):
                            lab.cleanup()
                        if not lab.state.get('released'):
                            fw = lab.firewall()
                            native = {'checked_at': int(time.time()*1000), 'firewall_status': (fw or {}).get('status'),
                                      'charge_mode': (fw or {}).get('charge_mode'), 'version': ((fw or {}).get('flavor') or {}).get('version'),
                                      'ecs': {}}
                            for role in ('probe','business'):
                                s = lab.server(role); native['ecs'][role] = s.status if s else None
                            if lab.state.get('object_id'):
                                eip = lab.eip()
                                native['eip'] = {k:eip.get(k) for k in ('id','public_ip','status','fw_instance_id')} if eip else None
                                native['rules'] = lab.rules()
                            if lab.state['runs']: lab.refresh_logs()
                            save(RUNTIME/'live-cloud.json',native)
                except BlockingIOError: pass
                except Exception:
                    path = RUNTIME/'live-cloud.json'
                    old = json.loads(path.read_text()) if path.exists() else {}
                    save(path,{**old,'error':'云端状态查询失败；显示上次核验快照，请留意时间。'})
                finally: self.mutex.release()
            time.sleep(15)
