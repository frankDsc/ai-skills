"""Asynchronous real SFTP upload with measured client throughput and target SHA-256."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid

RUNTIME=Path.home()/'.local/state/cloud-migration-lab'


class TransferJob:
    def __init__(self,connector=None,runtime=RUNTIME,size_bytes=128*1024*1024):
        self.connector=connector
        self.runtime=Path(runtime)
        self.size_bytes=size_bytes
        self.lock=threading.Lock()
        self.worker=None
        self.started=None
        self.window=deque()
        self.last_sample=0
        self.data={'phase':'idle','sent_bytes':0,'total_bytes':size_bytes,'bytes_per_second':0,
                   'average_bytes_per_second':0,'elapsed_seconds':0,'samples':[],'verified':False,
                   'source_hash':None,'target_hash':None,'error':None}
        evidence=self.runtime/'transfer-evidence.json'
        if evidence.exists():
            saved=json.loads(evidence.read_text())
            if saved.get('phase') in ('completed','failed'):self.data.update(saved)

    def enabled(self):
        if self.connector:return True
        path=self.runtime/'cloud-state.json'
        return path.exists() and bool(json.loads(path.read_text()).get('resources',{}).get('public_ip')) and (self.runtime/'known_hosts').exists()

    def snapshot(self):
        with self.lock:
            result=json.loads(json.dumps(self.data))
            if result['phase']=='transferring' and self.started is not None:
                result['elapsed_seconds']=time.monotonic()-self.started
                if time.monotonic()-self.last_sample>3:result['bytes_per_second']=0
        result['enabled']=self.enabled()
        result['rate_definition']='客户端 SFTP 已发送字节 / 实测时间；目标接收长度与 SHA-256 独立确认'
        return result

    def start(self):
        with self.lock:
            if self.worker and self.worker.is_alive():raise ValueError('已有传输任务正在执行')
            if not self.enabled():raise ValueError('请先创建真实 ECS，并完成 SSH 主机指纹固定')
            self.data={'phase':'preparing','job_id':uuid.uuid4().hex,'sent_bytes':0,
                       'total_bytes':self.size_bytes,'bytes_per_second':0,'average_bytes_per_second':0,
                       'elapsed_seconds':0,'samples':[],'verified':False,'source_hash':None,
                       'target_hash':None,'error':None,'started_at':time.time()}
            self.started=None;self.window.clear();self.last_sample=0
            self.worker=threading.Thread(target=self.run,daemon=True)
            self.worker.start()
        return {'ok':True,'job_id':self.data['job_id']}

    def update(self,sent,total):
        now=time.monotonic()
        with self.lock:
            self.data['sent_bytes']=sent
            if now-self.last_sample<0.25 and sent<total:return
            self.last_sample=now
            self.window.append((now,sent))
            while len(self.window)>2 and self.window[1][0]<=now-1:self.window.popleft()
            first_t,first_bytes=self.window[0]
            span=now-first_t
            rate=(sent-first_bytes)/span if span>0 else 0
            elapsed=now-self.started
            average=sent/elapsed if elapsed>0 else 0
            self.data.update(bytes_per_second=rate,average_bytes_per_second=average,elapsed_seconds=elapsed)
            self.data['samples'].append({'seconds':round(elapsed,3),'bytes_per_second':rate,'sent_bytes':sent})
            self.data['samples']=self.data['samples'][-240:]

    def run(self):
        client=sftp=None
        try:
            self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
            job=self.data['job_id'];source=self.runtime/(job+'.synthetic.bin')
            digest=hashlib.sha256()
            with source.open('wb') as f:
                remaining=self.size_bytes
                while remaining:
                    block=os.urandom(min(1024*1024,remaining))
                    f.write(block);digest.update(block);remaining-=len(block)
            source.chmod(0o600)
            if self.connector:client=self.connector()
            else:
                from cloud import Cloud
                client=Cloud().ssh()
            _,out,err=client.exec_command('mkdir -p /root/.local/state/cloud-migration-transfer && chmod 700 /root/.local/state/cloud-migration-transfer',timeout=30)
            if out.channel.recv_exit_status()!=0:raise RuntimeError('无法初始化 ECS 目标目录')
            sftp=client.open_sftp()
            sftp.get_channel().settimeout(30)
            target=f'/root/.local/state/cloud-migration-transfer/{job}.bin'
            with self.lock:
                self.started=time.monotonic();self.window.append((self.started,0))
                self.data.update(phase='transferring',source_hash=digest.hexdigest())
            sftp.put(str(source),target+'.partial',callback=self.update,confirm=True)
            elapsed=time.monotonic()-self.started
            size=sftp.stat(target+'.partial').st_size
            if size!=self.size_bytes:raise RuntimeError('目标文件长度与源端不符')
            with self.lock:
                self.data.update(phase='verifying',elapsed_seconds=elapsed,
                                 average_bytes_per_second=self.size_bytes/elapsed,bytes_per_second=0,
                                 target_size_bytes=size)
            _,out,err=client.exec_command('sha256sum '+target+'.partial',timeout=90)
            output=out.read().decode()
            if out.channel.recv_exit_status()!=0:raise RuntimeError('目标端摘要计算失败')
            target_hash=output.split()[0] if output.split() else ''
            with self.lock:self.data['target_hash']=target_hash
            if target_hash!=digest.hexdigest():raise RuntimeError('SHA-256 不一致，传输未验收')
            sftp.rename(target+'.partial',target)
            with self.lock:self.data.update(phase='completed',verified=True,completed_at=time.time())
        except Exception as exc:
            with self.lock:self.data.update(phase='failed',bytes_per_second=0,error=str(exc)[:250])
        finally:
            if sftp:sftp.close()
            if client:client.close()
            # Keep only the current generated payload locally; verified results contain its digest.
            if 'source' in locals():source.unlink(missing_ok=True)
            self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
            path=self.runtime/'transfer-evidence.json'
            with self.lock:content=json.dumps(self.data,ensure_ascii=False,indent=2)
            path.write_text(content);path.chmod(0o600)
