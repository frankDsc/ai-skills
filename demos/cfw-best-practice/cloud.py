"""Read-only account capability checks. This preview has no cloud mutation path."""
import csv
import json
import os
from pathlib import Path
import time

REGION = 'cn-north-4'
DEFAULT_RUNTIME = Path.home() / '.local/state/cfw-best-practice-lab'


def estimate(plan):
    r = plan['rates']
    hourly = r['cfw_hour'] + 2 * (r['ecs_hour'] + r['disk_hour'] + r['eip_hour'])
    total = hourly * plan['hours'] + r['cfw_gb'] * plan['cfw_gb'] + r['egress_gb'] * plan['egress_gb']
    return {'hourly_cny': round(hourly, 4), 'total_cny': round(total, 4)}


class Cloud:
    def __init__(self, runtime=None):
        self.runtime = Path(runtime or os.environ.get('CFW_DEMO_RUNTIME', DEFAULT_RUNTIME))
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.runtime / 'account-check.json'

    def snapshot(self):
        if not self.path.exists():
            return {'checked_at': None, 'connected': False, 'postpaid_supported': None, 'firewall_count': None}
        # Only this allowlist may enter the browser; no raw account response/IDs.
        d = json.loads(self.path.read_text())
        return {k: d.get(k) for k in ('checked_at', 'connected', 'postpaid_supported', 'firewall_count', 'region')}

    def preflight(self):
        from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
        from huaweicloudsdkcore.http.http_config import HttpConfig
        from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
        from huaweicloudsdkcfw.v1 import CfwClient, ListFirewallListRequest, QueryFireWallInstanceDto

        path = Path(os.environ.get('HWC_CREDENTIALS_CSV', str(Path.home() / 'Downloads/credentials.csv')))
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            raise ValueError('凭证文件需恰好包含一行')
        ak, sk = (rows[0].get(k, '').strip() for k in ('Access Key Id', 'Secret Access Key'))
        if not ak or not sk:
            raise ValueError('凭证文件缺少 AK/SK')
        config = HttpConfig.get_default_config()
        config.timeout = (10, 20)
        iam = IamClient.new_builder().with_credentials(GlobalCredentials(ak, sk)).with_http_config(config).with_endpoint('https://iam.myhuaweicloud.com').build()
        projects = iam.keystone_list_projects(KeystoneListProjectsRequest(name=REGION)).projects or []
        if not projects:
            raise ValueError('当前凭证无法访问北京四项目')
        client = CfwClient.new_builder().with_credentials(BasicCredentials(ak, sk).with_project_id(projects[0].id)).with_http_config(config).with_endpoint(f'https://cfw.{REGION}.myhuaweicloud.com').build()
        response = client.list_firewall_list(ListFirewallListRequest(body=QueryFireWallInstanceDto(limit=100, offset=0))).to_dict()
        data = response.get('data') or {}
        # Missing/unknown capability is not approval to purchase.
        result = {'checked_at': int(time.time() * 1000), 'connected': True, 'region': REGION,
                  'postpaid_supported': response.get('is_support_postpaid'), 'firewall_count': data.get('total')}
        temp = self.path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        os.replace(temp, self.path)
        return result
