"""Transfer protocol tests; isolated fake receiver, never provisions cloud resources."""
import hashlib
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from transfer import TransferJob


class Stream(io.BytesIO):
    @property
    def channel(self):return self
    def recv_exit_status(self):return 0


class Receiver:
    def __init__(self,corrupt=False,barrier=None):
        self.content=b'';self.renamed=False;self.corrupt=corrupt;self.barrier=barrier
    def exec_command(self,command,timeout):
        digest=('0'*64 if self.corrupt else hashlib.sha256(self.content).hexdigest()).encode()
        return None,Stream(digest+b' file\n'),Stream()
    def open_sftp(self):return self
    def get_channel(self):return self
    def settimeout(self,value):pass
    def put(self,source,target,callback,confirm):
        if self.barrier:self.barrier.wait(5)
        self.content=Path(source).read_bytes()
        for size in range(1024,len(self.content)+1,1024):callback(size,len(self.content))
    def stat(self,target):
        class Stat:pass
        s=Stat();s.st_size=len(self.content);return s
    def rename(self,source,target):self.renamed=True
    def close(self):pass


class TransferTests(unittest.TestCase):
    def test_real_byte_count_and_checksum_gate(self):
        for corrupt in (False,True):
            with tempfile.TemporaryDirectory() as root:
                receiver=Receiver(corrupt)
                job=TransferJob(lambda:receiver,runtime=root,size_bytes=4096)
                job.start();job.worker.join(5)
                self.assertFalse(job.worker.is_alive())
                state=job.snapshot()
                self.assertEqual(state['sent_bytes'],4096)
                self.assertEqual(state['verified'],not corrupt)
                self.assertEqual(receiver.renamed,not corrupt)
                self.assertEqual(state['phase'],'failed' if corrupt else 'completed')
                self.assertTrue((Path(root)/'transfer-evidence.json').exists())
                self.assertFalse(list(Path(root).glob('*.synthetic.bin')))
                self.assertEqual(TransferJob(runtime=root).snapshot()['verified'],not corrupt)

    def test_live_rate_is_measured_and_overlapping_job_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            barrier=threading.Event();receiver=Receiver(barrier=barrier)
            job=TransferJob(lambda:receiver,runtime=root,size_bytes=4096)
            job.start()
            with self.assertRaises(ValueError):job.start()
            barrier.set();job.worker.join(5)
            job.started=0;job.window.clear();job.window.append((0,0));job.last_sample=0
            with patch('transfer.time.monotonic',return_value=1):job.update(1048576,2097152)
            self.assertEqual(job.snapshot()['bytes_per_second'],1048576)
            self.assertEqual(job.snapshot()['average_bytes_per_second'],1048576)


if __name__=='__main__':unittest.main()
