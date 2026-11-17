"""Owned synthetic HTTP workload, installed only on the two disposable ECS."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit

ORDERS = [{'order_id': f'DEMO-{i:04}', 'customer': f'合成客户{i:03}', 'amount_cny': round(i*12.5, 2), 'status': 'simulated'} for i in range(1, 21)]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        value = {'synthetic': True, 'service': 'cfw-owned-lab', 'status': 'ok'}
        code = 200
        if path == '/orders': value = {'synthetic': True, 'orders': ORDERS}
        elif path not in ('/', '/health'): value, code = {'error': 'not found'}, 404
        payload = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, choices=(8080, 18080), required=True)
    ThreadingHTTPServer(('0.0.0.0', parser.parse_args().port), Handler).serve_forever()
