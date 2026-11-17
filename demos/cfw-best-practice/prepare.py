"""Read-only Hong Kong capability/SKU/image lookup and current BSS quote."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
from huaweicloudsdkcfw.v1 import CfwClient, ListFirewallListRequest, QueryFireWallInstanceDto
from huaweicloudsdkecs.v2 import EcsClient, NovaListAvailabilityZonesRequest, ListFlavorsRequest
from huaweicloudsdkims.v2 import ImsClient, ListImagesRequest
from huaweicloudsdkbss.v2 import BssClient, ListOnDemandResourceRatingsRequest, RateOnDemandReq, DemandProductInfo
from live import RUNTIME, save


def prepare():
    import os
    state=RUNTIME/'live-state.json'
    if state.exists():
        previous=json.loads(state.read_text())
        if previous.get('resources') and not previous.get('released'):
            raise ValueError('已有未释放环境，禁止覆盖其区域与资源计划')
    with Path(os.environ.get('HWC_CREDENTIALS_CSV',str(Path.home()/'Downloads/credentials.csv'))).open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=1:raise ValueError('凭证文件必须恰好一行')
    ak,sk=(rows[0][k].strip() for k in ('Access Key Id','Secret Access Key'))
    region='ap-southeast-1';flavor='c6.large.2'
    iam=IamClient.new_builder().with_credentials(GlobalCredentials(ak,sk)).with_endpoint('https://iam.myhuaweicloud.com').build()
    projects=iam.keystone_list_projects(KeystoneListProjectsRequest(name=region)).projects or []
    if len(projects)!=1:raise ValueError('无法唯一识别可访问的香港项目')
    pid=projects[0].id;cred=BasicCredentials(ak,sk).with_project_id(pid)
    cfw=CfwClient.new_builder().with_credentials(cred).with_endpoint(f'https://cfw.{region}.myhuaweicloud.com').build()
    capability=cfw.list_firewall_list(ListFirewallListRequest(body=QueryFireWallInstanceDto(limit=1,offset=0))).to_dict()
    if capability.get('is_support_postpaid') is not True:raise ValueError('当前香港项目不支持 CFW 按需，未创建资源')
    ecs=EcsClient.new_builder().with_credentials(cred).with_endpoint(f'https://ecs.{region}.myhuaweicloud.com').build()
    zones=ecs.nova_list_availability_zones(NovaListAvailabilityZonesRequest()).to_json_object()['availabilityZoneInfo']
    az=None
    for zone in zones:
        if zone['zoneState']['available'] and any(x['id']==flavor for x in ecs.list_flavors(ListFlavorsRequest(availability_zone=zone['zoneName'])).to_json_object()['flavors']):
            az=zone['zoneName'];break
    if az is None:raise ValueError('当前无可用 c6.large.2；不自动升级规格')
    ims=ImsClient.new_builder().with_credentials(cred).with_endpoint(f'https://ims.{region}.myhuaweicloud.com').build()
    images=ims.list_images(ListImagesRequest(imagetype='gold',os_type='Linux',platform='Ubuntu',status='active',architecture='x86_64',limit=200)).to_json_object()['images']
    images=[x for x in images if '22.04' in x['name'] and int(x.get('min_disk',0))<=40 and not any(w in x['name'].lower() for w in ('gpu','cuda','graphic','driver','arm'))]
    images.sort(key=lambda x:x.get('created_at',''),reverse=True)
    if not images:raise ValueError('没有适合的 Ubuntu 22.04 公共镜像')
    bss=BssClient.new_builder().with_credentials(GlobalCredentials(ak,sk)).with_endpoint('https://bss.myhuaweicloud.com').build()
    items=[('ecs_hour','ec2','vm',flavor+'.linux','Duration',4,None,None),('disk_hour','ebs','volume','SAS','Duration',4,40,17),('eip_hour','vpc','ip','5_bgp','Duration',4,None,None),('egress_gb','vpc','bandwidth','12_bgp','upflow',10,5,15),('cfw_hour','cfw','cfw','cfw.professional','usage_duration',4,None,None),('cfw_gb','cfw','cfw.exp.trafficflow','cfw.expack.trafficflow.professional','megabyte',10,None,None)]
    quotes={}
    for key,service,resource,spec,factor,unit,size,size_unit in items:
        product=DemandProductInfo(id=key,cloud_service_type='hws.service.type.'+service,resource_type='hws.resource.type.'+resource,resource_spec=spec,region=region,usage_factor=factor,usage_value=1,usage_measure_id=unit,subscription_num=1,resource_size=size,size_measure_id=size_unit)
        quote=bss.list_on_demand_resource_ratings(ListOnDemandResourceRatingsRequest(body=RateOnDemandReq(project_id=pid,inquiry_precision=1,product_infos=[product]))).to_json_object()
        if quote.get('measure_id')!=1 or quote.get('currency')!='CNY':raise ValueError('询价币种或计量单位不符')
        quotes[key]=quote
    rates={k:float(v['amount']) for k,v in quotes.items()}
    hour=rates['cfw_hour']+2*sum(rates[k] for k in ('ecs_hour','disk_hour','eip_hour'))
    total=hour*2+rates['cfw_gb']+rates['egress_gb']
    plan={'region':region,'project_id':pid,'availability_zone':az,'flavor':flavor,'image_id':images[0]['id'],'image_name':images[0]['name'],'rates':rates,'hourly_cny':round(hour,4),'two_hour_estimate_cny':round(total,4),'quotes':quotes,'disk_gb':40,'eip_mbps':5,'quoted_at':datetime.now(timezone.utc).isoformat()}
    RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700);save(RUNTIME/'hongkong-plan.json',plan)
    return {k:v for k,v in plan.items() if k not in ('project_id','image_id','quotes')}


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
