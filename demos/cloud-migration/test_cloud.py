"""Cleanup trust-boundary checks; no network calls or resource mutations."""
from types import SimpleNamespace
import unittest
from cloud import Cloud


class CleanupTests(unittest.TestCase):
    def cloud(self,resources):
        c=Cloud.__new__(Cloud)
        c.state={'demo_id':'migration-test','resources':resources}
        c.pid='test-project';c.save=lambda:None
        return c

    def test_requires_exact_id_and_refuses_foreign_instance(self):
        c=self.cloud({'server_id':'test-server'})
        with self.assertRaises(ValueError):c.release('wrong')
        c.ecs=SimpleNamespace(show_server=lambda _:SimpleNamespace(server=SimpleNamespace(name='other-owner')))
        with self.assertRaisesRegex(ValueError,'不匹配'):c.release('migration-test')
        self.assertEqual(c.state['resources']['server_id'],'test-server')

    def test_refuses_foreign_network_and_keeps_failed_ids(self):
        c=self.cloud({'sg_id':'foreign-group'})
        calls=[]
        def api(service,path,method='GET',**kwargs):
            calls.append(method)
            return {'security_group':{'name':'somebody-else'}}
        c.api=api
        with self.assertRaises(ValueError):c.release('migration-test')
        self.assertEqual(calls,['GET'])
        self.assertEqual(c.state['resources']['sg_id'],'foreign-group')

    def test_network_deletion_order_and_persisted_removal(self):
        c=self.cloud({'sg_id':'sg','subnet_id':'subnet','vpc_id':'vpc'})
        names={'sg':('security_group','migration-test-sg'),
               'subnet':('subnet','migration-test-subnet'),'vpc':('vpc','migration-test')}
        removed=[];saved=[]
        c.save=lambda:saved.append(dict(c.state['resources']))
        def api(service,path,method='GET',**kwargs):
            key=path.rsplit('/',1)[-1]
            if method=='DELETE':removed.append(key);return {}
            field,name=names[key];return {field:{'name':name}}
        c.api=api
        self.assertTrue(c.release('migration-test')['released'])
        self.assertEqual(removed,['sg','subnet','vpc'])
        self.assertEqual(c.state['resources'],{})
        self.assertTrue(c.state['released'])
        self.assertGreaterEqual(len(saved),4)

    def test_in_use_root_disk_is_not_deleted(self):
        c=self.cloud({'root_volume_id':'owned-root'})
        calls=[]
        def api(service,path,method='GET',**kwargs):
            calls.append(method);return {'volume':{'status':'in-use'}}
        c.api=api
        with self.assertRaises(ValueError):c.release('migration-test')
        self.assertEqual(calls,['GET'])
        self.assertIn('root_volume_id',c.state['resources'])


if __name__=='__main__':unittest.main()
