"""Catalog, command boundaries and evidence correlation; no cloud calls."""
import unittest
from scenarios import SCENARIOS,command_for,get_scenario,match_events,CLEANUP_COMMAND


class ScenarioTests(unittest.TestCase):
    def test_ten_unique_scenarios_with_official_evidence(self):
        self.assertEqual(len(SCENARIOS),10)
        self.assertEqual(len({s['id'] for s in SCENARIOS}),10)
        for s in SCENARIOS:
            self.assertTrue(s['source'].startswith('https://support.huaweicloud.com/'))
            self.assertTrue(s['event_classes'] or s['event_types'])

    def test_remote_scripts_compile_and_have_bounded_tokens(self):
        for s in SCENARIOS:
            command=command_for(s['id'],'a012345678')
            compile(command.split('\n',1)[1].rsplit('\n',1)[0],s['id'],'exec')
        compile(CLEANUP_COMMAND.split('\n',1)[1].rsplit('\n',1)[0],'cleanup','exec')
        for ident in ['; uname -a',None,[],{'id':'suid'}]:
            with self.assertRaises(ValueError):get_scenario(ident)
        for token in ['../etc','abc;id','123','abcdef0123\n']:
            with self.assertRaises(ValueError):command_for('suid',token)

    def test_no_external_scan_target_or_shell_binding(self):
        scan=command_for('port_scan','a012345678')
        self.assertIn("'127.0.0.1'",scan)
        self.assertIn("'--host-timeout','8s'",scan)
        netcat=command_for('netcat','a012345678')
        self.assertNotIn("'-e'",netcat)
        self.assertNotIn('/dev/tcp',netcat)

    def test_only_new_same_scenario_events_match(self):
        run={'scenario_id':'suid','started_at':2000,'baseline_event_ids':['old']}
        events=[
            {'event_id':'old','occur_time':3000,'event_type':3002},
            {'event_id':'too-early','occur_time':1999,'event_type':3002},
            {'event_id':'wrong-type','occur_time':3000,'event_type':3018},
            {'event_id':'valid','occur_time':3000,'event_type':3002},
        ]
        self.assertEqual([e['event_id'] for e in match_events(run,events)],['valid'])
        run['scenario_id']='shell_copy'
        self.assertEqual([e['event_id'] for e in match_events(run,events)],['wrong-type'])

    def test_names_are_not_used_to_fabricate_a_match(self):
        run={'scenario_id':'suid','started_at':1000}
        event={'event_id':'arbitrary','occur_time':2000,'event_name':'File Privilege Escalation','event_type':4004}
        self.assertEqual(match_events(run,[event]),[])

    def test_hss_second_precision_and_scan_category(self):
        run={'scenario_id':'port_scan','started_at':2345,'baseline_event_ids':['old']}
        events=[{'event_id':'scan','occur_time':2000,'event_type':6003,'event_class_id':'hips_0011'},
                {'event_id':'old','occur_time':2000,'event_type':6003},
                {'event_id':'before','occur_time':1000,'event_type':6003}]
        self.assertEqual([e['event_id'] for e in match_events(run,events)],['scan'])


if __name__=='__main__':unittest.main()
