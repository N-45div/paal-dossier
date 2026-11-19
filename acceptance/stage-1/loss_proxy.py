"""Forward provider traffic to the mock, then drop each answer before delivery."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket


class LossProxy(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/_fault/health':
            self.send_response(200)
            self.end_headers()
            return
        self.drop_after_forward()

    def do_POST(self):
        self.drop_after_forward()

    def drop_after_forward(self):
        size = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(size)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'connection', 'content-length', 'transfer-encoding')}
        upstream = HTTPConnection('mock', 8080, timeout=20)
        try:
            upstream.request(self.command, self.path, body=body, headers=headers)
            upstream.getresponse().read()
        finally:
            upstream.close()
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()


ThreadingHTTPServer(('0.0.0.0', 8080), LossProxy).serve_forever()
