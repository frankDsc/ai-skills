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

HERE=Path(__file__).resolve().parent


class Runner:
    def __init__(self):
        self.host=os.environ.get('MIGRATION_SSH_HOST')
        self.root=os.environ.get('MIGRATION_RUNTIME',str(Path.home()/'.local/state/cloud-migration-lab'))
        if self.host:
            # Host aliases are configured outside this repository with strict host key checking.
            if not all(c.isalnum() or c in '.-_' for c in self.host):
                raise ValueError('MIGRATION_SSH_HOST 必须是受信任的 SSH 配置别名')
            self.root='.local/state/cloud-migration-lab'

    def call(self,action):
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


def create_app(runner=None,port=8901):
    app=Flask(__name__)
    runner=runner or Runner()
    token=secrets.token_urlsafe(32)
    lock=threading.Lock()
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
        if not lock.acquire(blocking=False):
            return jsonify(busy=True)
        try:
            data=runner.call('status')
            check_path=Path.home()/'.local/state/cloud-migration-lab/cloud-check.json'
            cloud_check=json.loads(check_path.read_text()) if check_path.exists() else None
            return jsonify(**data,busy=False,execution='ecs-ssh' if runner.host else 'local',
                           execution_label='真实 ECS · SSH 执行' if runner.host else '本机预演 · 尚未部署 ECS',
                           region='cn-north-4',cloud_check=cloud_check)
        except Exception:
            app.logger.exception('Status failed')
            return jsonify(error='执行后端不可用；请检查本机日志与连接。'),502
        finally:
            lock.release()

    @app.get('/api/actions')
    def actions():
        return jsonify(actions=[dict(id=k,label=v[0],description=v[1],flow=v[2]) for k,v in ACTIONS.items()])

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
