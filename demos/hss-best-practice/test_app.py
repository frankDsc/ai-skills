"""Isolated HTTP boundary tests. These doubles are not used by the live demo."""
import re
import unittest
from unittest.mock import Mock

from app import create_app
from cloud import Cloud


class AppTests(unittest.TestCase):
    def setUp(self):
        self.cloud=Mock()
        self.cloud.project_id='test-project'
        self.cloud.state={'demo_id':'test-owned-demo','plan':{},'resources':{},'checks':{}}
        self.cloud.snapshot.return_value={'connected':True,'host':{'agent_status':'not_installed','protect_status':'closed'}}
        self.cloud.events.return_value={'events':[],'total':0}
        self.client=create_app(self.cloud).test_client()
        self.base='http://localhost:8899'
        html=self.client.get('/',base_url=self.base).get_data(as_text=True)
        self.token=re.search(r'name="demo-token" content="([^"]+)"',html)[1]

    def post(self,payload,**headers):
        return self.client.post('/api/execute',base_url=self.base,json=payload,headers={'X-Demo-Token':self.token,**headers})

    def test_no_token_cannot_start_cloud_operation(self):
        response=self.client.post('/api/execute',base_url=self.base,json={'id':'provision'})
        self.assertEqual(response.status_code,403)
        self.cloud.provision.assert_not_called()

    def test_unknown_host_and_cross_origin_rejected(self):
        self.assertEqual(self.client.get('/api/status',base_url='http://evil.example:8899').status_code,403)
        self.assertEqual(self.post({'id':'provision'},Origin='https://evil.example').status_code,403)
        self.cloud.provision.assert_not_called()

    def test_only_known_actions_allowed(self):
        self.assertEqual(self.post({'id':'shell','cmd':'uname -a'}).status_code,400)
        self.assertEqual(self.post({'id':['provision']}).status_code,400)
        self.assertEqual(self.post(['provision']).status_code,400)

    def test_cleanup_requires_exact_owned_demo_id(self):
        self.assertEqual(self.post({'id':'cleanup','confirmation':'wrong'}).status_code,400)
        self.cloud.cleanup.assert_not_called()

    def test_real_status_is_not_replaced_by_green_defaults(self):
        data=self.client.get('/api/status',base_url=self.base).get_json()
        self.assertEqual(data['host']['protect_status'],'closed')
        self.assertEqual(data['host']['agent_status'],'not_installed')

    def test_events_error_not_reported_as_no_incidents(self):
        self.cloud.events.side_effect=RuntimeError('permission denied')
        response=self.client.get('/api/events',base_url=self.base)
        self.assertEqual(response.status_code,502)
        self.assertIn('error',response.get_json())

    def test_empty_demo_does_not_contact_other_hosts(self):
        cloud=Cloud.__new__(Cloud)
        cloud.state={'resources':{}}
        cloud.project_id='test-project'
        cloud.hss=Mock()
        self.assertEqual(cloud.events(),{'events':[],'total':0})
        cloud.hss.list_security_events.assert_not_called()

    def test_acknowledgement_requires_artifact_cleanup(self):
        cloud=Cloud.__new__(Cloud)
        cloud.state={'checks':{'artifacts_clean':False}}
        cloud.hss=Mock()
        with self.assertRaises(ValueError):cloud.acknowledge()
        cloud.hss.change_event.assert_not_called()


if __name__=='__main__':unittest.main()
