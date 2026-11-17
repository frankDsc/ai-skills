from copy import deepcopy
from types import SimpleNamespace
import unittest
import json
from pathlib import Path
import tempfile
import threading
import os
import subprocess
import sys
from unittest.mock import patch
from live import Lab, owned_firewall, matches_deny


class LiveSafetyTests(unittest.TestCase):
    def test_new_round_uses_explicit_private_runtime_without_touching_old_state(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'-c','import live; print(live.RUNTIME)'],env={**os.environ,'CFW_DEMO_RUNTIME':directory},capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.strip(),directory)
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_already_bound_eip_is_verified_without_rebinding(self):
        lab=Lab.__new__(Lab);lab.pid='pid';lab.guard_active=lambda:None;lab.write=lambda:None
        lab.state={'demo_id':'lab','checks':{},'resources':{role:{'server_id':role,'port_id':role+'-port','eip_id':role+'-eip','public_ip':ip,'peer_rule_id':'rule'} for role,ip in [('probe','192.0.2.1'),('business','198.51.100.2')]}}
        lab.server=lambda role:SimpleNamespace(status='ACTIVE',to_dict=lambda:{'os_extended_volumesvolumes_attached':[{'id':role+'-disk','boot_index':0}]})
        calls=[]
        def api(service,path,method='GET',*args,**kwargs):
            calls.append(method);role=path.rsplit('/',1)[1].removesuffix('-eip')
            return {'publicip':{'public_ip_address':lab.state['resources'][role]['public_ip'],'port_id':role+'-port'}}
        lab.api=api
        self.assertEqual(lab.bind_hosts(),{'hosts_ready':True})
        self.assertEqual(calls,['GET','GET'])
        lab.api=lambda *args,**kwargs:{'publicip':{'public_ip_address':'192.0.2.1','port_id':'foreign'}}
        with self.assertRaises(ValueError):lab.bind_hosts()

    def test_firewall_name_and_postpaid_ownership_required(self):
        self.assertTrue(owned_firewall({'fw_instance_name':'lab','charge_mode':1},'lab'))
        self.assertFalse(owned_firewall({'fw_instance_name':'lab','charge_mode':0},'lab'))
        self.assertFalse(owned_firewall({'fw_instance_name':'other','charge_mode':1},'lab'))

    def test_foreign_server_cannot_be_used_or_deleted(self):
        lab = Lab.__new__(Lab)
        lab.state = {'demo_id':'lab','resources':{'probe':{'server_id':'id'}}}
        lab.ecs = SimpleNamespace(show_server=lambda r: SimpleNamespace(server=SimpleNamespace(name='production',status='ACTIVE')))
        with self.assertRaises(ValueError): lab.server('probe')
        with self.assertRaises(ValueError): lab.cleanup_host('probe')

    def test_deadline_blocks_more_paid_actions(self):
        lab = Lab.__new__(Lab);lab.state = {'released':False,'cleanup_due_at':1}
        with self.assertRaises(ValueError):lab.guard_active()

    def test_dedicated_bandwidth_waits_for_eip_auto_release(self):
        lab=Lab.__new__(Lab);lab.pid='pid';lab.state={'demo_id':'lab','resources':{'probe':{'bandwidth_id':'bw'}}};lab.write=lambda:None
        calls=[]
        def api(*args,**kwargs):
            calls.append(args)
            return {'bandwidth':{'name':'lab-probe-bw','publicip_info':[],'share_type':'PER'}}
        lab.api=api
        self.assertFalse(lab.cleanup_host('probe'))
        self.assertTrue(all(len(a)<3 or a[2]!='DELETE' for a in calls))
        self.assertEqual(lab.state['resources']['probe']['bandwidth_id'],'bw')
        lab.api=lambda *args,**kwargs:None
        self.assertTrue(lab.cleanup_host('probe'))
        self.assertNotIn('probe',lab.state['resources'])

    def test_completed_cleanup_does_not_look_up_or_delete_new_resources(self):
        lab=Lab.__new__(Lab);lab.state={'released':True,'resources':{}}
        def unexpected():raise AssertionError('completed cleanup must not query a new resource')
        lab.firewall=unexpected
        self.assertEqual(lab.cleanup(),{'released':True})

    def test_five_tuple_rule_action_and_time_all_required(self):
        sample={'src_ip':'192.0.2.1','dst_ip':'198.51.100.2','src_port':45001,'dst_port':8080,'started_at':1794830000000,'finished_at':1794830004000}
        run={'deny_rule_id':'unique','measurements':{'deny':[sample]}}
        log={**sample,'rule_id':'unique','action':'deny','protocol':'TCP','hit_time':1794830002000}
        self.assertTrue(matches_deny(run,log))
        decorated=deepcopy(log);decorated['src_ip']='192.0.2.1(Hong Kong)'
        self.assertTrue(matches_deny(run,decorated))
        for k,v in [('src_ip','192.0.2.9'),('dst_ip','198.51.100.9'),('src_port',45002),('dst_port',22),('rule_id','other'),('action','permit'),('protocol','UDP'),('hit_time',1794831000000)]:
            changed=deepcopy(log);changed[k]=v
            self.assertFalse(matches_deny(run,changed),k)
        self.assertFalse(matches_deny(run,{}))

    def test_live_dashboard_never_returns_credentials_or_account_ids(self):
        from live_service import LiveService
        from app import PLAN
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            state={'demo_id':'lab','region':'ap-southeast-1','resources':{'firewall_id':'fw','probe':{'server_id':'server','password':'PRIVATE_PASSWORD','tls_token':'PRIVATE_TOKEN'}},'checks':{},'runs':[],'journal':[]}
            (root/'live-state.json').write_text(json.dumps(state))
            (root/'hongkong-plan.json').write_text(json.dumps({'region':'ap-southeast-1','rates':PLAN['rates'],'project_id':'PRIVATE_PROJECT'}))
            (root/'live-cloud.json').write_text(json.dumps({'project_id':'PRIVATE_PROJECT','eip':{'status':0,'domain_id':'PRIVATE_DOMAIN'}}))
            (root/'billing-summary.json').write_text(json.dumps({'demo_id':'lab','amount':'1.23','currency':'CNY','account_id':'PRIVATE_BILLING'}))
            service=LiveService.__new__(LiveService);service.jobs=[];service.mutex=threading.Lock()
            with patch('live_service.RUNTIME',root):result=service.snapshot(PLAN)
            self.assertNotIn('PRIVATE_',json.dumps(result))
            self.assertEqual(result['cloud']['eip']['status'],0)
            self.assertEqual(result['billing_summary']['amount'],'1.23')
            (root/'billing-summary.json').write_text(json.dumps({'demo_id':'different-lab','amount':'9.99'}))
            with patch('live_service.RUNTIME',root):self.assertEqual(service.snapshot(PLAN)['billing_summary'],{})


if __name__ == '__main__':unittest.main()
