"""Read-only SMS telemetry sampler; stops at the authorized resource deadline."""
from datetime import datetime, timezone
import fcntl
import os
import time
from sms_lab import SmsLab

if __name__ == '__main__':
    initial = SmsLab()
    lock = os.open(initial.cloud.runtime/'sms-watch.lock',os.O_RDWR|os.O_CREAT,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    deadline = datetime.fromisoformat(initial.cloud.state['auto_release_at'].replace('Z','+00:00')).timestamp()
    previous = None
    while time.time() < deadline:
        try:
            lab = SmsLab()
            if lab.state.get('released'): break
            state = lab.observe()
            task = state.get('task',{})
            phase = (task.get('state'),task.get('subtask_info'))
            if phase != previous:
                print({'state':phase[0],'phase':phase[1],'speed_mbps':task.get('migrate_speed')},flush=True)
                previous = phase
            if task.get('state') == 'MIGRATE_SUCCESS': break
        except Exception as exc:
            # Keep the last observed evidence; never manufacture new samples on errors.
            print({'sampling_error':type(exc).__name__},flush=True)
        time.sleep(5)
