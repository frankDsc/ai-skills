"""Content integrity and cutover/rollback guards, with isolated synthetic data."""
import re
import tempfile
import unittest
from pathlib import Path

from app import create_app
from engine import Lab


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab=Lab(self.temp.name)

    def run_ok(self,*actions):
        for action in actions:
            result=self.lab.execute(action)
            self.assertTrue(result['ok'],result)

    def test_full_incremental_and_rollback(self):
        self.run_ok('prepare','full','change')
        self.assertEqual(self.lab.compare()['row_diff'],40)
        self.assertEqual(self.lab.compare()['file_diff'],3)
        self.assertFalse(self.lab.execute('cutover')['ok'])
        self.run_ok('sync')
        self.assertEqual(len(self.lab.rows('target')),1220)
        self.assertTrue(self.lab.compare()['consistent'])
        self.run_ok('verify')
        self.assertFalse(self.lab.snapshot()['gate_passed'])
        self.run_ok('freeze','verify','cutover','rollback')
        self.assertEqual(self.lab.state['active'],'source')
        self.assertFalse(self.lab.state['frozen'])
        self.assertFalse(Lab(self.temp.name).snapshot()['gate_passed'])

    def test_corruption_invalidates_cutover(self):
        self.run_ok('prepare','full','freeze','verify')
        (Path(self.temp.name)/'target/objects/attachment-00.txt').write_text('corrupted')
        self.assertFalse(self.lab.snapshot()['gate_passed'])
        self.assertFalse(self.lab.execute('cutover')['ok'])
        self.run_ok('sync','verify','cutover','target_write')
        self.assertFalse(self.lab.execute('rollback')['ok'])
        self.assertEqual(self.lab.state['active'],'target')
        self.assertEqual(len(self.lab.rows('target')),1201)

    def test_freeze_and_duplicate_prepare_guards(self):
        self.run_ok('prepare','full','freeze')
        self.assertFalse(self.lab.execute('change')['ok'])
        self.assertFalse(self.lab.execute('prepare')['ok'])
        self.assertEqual(len(self.lab.rows('source')),1200)

    def test_http_boundary_and_action_whitelist(self):
        lab=self.lab
        class LocalRunner:
            host=None
            def call(self,action):
                return lab.snapshot() if action=='status' else lab.execute(action)
        client=create_app(LocalRunner()).test_client()
        host='http://127.0.0.1:8901'
        self.assertEqual(client.get('/api/status',base_url='http://attacker.invalid').status_code,403)
        self.assertEqual(client.post('/api/execute',base_url=host,json={'id':'prepare'}).status_code,403)
        html=client.get('/',base_url=host).text
        token=re.search(r'name="demo-token" content="([^"]+)"',html).group(1)
        headers={'X-Demo-Token':token,'Origin':host}
        self.assertEqual(client.post('/api/execute',base_url=host,json={'id':'__dict__'},headers=headers).status_code,400)
        self.assertEqual(client.post('/api/execute',base_url=host,json=['prepare'],headers=headers).status_code,400)
        self.assertEqual(client.post('/api/execute',base_url=host,json={'id':'prepare'},headers={**headers,'Origin':'https://evil.invalid'}).status_code,403)
        self.assertEqual(client.post('/api/execute',base_url=host,json={'id':'prepare'},headers=headers).status_code,200)
        self.assertEqual(client.get('/api/status',base_url=host).json['source_orders'],1200)


if __name__=='__main__':
    unittest.main()
