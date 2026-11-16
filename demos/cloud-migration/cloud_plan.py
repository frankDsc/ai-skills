"""Read-only live SKU/image lookup and BSS quote; creates no cloud resources."""
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials,GlobalCredentials
from huaweicloudsdkiam.v3 import IamClient,KeystoneListProjectsRequest
from huaweicloudsdkecs.v2 import EcsClient,ListFlavorsRequest,NovaListAvailabilityZonesRequest
from huaweicloudsdkims.v2 import ImsClient,ListImagesRequest
from huaweicloudsdkbss.v2 import BssClient,ListOnDemandResourceRatingsRequest,RateOnDemandReq,DemandProductInfo


def plan():
    path=Path(os.environ.get('HWC_CREDENTIALS_CSV',str(Path.home()/'Downloads/credentials.csv')))
    with path.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    if len(rows)!=1:raise ValueError('凭证 CSV 必须恰好一行')
    ak,sk=(rows[0].get(k,'').strip() for k in ('Access Key Id','Secret Access Key'))
    if not ak or not sk:raise ValueError('凭证文件无效')
    region='cn-north-4';flavor='c6.large.2'
    iam=IamClient.new_builder().with_credentials(GlobalCredentials(ak,sk)).with_endpoint('https://iam.myhuaweicloud.com').build()
    projects=iam.keystone_list_projects(KeystoneListProjectsRequest(name=region)).projects
    if not projects:raise ValueError('无法访问北京四项目')
    pid=projects[0].id;cred=BasicCredentials(ak,sk).with_project_id(pid)
    ecs=EcsClient.new_builder().with_credentials(cred).with_endpoint(f'https://ecs.{region}.myhuaweicloud.com').build()
    zones=ecs.nova_list_availability_zones(NovaListAvailabilityZonesRequest()).to_json_object()['availabilityZoneInfo']
    az=None
    for zone in zones:
        if not zone['zoneState']['available']:continue
        flavors=ecs.list_flavors(ListFlavorsRequest(availability_zone=zone['zoneName'])).to_json_object()['flavors']
        if any(x['id']==flavor for x in flavors):az=zone['zoneName'];break
    if not az:raise ValueError('所选小规格在北京四不可用；请重新选型和询价')
    ims=ImsClient.new_builder().with_credentials(cred).with_endpoint(f'https://ims.{region}.myhuaweicloud.com').build()
    images=ims.list_images(ListImagesRequest(imagetype='gold',os_type='Linux',platform='Ubuntu',status='active',architecture='x86_64',limit=200)).to_json_object()['images']
    images=[x for x in images if '22.04' in x['name'] and int(x.get('min_disk',0))<=40
            and not any(w in x['name'].lower() for w in ('gpu','cuda','arm','graphic','driver'))]
    images.sort(key=lambda x:x.get('created_at',''),reverse=True)
    if not images:raise ValueError('未发现合适的 Ubuntu 公共镜像')
    result={'region':region,'project_id':pid,'availability_zone':az,'flavor':flavor,
            'image_id':images[0]['id'],'image_name':images[0]['name'],'disk_gb':40,'eip_mbps':5}
    bss=BssClient.new_builder().with_credentials(GlobalCredentials(ak,sk)).with_endpoint('https://bss.myhuaweicloud.com').build()
    items=[('ecs_hour','ec2','vm',flavor+'.linux','Duration',4,None,None),
           ('disk_hour','ebs','volume','SAS','Duration',4,40,17),
           ('eip_hour','vpc','ip','5_bgp','Duration',4,None,None),
           ('egress_gb','vpc','bandwidth','12_bgp','upflow',10,5,15)]
    prices={}
    for key,service,resource,spec,factor,unit,size,size_unit in items:
        product=DemandProductInfo(id=key,cloud_service_type='hws.service.type.'+service,
            resource_type='hws.resource.type.'+resource,resource_spec=spec,region=region,
            usage_factor=factor,usage_value=1,usage_measure_id=unit,subscription_num=1,
            resource_size=size,size_measure_id=size_unit)
        quote=bss.list_on_demand_resource_ratings(ListOnDemandResourceRatingsRequest(
            body=RateOnDemandReq(project_id=pid,inquiry_precision=1,product_infos=[product]))).to_json_object()
        if quote.get('measure_id')!=1 or quote.get('currency') not in ('CNY','',None):raise ValueError('询价币种/单位不符合预期')
        prices[key]=float(quote['amount'])
    prices['hourly_total']=sum(prices[k] for k in ('ecs_hour','disk_hour','eip_hour'))
    result.update(prices=prices,quoted_at=datetime.now(timezone.utc).isoformat())
    root=Path.home()/'.local/state/cloud-migration-lab';root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=root/'provision-plan.json'
    # A read-only re-quote must preserve an existing plan's operator allowlist.
    if target.exists():
        old=json.loads(target.read_text())
        if old.get('ssh_cidr'):result['ssh_cidr']=old['ssh_cidr']
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2));target.chmod(0o600)
    return {k:v for k,v in result.items() if k not in ('project_id','image_id','ssh_cidr')}


if __name__=='__main__':print(json.dumps(plan(),ensure_ascii=False,indent=2))
