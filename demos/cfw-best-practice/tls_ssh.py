"""Authenticated TLS wrapper for this lab's localhost SSH, never an open proxy."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import select
import socket
import ssl

TOKEN = Path('/opt/cfw-lab/tls-token').read_text().strip()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(b'cfw-owned-tls-ssh')

    def do_CONNECT(self):
        if self.path != '/ssh' or not secrets.compare_digest(self.headers.get('Authorization',''), 'Bearer '+TOKEN):
            self.send_error(403);return
        upstream = socket.create_connection(('127.0.0.1',22),timeout=10)
        self.send_response(200);self.end_headers();self.wfile.flush()
        self.connection.settimeout(45);upstream.settimeout(45)
        try:
            while True:
                ready = [self.connection] if self.connection.pending() else select.select([self.connection,upstream],[],[],45)[0]
                if not ready:return
                for source in ready:
                    payload=source.recv(65536)
                    if not payload:return
                    (upstream if source is self.connection else self.connection).sendall(payload)
        finally:upstream.close()

    def log_message(self,*args):pass


if __name__ == '__main__':
    server=ThreadingHTTPServer(('0.0.0.0',443),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain('/opt/cfw-lab/tls.crt','/opt/cfw-lab/tls.key')
    server.socket=context.wrap_socket(server.socket,server_side=True)
    server.serve_forever()
