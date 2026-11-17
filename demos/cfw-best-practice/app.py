"""Local CFW dashboard: real scoped runtime when deployed, otherwise safe preview."""
import argparse
import json
from pathlib import Path
import secrets
import threading

from flask import Flask, jsonify, render_template, request
from cloud import Cloud, estimate
from diagram import build

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'plan.json').read_text())
ORIGINS = ('http://127.0.0.1:8902', 'http://localhost:8902')


def create_app(cloud=None):
    app = Flask(__name__)
    live = None
    if cloud is None and (Path.home()/'.local/state/cfw-best-practice-lab/live-state.json').exists():
        from live_service import LiveService
        live = LiveService()
    cloud = cloud or Cloud()
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()

    @app.before_request
    def guard():
        if request.host not in ('127.0.0.1:8902', 'localhost:8902'):
            return jsonify(error='Host not allowed'), 403
        if request.method == 'POST':
            if request.headers.get('Origin') not in (None, *ORIGINS):
                return jsonify(error='Origin not allowed'), 403
            if not secrets.compare_digest(request.headers.get('X-Demo-Token', ''), token):
                return jsonify(error='请从本机页面发起操作'), 403

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
                                 'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"})
        return response

    @app.get('/')
    def index():
        plan = live.plan(PLAN) if live else PLAN
        architecture = build()
        return render_template('index.html', csrf=token, architecture=architecture, plan=plan, estimate=estimate(plan), is_live=bool(live))

    @app.get('/api/status')
    def status():
        if live: return jsonify(live.snapshot(PLAN))
        return jsonify(mode='preview', account=cloud.snapshot(), plan=PLAN, estimate=estimate(PLAN),
                       resources_created=0, tests_executed=0, logs=[], cleanup_scheduled=False,
                       deployment_enabled=False, blocker='当前为方案预览；未创建真实 CFW 或 ECS，未执行云端演练。')

    @app.post('/api/preflight')
    def preflight():
        if not lock.acquire(blocking=False):
            return jsonify(error='正在核验，请稍候'), 409
        try:
            return jsonify(account=cloud.preflight())
        except Exception:
            # SDK errors may contain signed requests or account IDs.
            return jsonify(error='只读核验失败；请检查凭证、网络及 IAM/CFW 查询权限。上次快照不代表当前状态。'), 502
        finally:
            lock.release()

    @app.post('/api/execute')
    def execute():
        if live:
            try: return jsonify(job_id=live.execute(request.get_json(silent=True)),status='running'),202
            except ValueError as e: return jsonify(error=str(e)),400
            except BlockingIOError: return jsonify(error='已有云端操作执行中，请稍后重试'),409
        return jsonify(error='当前预览版本禁止创建资源或执行云端动作；需先解决按需购买资格并接入真实执行器。'), 409

    @app.get('/api/export')
    def export():
        if live:
            response = jsonify(document_type='CFW 真实演练记录', **live.snapshot(PLAN))
            response.headers['Content-Disposition'] = 'attachment; filename="cfw-live-evidence.json"'
            return response
        response = jsonify(document_type='方案与资格核验（非实测报告）', plan=PLAN, estimate=estimate(PLAN),
                           account=cloud.snapshot(), resources_created=0, measurements=[], cloud_logs=[])
        response.headers['Content-Disposition'] = 'attachment; filename="cfw-lab-plan.json"'
        return response

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(Cloud().preflight(), ensure_ascii=False, indent=2))
    else:
        create_app().run(host='127.0.0.1', port=8902, debug=False, threaded=True)
