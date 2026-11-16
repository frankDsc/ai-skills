"""Small synthetic order application that boots with the migrated OS."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import time
from urllib.request import urlopen

ROOT = Path('/opt/sms-migration-lab')
DB = ROOT / 'orders.sqlite'


def connect():
    db = sqlite3.connect(str(DB), timeout=10)
    db.row_factory = sqlite3.Row
    return db


def seed():
    ROOT.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer TEXT, product TEXT, amount_cents INTEGER, status TEXT, created_at REAL)')
        if not db.execute('SELECT count(*) FROM orders').fetchone()[0]:
            db.executemany('INSERT INTO orders VALUES (?,?,?,?,?,?)', [
                (i, 'SYNTH-CUSTOMER-%05d' % (i % 300), ['测试键盘','测试显示器','测试云套餐'][i % 3],
                 1000 + i % 997 * 100, ['已支付','待发货','已完成'][i % 3], time.time()) for i in range(1,10001)])
    if not (ROOT / 'payload.bin').exists():
        import os
        with (ROOT / 'payload.bin').open('wb') as f:
            for _ in range(256):
                f.write(os.urandom(8 * 1024 * 1024))
    digest = hashlib.sha256()
    with (ROOT / 'payload.bin').open('rb') as f:
        for chunk in iter(lambda:f.read(1024 * 1024), b''):
            digest.update(chunk)
    (ROOT / 'payload.sha256').write_text(digest.hexdigest())


def identity():
    try:
        with urlopen('http://169.254.169.254/openstack/latest/meta_data.json', timeout=2) as response:
            metadata = json.load(response)
    except Exception:
        metadata = {}
    return {'instance_id': metadata.get('uuid'), 'hostname': metadata.get('hostname'),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/health', '/orders'):
            self.send_error(404); return
        with connect() as db:
            if self.path == '/orders':
                data = {'synthetic': True, 'orders': [dict(r) for r in db.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 10')]}
            else:
                rows = [tuple(r) for r in db.execute('SELECT * FROM orders ORDER BY id')]
                data = {'healthy': True, 'synthetic': True, **identity(), 'orders': len(rows),
                        'orders_sha256': hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest(),
                        'payload_sha256': (ROOT / 'payload.sha256').read_text(),
                        'service_version': 'sms-order-demo-1', 'time': time.time()}
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['seed','serve','write','checkpoint'])
    args = parser.parse_args()
    if args.action == 'seed': seed()
    elif args.action == 'serve': ThreadingHTTPServer(('0.0.0.0',8080), Handler).serve_forever()
    elif args.action == 'checkpoint':
        with connect() as db: db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    else:
        while True:
            with connect() as db:
                db.execute('INSERT INTO orders(customer,product,amount_cents,status,created_at) VALUES (?,?,?,?,?)',
                    ('SYNTH-LIVE-CUSTOMER','测试增量订单',12345,'已支付',time.time()))
            time.sleep(2)
