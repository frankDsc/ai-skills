"""Loopback-only lab UI with fixed actions; optional existing-ECS SSH runner."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading

from flask import Flask, jsonify, render_template, request
from diagram import build
from engine import Lab, ACTIONS
from transfer import TransferJob

HERE=Path(__file__).resolve().parent


class Runner:
    def __init__(self):
        self.host=os.environ.get('MIGRATION_SSH_HOST')
        self.cloud=None
        cloud_path=Path.home()/'.local/state/cloud-migration-lab/cloud-state.json'
        cloud_state=json.loads(cloud_path.read_text()) if cloud_path.exists() else {}
        if cloud_state.get('resources',{}).get('public_ip') or cloud_state.get('released'):
            from cloud import Cloud
            self.cloud=Cloud()
            self.host='managed-ecs'
        self.root=os.environ.get('MIGRATION_RUNTIME',str(Path.home()/'.local/state/cloud-migration-lab'))
        if self.host:
            # Host aliases are configured outside this repository with strict host key checking.
            if not all(c.isalnum() or c in '.-_' for c in self.host):
                raise ValueError('MIGRATION_SSH_HOST 必须是受信任的 SSH 配置别名')
            self.root='.local/state/cloud-migration-lab'

    def call(self,action):
        if self.cloud:
            self.cloud.state=json.loads(self.cloud.path.read_text())
            history=self.cloud.runtime/'cloud-last-snapshot.json'
            if self.cloud.state.get('released'):
                if action!='status':raise ValueError('云环境已释放，当前仅展示历史实测记录')
                result=json.loads(history.read_text())
                return {**result,'released':True}
            result=self.cloud.execute_engine(action)
            if action=='status':
                history.write_text(json.dumps(result,ensure_ascii=False));history.chmod(0o600)
            return result
        if self.host:
            # Fixed Python source via stdin; no arbitrary browser command or remote shell input.
            command=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                     '-o','ConnectTimeout=10',self.host,
                     f'python3 - --root {self.root} --action {action}']
            result=subprocess.run(command,input=(HERE/'engine.py').read_text(),text=True,
                                  capture_output=True,timeout=90)
            if result.returncode:
                raise RuntimeError('ECS SSH 执行失败；请在本机检查 SSH 别名、主机指纹及 Python 3。')
            return json.loads(result.stdout)
        lab=Lab(self.root)
        return lab.snapshot() if action=='status' else lab.execute(action)


def create_app(runner=None,port=8901,transfer=None):
    app=Flask(__name__)
    runner=runner or Runner()
    token=secrets.token_urlsafe(32)
    lock=threading.Lock()
    status_lock=threading.Lock()
    transfer=transfer or TransferJob()
    hosts={f'127.0.0.1:{port}',f'localhost:{port}'}

    @app.before_request
    def protect():
        if request.host not in hosts:
            return jsonify(error='Host not allowed'),403
        if request.method=='POST':
            if request.headers.get('Origin') not in {None,*('http://'+x for x in hosts)}:
                return jsonify(error='Origin not allowed'),403
            if not secrets.compare_digest(request.headers.get('X-Demo-Token',''),token):
                return jsonify(error='请从本机演示页面发起操作'),403
            if request.content_length and request.content_length>2048:
                return jsonify(error='请求过大'),413

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                                 'X-Frame-Options':'DENY','Referrer-Policy':'no-referrer'})
        return response

    @app.get('/')
    def index():
        return render_template('index.html',token=token,architecture=build())

    @app.get('/api/status')
    def status():
        if lock.locked():
            return jsonify(busy=True)
        status_lock.acquire()
        try:
            data=runner.call('status')
            check_path=Path.home()/'.local/state/cloud-migration-lab/cloud-check.json'
            cloud_check=json.loads(check_path.read_text()) if check_path.exists() else None
            cloud=getattr(runner,'cloud',None)
            details=None
            if cloud:
                r=cloud.state['resources']
                details={'name':cloud.state['demo_id'],'server_id':r.get('server_id'),
                         'public_ip':r.get('public_ip'),'created_at':r.get('created_at'),
                         'flavor':cloud.plan['flavor'],
                         'hourly_cny':round(cloud.plan.get('prices',{}).get('hourly_total',0.4996),4),
                         'budget_cny':3,'auto_release_at':cloud.state.get('auto_release_at')}
            return jsonify(**data,busy=False,execution='ecs-ssh' if runner.host else 'local',
                           execution_label='云环境已释放 · 历史实测记录' if data.get('released') else ('真实 ECS · SSH 执行' if runner.host else '本机预演 · 尚未部署 ECS'),
                           region='cn-north-4',cloud_check=cloud_check,cloud_details=details)
        except Exception:
            app.logger.exception('Status failed')
            return jsonify(error='执行后端不可用；请检查本机日志与连接。'),502
        finally:
            status_lock.release()

    @app.get('/api/actions')
    def actions():
        return jsonify(actions=[dict(id=k,label=v[0],description=v[1],flow=v[2]) for k,v in ACTIONS.items()])

    @app.get('/api/transfer')
    def transfer_status():
        return jsonify(transfer.snapshot())

    @app.post('/api/transfer/start')
    def transfer_start():
        try:return jsonify(transfer.start()),202
        except ValueError as exc:return jsonify(error=str(exc)),409

    @app.post('/api/execute')
    def execute():
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or not isinstance(data.get('id'),str) or data['id'] not in ACTIONS:
            return jsonify(error='未知动作'),400
        if not lock.acquire(blocking=False):
            return jsonify(error='已有动作执行中'),409
        try:
            result=runner.call(data['id'])
            return jsonify(result),200 if result.get('ok') else 409
        except Exception:
            app.logger.exception('Execution failed')
            return jsonify(error='执行失败；请检查日志，刷新实际状态后再决定是否重试。'),502
        finally:
            lock.release()

    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8901)
    args=parser.parse_args()
    create_app(port=args.port).run(host='127.0.0.1',port=args.port,threaded=True,debug=False)
