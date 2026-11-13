"""Read-only Huawei IAM/ECS preflight; never copies credentials or identifiers to output."""
import csv
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
from huaweicloudsdkecs.v2 import EcsClient, NovaListServersRequest


def check():
    path=Path(os.environ.get('HWC_CREDENTIALS_CSV',str(Path.home()/'Downloads/credentials.csv')))
    with path.open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=1:
        raise ValueError('凭证文件应仅含一行')
    ak,sk=(rows[0].get(key,'').strip() for key in ('Access Key Id','Secret Access Key'))
    if not ak or not sk:
        raise ValueError('凭证文件格式无效')
    region='cn-north-4'
    iam=IamClient.new_builder().with_credentials(GlobalCredentials(ak,sk)).with_endpoint('https://iam.myhuaweicloud.com').build()
    projects=iam.keystone_list_projects(KeystoneListProjectsRequest(name=region)).projects or []
    if not projects:
        raise ValueError('没有可用的北京四项目')
    ecs=EcsClient.new_builder().with_credentials(BasicCredentials(ak,sk).with_project_id(projects[0].id)).with_endpoint(f'https://ecs.{region}.myhuaweicloud.com').build()
    response=ecs.nova_list_servers(NovaListServersRequest(limit=1))
    return {'api_connected':True,'region':region,'has_existing_ecs':bool(response.servers),
            'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'IAM 项目列表与 ECS 只读查询；未创建资源'}


if __name__=='__main__':
    try:
        result=check()
    except Exception as exc:
        result={'api_connected':False,'error_type':type(exc).__name__,
                'status_code':getattr(exc,'status_code',None),'checked_at':datetime.now(timezone.utc).isoformat()}
    root=Path.home()/'.local/state/cloud-migration-lab'
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=root/'cloud-check.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    os.chmod(path,0o600)
    print(json.dumps(result,ensure_ascii=False))
