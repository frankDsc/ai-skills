"""Fixed HTTP probe code sent to an API-verified owned ECS over pinned SSH."""
import http.client
import json
import socket
import time


def run(host, port, public_source, marker):
    measurements = []
    for i in range(3):
        record = {'request_id': marker+'-'+str(i), 'started_at': int(time.time()*1000),
                  'src_ip': public_source, 'dst_ip': host, 'dst_port': port, 'protocol': 'TCP'}
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0)); s.settimeout(4)
        record['src_port'] = s.getsockname()[1]
        start = time.perf_counter()
        conn = None
        try:
            s.connect((host, port))
            conn = http.client.HTTPConnection(host, port, timeout=4); conn.sock = s
            conn.request('GET', '/orders?run='+record['request_id'], headers={'Connection': 'close'})
            response = conn.getresponse()
            body = response.read(65537)
            if len(body) > 65536: raise ValueError('response_limit')
            record.update(http_status=response.status, bytes=len(body), error=None,
                          synthetic=json.loads(body).get('synthetic') is True)
        except Exception as e:
            record.update(http_status=None, bytes=0, error=type(e).__name__, synthetic=False)
        finally:
            if conn: conn.close()
            s.close()
        record.update(elapsed_ms=round((time.perf_counter()-start)*1000, 3), finished_at=int(time.time()*1000))
        measurements.append(record)
        time.sleep(0.2)
    return measurements
