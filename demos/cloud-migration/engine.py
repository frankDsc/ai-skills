"""Synthetic migration lab; only touches its own private runtime directory.

SQLite row comparison and file copying demonstrate the workflow, not SMS/DRS/OMS.
The same engine can run locally or on a test ECS through the SSH runner.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time

ACTIONS = {
    'prepare': ('生成模拟源数据', '1,200 笔虚构订单、应用配置、12 个合成附件', ['source']),
    'full': ('执行全量搬迁', '复制应用、订单库与附件，保留源端服务', ['source','transfer','target']),
    'change': ('产生源端增量', '新增 25 笔、更新 10 笔、删除 5 笔订单及附件变更', ['source']),
    'sync': ('执行差异补迁', '按主键比对订单、按 SHA-256 比对文件，处理删除', ['source','transfer','target']),
    'freeze': ('冻结源端写入', '进入只读割接窗口，阻止新的源端模拟交易', ['source']),
    'verify': ('验证割接门禁', '对比全部订单内容、文件摘要，并做只读业务探针', ['source','transfer','target']),
    'cutover': ('切换演示业务', '门禁通过才将本实验逻辑路由切至目标端；保留只读回退窗', ['transfer','target']),
    'rollback': ('执行只读回退', '目标未产生新写入且源目标仍一致时才允许回退', ['target','transfer','source']),
    'target_write': ('验证写后回退拦截', '在目标写入一笔虚构订单，验证简单回切被禁止', ['target']),
}


class Lab:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.path = self.root/'lab.json'
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'prepared': False, 'full': False, 'frozen': False, 'active': 'source',
            'changed': False, 'target_writes': 0, 'verification': None,
            'last_action': None, 'events': [], 'metrics': {},
        }

    def save(self):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        os.chmod(temp, 0o600)
        temp.replace(self.path)

    def rows(self, side):
        p = self.root/side/'orders.sqlite'
        if not p.exists():
            return []
        with sqlite3.connect(p) as conn:
            return conn.execute('SELECT id,customer,amount_cents,status FROM orders ORDER BY id').fetchall()

    def files(self, side):
        base = self.root/side
        return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ('app','objects') if (base/folder).exists()
                for p in sorted((base/folder).rglob('*')) if p.is_file()}

    def signature(self, side):
        return hashlib.sha256(json.dumps({'rows': self.rows(side), 'files': self.files(side)},
                                        sort_keys=True).encode()).hexdigest()

    def compare(self):
        left, right = dict((x[0],x) for x in self.rows('source')), dict((x[0],x) for x in self.rows('target'))
        lf, rf = self.files('source'), self.files('target')
        row_diff = sum(left.get(k) != right.get(k) for k in left.keys() | right.keys())
        file_diff = sum(lf.get(k) != rf.get(k) for k in lf.keys() | rf.keys())
        ready = self.state['prepared'] and self.state['full']
        return {'row_diff': row_diff, 'file_diff': file_diff,
                'consistent': bool(ready and row_diff == 0 and file_diff == 0),
                'source_hash': self.signature('source'), 'target_hash': self.signature('target')}

    def require(self, value, message):
        if not value:
            raise ValueError(message)

    def prepare(self):
        self.require(not self.state['prepared'], '源数据已存在；为保护演练记录，不重复覆盖。')
        base = self.root/'source'
        (base/'app').mkdir(parents=True, exist_ok=True)
        (base/'objects').mkdir(exist_ok=True)
        with sqlite3.connect(base/'orders.sqlite') as conn:
            conn.execute('CREATE TABLE orders(id INTEGER PRIMARY KEY,customer TEXT,amount_cents INTEGER,status TEXT)')
            conn.executemany('INSERT INTO orders VALUES(?,?,?,?)',
                             [(i,f'SYNTH-CUSTOMER-{i%80:03d}', 1000+i*37, 'paid') for i in range(1,1201)])
        (base/'app'/'settings.json').write_text(json.dumps({'application':'synthetic-order-service','schema':1}))
        for i in range(12):
            (base/'objects'/f'attachment-{i:02d}.txt').write_bytes((f'SYNTHETIC-ONLY-{i:02d}\n'*2048).encode())
        self.state['prepared'] = True
        return {'orders':1200,'objects':12,'data':'100% synthetic'}

    def full(self):
        self.require(self.state['prepared'] and self.state['active']=='source', '请先生成源数据，并保持源端服务。')
        target = self.root/'target'
        target.mkdir(exist_ok=True)
        with sqlite3.connect(self.root/'source'/'orders.sqlite') as src, sqlite3.connect(target/'orders.sqlite') as dst:
            src.backup(dst)
        for name in ('app','objects'):
            shutil.copytree(self.root/'source'/name,target/name,dirs_exist_ok=True)
            for p in (target/name).rglob('*'):
                if p.is_file() and not (self.root/'source'/p.relative_to(target)).exists():
                    p.unlink()
        self.state['full'] = True
        self.state['verification'] = None
        return {'orders':len(self.rows('target')),'files':len(self.files('target'))}

    def change(self):
        self.require(self.state['full'] and not self.state['frozen'] and self.state['active']=='source', '全量后、冻结前才可模拟源端交易。')
        self.require(not self.state['changed'], '本轮增量已生成，请补迁后继续割接。')
        with sqlite3.connect(self.root/'source'/'orders.sqlite') as conn:
            conn.executemany('INSERT INTO orders VALUES(?,?,?,?)', [(i,'SYNTH-NEW',2400+i,'paid') for i in range(1201,1226)])
            conn.execute("UPDATE orders SET status='refunded' WHERE id BETWEEN 1 AND 10")
            conn.execute('DELETE FROM orders WHERE id BETWEEN 11 AND 15')
        base = self.root/'source'/'objects'
        (base/'attachment-00.txt').write_text('SYNTHETIC UPDATED CONTENT\n')
        (base/'attachment-01.txt').unlink()
        (base/'attachment-new.txt').write_text('SYNTHETIC NEW OBJECT\n')
        self.state['changed'] = True
        self.state['verification'] = None
        return {'inserted':25,'updated':10,'deleted':5,'file_changes':3}

    def sync(self):
        self.require(self.state['full'] and self.state['active']=='source', '先完成全量搬迁，且当前仍由源端服务。')
        src, dst = dict((x[0],x) for x in self.rows('source')), dict((x[0],x) for x in self.rows('target'))
        changed = [v for k,v in src.items() if dst.get(k)!=v]
        deleted = [(k,) for k in dst.keys()-src.keys()]
        with sqlite3.connect(self.root/'target'/'orders.sqlite') as conn:
            conn.executemany('INSERT OR REPLACE INTO orders VALUES(?,?,?,?)', changed)
            conn.executemany('DELETE FROM orders WHERE id=?', deleted)
        lf, rf = self.files('source'), self.files('target')
        copied = [k for k,v in lf.items() if rf.get(k)!=v]
        removed = list(rf.keys()-lf.keys())
        for name in copied:
            target = self.root/'target'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(self.root/'source'/name,target)
        for name in removed:
            (self.root/'target'/name).unlink()
        self.state['verification'] = None
        return {'upserted':len(changed),'deleted':len(deleted),'files_copied':len(copied),'files_deleted':len(removed)}

    def freeze(self):
        self.require(self.state['full'] and self.state['active']=='source', '先完成全量搬迁。')
        self.state['frozen'] = True
        return {'source_read_only':True,'scope':'实验引擎写入门禁；不修改真实数据库或业务'}

    def verify(self):
        self.require(self.state['full'], '请先完成全量搬迁。')
        result = self.compare()
        with sqlite3.connect(self.root/'target'/'orders.sqlite') as conn:
            probe = conn.execute('SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM orders').fetchone()
        result.update({'probe_ok':probe[0]>0,'orders':probe[0],'sum_cents':probe[1],
                       'passed':result['consistent'] and self.state['frozen'] and probe[0]>0,'ts':time.time()})
        self.state['verification'] = result
        return result

    def cutover(self):
        v = self.state['verification'] or {}
        result = self.compare()
        self.require(self.state['active']=='source' and self.state['frozen'] and v.get('passed')
                     and result['consistent'] and v.get('source_hash')==result['source_hash'],
                     '割接被拦截：需冻结写入、完成最新全内容校验与业务探针。')
        self.state['active'] = 'target'
        self.state['target_writes'] = 0
        return {'active':'target','target_mode':'read-only','scope':'仅切换本实验逻辑路由，不更改云 DNS/ELB'}

    def target_write(self):
        self.require(self.state['active']=='target', '先割接到目标端。')
        with sqlite3.connect(self.root/'target'/'orders.sqlite') as conn:
            conn.execute("INSERT INTO orders(customer,amount_cents,status) VALUES('SYNTH-TARGET-WRITE',9900,'paid')")
        self.state['target_writes'] += 1
        self.state['verification'] = None
        return {'target_writes':self.state['target_writes'],'rollback':'禁止简单回切；需反向同步或合并新写入'}

    def rollback(self):
        self.require(self.state['active']=='target', '当前未割接至目标端。')
        self.require(self.state['target_writes']==0 and self.compare()['consistent'],
                     '回退被拦截：目标存在新写入或源目标不一致，必须先做反向同步/数据合并。')
        self.state['active'] = 'source'
        self.state['frozen'] = False
        self.state['verification'] = None
        return {'active':'source','data_loss':0,'scope':'只读观察窗内的逻辑路由回退'}

    def execute(self, action):
        self.require(action in ACTIONS,'未知动作')
        start = time.monotonic()
        try:
            result = getattr(self, action)()
            status, error = 'success', None
        except ValueError as exc:
            result, status, error = {}, 'blocked', str(exc)
        elapsed = round((time.monotonic()-start)*1000,2)
        self.state['last_action'] = action
        self.state['metrics'][action] = {'elapsed_ms':elapsed,**result}
        self.state['events'].insert(0, {'id':time.time_ns(),'action':action,'name':ACTIONS[action][0],
                                     'status':status,'detail':error or result,'elapsed_ms':elapsed,'ts':time.time()})
        self.state['events'] = self.state['events'][:100]
        self.save()
        return {'ok':status=='success','error':error,'result':result,'elapsed_ms':elapsed}

    def snapshot(self):
        comparison = self.compare()
        v = self.state['verification'] or {}
        fresh = bool(v.get('passed') and self.state['frozen'] and comparison['consistent']
                     and v.get('source_hash')==comparison['source_hash'])
        return {**self.state,'comparison':comparison,'gate_passed':fresh,
                'source_orders':len(self.rows('source')),'target_orders':len(self.rows('target')),
                'source_files':len(self.files('source')),'target_files':len(self.files('target')),
                'sample':[dict(zip(('id','customer','amount_cents','status'),x)) for x in self.rows(self.state['active'])[:5]],
                'bytes':sum(p.stat().st_size for p in (self.root/'source').rglob('*') if p.is_file())}


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path.home()/'.local/state/cloud-migration-lab'))
    parser.add_argument('--action', choices=['status',*ACTIONS], default='status')
    args = parser.parse_args()
    lab = Lab(args.root)
    print(json.dumps(lab.snapshot() if args.action=='status' else lab.execute(args.action),ensure_ascii=False))
