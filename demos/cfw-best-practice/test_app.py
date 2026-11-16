import json
from pathlib import Path
import re
import tempfile
import unittest

from app import PLAN, create_app
from cloud import Cloud, estimate


class PreviewSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cloud = Cloud(self.temp.name)
        self.app = create_app(self.cloud)
        self.client = self.app.test_client()
        page = self.client.get('/', base_url='http://127.0.0.1:8902').get_data(as_text=True)
        self.token = re.search(r'name="demo-token" content="([^"]+)"', page)[1]

    def get(self, path):
        return self.client.get(path, base_url='http://127.0.0.1:8902')

    def post(self, path, **kwargs):
        return self.client.post(path, base_url='http://127.0.0.1:8902', **kwargs)

    def test_missing_snapshot_is_unknown_not_supported(self):
        status = self.get('/api/status').get_json()
        self.assertIsNone(status['account']['postpaid_supported'])
        self.assertFalse(status['deployment_enabled'])
        self.assertEqual(status['tests_executed'], 0)
        self.assertEqual(status['logs'], [])

    def test_no_cloud_write_even_with_valid_token_and_eligible_account(self):
        self.cloud.path.write_text(json.dumps({'connected': True, 'postpaid_supported': True}))
        response = self.post('/api/execute', json={'id': 'provision'}, headers={'X-Demo-Token': self.token})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.get('/api/status').get_json()['resources_created'], 0)

    def test_external_host_origin_and_missing_token_rejected(self):
        self.assertEqual(self.client.get('/', base_url='http://evil.example:8902').status_code, 403)
        self.assertEqual(self.post('/api/preflight').status_code, 403)
        self.assertEqual(self.post('/api/preflight', headers={'Origin': 'https://evil.example', 'X-Demo-Token': self.token}).status_code, 403)

    def test_snapshot_and_export_do_not_leak_raw_fields(self):
        self.cloud.path.write_text(json.dumps({'connected': True, 'postpaid_supported': False, 'firewall_count': 0, 'secret': 'PRIVATE_TEST_SENTINEL', 'project_id': 'PRIVATE_PROJECT'}))
        for path in ('/api/status', '/api/export'):
            data = self.get(path)
            self.assertNotIn('PRIVATE_', data.get_data(as_text=True))
        exported = self.get('/api/export').get_json()
        self.assertEqual(exported['measurements'], [])
        self.assertIn('非实测', exported['document_type'])

    def test_budget_math_matches_approved_scope(self):
        result = estimate(PLAN)
        self.assertEqual(result, {'hourly_cny': 3.1592, 'total_cny': 7.4784})
        self.assertLess(result['total_cny'], PLAN['budget_cny'])

    def test_preflight_failure_does_not_echo_credentials(self):
        def fail():
            raise RuntimeError('PRIVATE_CREDENTIAL')
        self.cloud.preflight = fail
        response = self.post('/api/preflight', headers={'X-Demo-Token': self.token})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('PRIVATE_CREDENTIAL', response.get_data(as_text=True))

    def test_plan_has_no_unexecuted_measurements(self):
        self.assertEqual(len(PLAN['scenarios']), 4)
        self.assertTrue(all(len(s['stages']) == 4 and s['acceptance'] for s in PLAN['scenarios']))
        svg = (Path(__file__).parent / 'architecture.svg').read_text()
        self.assertIn('data:image/svg+xml;base64,', svg)
        self.assertNotIn('http://127.0.0.1', svg)


if __name__ == '__main__':
    unittest.main()
