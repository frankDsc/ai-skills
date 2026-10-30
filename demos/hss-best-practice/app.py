"""Loopback-only Flask frontend + cloud backend; asynchronous fixed actions."""
import argparse
import json
from pathlib import Path
import secrets
import threading
import time

from flask import Flask, jsonify, request, render_template
from cloud import Cloud, error_message
from diagram import build
from scenarios import SCENARIOS,get_scenario,match_events

ACTIONS = {
    'preflight': ('账户与规格预检','校验区域、HSS 权限、镜像和 SSH 来源'),
    'provision': ('创建演练环境','专用 VPC / 安全组 / ECS / EIP，产生按需费用'),
    'install': ('安装 HSS Agent','获取官方安装命令，等待主机上线'),
    'protect': ('开启企业版防护','按需计费，等待云端防护状态确认'),
    'exercise': ('执行选定场景演练','专用主机上的固定受控场景，目标与命令不可由浏览器自定义'),
    'prepare_scenarios': ('准备演练依赖','仅在专用主机安装固定的四种测试工具'),
    'risks': ('查询漏洞与基线','读取 HSS 已上报的真实风险，不自动修复'),
    'cleanup_artifacts': ('清理演练产物','清理专用主机上的测试文件、账号与 cron 项'),
    'acknowledge': ('标记演练告警已处理','清理产物后，仅标记本次主机与场景匹配的事件'),
    'cleanup': ('释放 Demo 资源','关闭 HSS 防护并释放本次记录的资源'),
}


def create_app(cloud=None):
    app=Flask(__name__)
    cloud=cloud or Cloud()
    csrf=secrets.token_urlsafe(32)
    lock=threading.Lock()
    jobs=[]
    cache={}
    arch=build()

    @app.before_request
    def protect_loopback():
        if request.host not in ('127.0.0.1:8899','localhost:8899'):
            return jsonify(error='Host not allowed'),403
        if request.method=='POST':
            if request.headers.get('Origin') not in (None,'http://127.0.0.1:8899','http://localhost:8899'):
                return jsonify(error='Origin not allowed'),403
            if not secrets.compare_digest(request.headers.get('X-Demo-Token',''),csrf):
                return jsonify(error='请从本机演示页面发起操作'),403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.get('/')
    def index():
        return render_template('index.html',csrf=csrf,architecture=arch)

    @app.get('/api/health')
    def health():
        return jsonify(ok=True,region='cn-north-4',connected=bool(cloud.project_id))

    def cached(key,fn,ttl):
        now=time.monotonic()
        old=cache.get(key)
        if old and now-old[0]<ttl:return old[1]
        value=fn();cache[key]=(now,value)
        return value

    @app.get('/api/status')
    def status():
        try:
            data=cached('status',cloud.snapshot,8)
            run=dict(cloud.state['last_exercise']) if cloud.state.get('last_exercise') else None
            if run:
                try:
                    run['matched_events']=match_events(run,cached('events',cloud.events,5)['events'])
                    run['detection_status']='detected' if run['matched_events'] else 'pending'
                except Exception as exc:
                    run['detection_status']='query_error';run['detection_error']=error_message(exc)
            return jsonify(**data,jobs=jobs[-20:],busy=lock.locked(),plan=cloud.state.get('plan'),last_exercise=run)
        except Exception as exc:
            return jsonify(error=error_message(exc)),502

    @app.get('/api/events')
    def events():
        try:return jsonify(cached('events',cloud.events,5))
        except Exception as exc:return jsonify(events=[],total=0,error=error_message(exc)),502

    @app.get('/api/actions')
    def actions():
        return jsonify(actions=[{'id':k,'label':v[0],'description':v[1]} for k,v in ACTIONS.items()])

    @app.get('/api/scenarios')
    def scenarios():
        return jsonify(scenarios=SCENARIOS)

    @app.post('/api/execute')
    def execute():
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict):return jsonify(error='请求必须是 JSON 对象'),400
        action=data.get('id')
        if not isinstance(action,str) or action not in ACTIONS:return jsonify(error='未知动作'),400
        scenario_id=data.get('scenario_id','suid')
        if action=='exercise':
            try:get_scenario(scenario_id)
            except ValueError:return jsonify(error='未知演练场景'),400
        if action=='cleanup' and data.get('confirmation')!=cloud.state['demo_id']:
            return jsonify(error='释放资源需要输入完整 Demo ID'),400
        if not lock.acquire(blocking=False):return jsonify(error='已有操作执行中，请等待完成'),409
        job={'id':secrets.token_hex(6),'action':action,'label':ACTIONS[action][0],'status':'running','started_at':int(time.time()*1000)}
        if action=='exercise':
            job['scenario_id']=scenario_id;job['label']=get_scenario(scenario_id)['name']
        jobs.append(job)
        del jobs[:-20]

        def run():
            try:
                if not cloud.project_id:cloud.connect()
                job['result']=cloud.exercise(scenario_id) if action=='exercise' else getattr(cloud,action)()
                job['status']='success'
            except Exception as exc:
                message=error_message(exc)
                # Installation responses may contain a signed URL/token; don't echo them.
                if action=='install':message=f'安装失败（{type(exc).__name__}）；请检查 Agent 状态与受限 SSH 网络，安装令牌已隐藏'
                job['status']='error';job['error']=message
                cloud.record(ACTIONS[action][0]+'失败',message,'error')
            finally:
                job['finished_at']=int(time.time()*1000)
                cache.clear();lock.release()
        threading.Thread(target=run,daemon=True).start()
        return jsonify(job_id=job['id'],status='running'),202

    app.config['DEMO_CLOUD']=cloud
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--action',choices=list(ACTIONS))
    parser.add_argument('--confirm')
    parser.add_argument('--scenario',default='suid',choices=[s['id'] for s in SCENARIOS])
    args=parser.parse_args()
    cloud=Cloud()
    try:
        cloud.connect()
        if args.action:
            if args.action=='cleanup' and args.confirm!=cloud.state['demo_id']:
                raise ValueError('清理须提供 --confirm <demo-id>')
            result=cloud.exercise(args.scenario) if args.action=='exercise' else getattr(cloud,args.action)()
            print(json.dumps(result,ensure_ascii=False,indent=2))
        else:
            create_app(cloud).run(host='127.0.0.1',port=8899,threaded=True,debug=False)
    except Exception as exc:
        print('ERROR:',error_message(exc))
        raise SystemExit(1)
