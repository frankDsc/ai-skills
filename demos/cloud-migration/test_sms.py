"""SMS cleanup refuses changed ownership; these checks never access cloud APIs."""
from types import SimpleNamespace
import unittest
from sms_lab import SmsLab


class SmsBoundaryTests(unittest.TestCase):
    def lab(self):
        lab=SmsLab.__new__(SmsLab)
        lab.state={'demo_id':'migration-test','task_name':'sms-test','target_id':'target',
                   'target_name':'migration-test-sms-target','target_root_volume_id':'owned-root'}
        lab.save=lambda:None
        return lab

    def test_foreign_task_is_not_stopped_or_deleted(self):
        lab=self.lab();lab.state['task_id']='task'
        lab.cloud=SimpleNamespace()
        lab.client=SimpleNamespace(show_task=lambda _:SimpleNamespace(name='somebody-else'))
        with self.assertRaisesRegex(ValueError,'ownership'):lab.release('migration-test')
        self.assertEqual(lab.state['task_id'],'task')

    def test_unknown_disk_prevents_ecs_deletion(self):
        lab=self.lab()
        server=SimpleNamespace(name=lab.state['target_name'],status='ACTIVE',
            os_extended_volumesvolumes_attached=[SimpleNamespace(id='foreign-disk')])
        lab.cloud=SimpleNamespace(ecs=SimpleNamespace(show_server=lambda _:SimpleNamespace(server=server)))
        with self.assertRaisesRegex(ValueError,'unrecognized disk'):lab.release('migration-test')
        self.assertIn('target_id',lab.state)

    def test_unvalidated_target_cannot_receive_demo_traffic(self):
        lab=self.lab()
        with self.assertRaisesRegex(ValueError,'validation'):lab.orders('target')
        with self.assertRaisesRegex(ValueError,'Unknown'):lab.orders('external-host')
        with self.assertRaisesRegex(ValueError,'confirmation'):lab.release('wrong-id')

    def test_snapshot_with_foreign_parent_is_not_deleted(self):
        lab=self.lab();lab.state['snapshot_ids']=['snapshot'];calls=[]
        def api(service,path,method='GET',**kwargs):
            calls.append(method)
            return {'snapshot':{'volume_id':'foreign-volume','status':'available'}}
        lab.cloud=SimpleNamespace(pid='project',api=api)
        with self.assertRaisesRegex(ValueError,'dedicated target'):lab.cleanup_snapshots()
        self.assertEqual(calls,['GET'])
        self.assertEqual(lab.state['snapshot_ids'],['snapshot'])

    def test_deleted_target_tombstone_still_checks_disk_removal(self):
        lab=self.lab();calls=[]
        server=SimpleNamespace(name=lab.state['target_name'],status='DELETED')
        def api(service,path,**kwargs):
            calls.append(path);return None
        lab.cloud=SimpleNamespace(pid='project',api=api,
            ecs=SimpleNamespace(show_server=lambda _:SimpleNamespace(server=server)))
        self.assertTrue(lab.release('migration-test')['sms_released'])
        self.assertNotIn('target_id',lab.state)
        self.assertEqual(calls,['/v2/project/volumes/owned-root'])


if __name__=='__main__':unittest.main()
