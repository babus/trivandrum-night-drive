#!/usr/bin/env python3
"""Dev server that serves the pre-compressed .gz when the browser accepts gzip.

    python3 serve.py [port]

Binds to all interfaces so a phone on the same WiFi can reach it. Prints the LAN
URL on start. Python's stock http.server does no compression at all, which on this
project means shipping 14 MB instead of ~3 MB.
"""
import http.server
import mimetypes
import os
import shutil
import socket
import socketserver
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8733


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'trivandrum-night-drive'

    def do_GET(self):
        self._serve(send_body=True)

    def do_HEAD(self):
        self._serve(send_body=False)

    def _serve(self, send_body):
        rel = self.path.split('?', 1)[0].split('#', 1)[0].lstrip('/')
        if not rel or rel.endswith('/'):
            rel += 'index.html'

        path = os.path.normpath(os.path.join(ROOT, rel))
        if not path.startswith(ROOT) or not os.path.isfile(path):
            self.send_error(404, 'Not found')
            return

        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype in ('application/javascript', 'application/json'):
            ctype += '; charset=utf-8'

        # Use the .gz only if it exists and is no older than the file it mirrors,
        # so a rebuild never serves stale compressed bytes.
        gz = path + '.gz'
        use_gz = (
            'gzip' in self.headers.get('Accept-Encoding', '')
            and os.path.isfile(gz)
            and os.path.getmtime(gz) >= os.path.getmtime(path)
        )
        served = gz if use_gz else path

        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(os.path.getsize(served)))
        if use_gz:
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Vary', 'Accept-Encoding')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

        if send_body:
            try:
                with open(served, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass  # browser navigated away mid-download

    def log_message(self, fmt, *args):
        sys.stderr.write('  %s\n' % (fmt % args))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))          # no packets sent; just picks the route
        return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        s.close()


if __name__ == '__main__':
    idx = os.path.join(ROOT, 'index.html')
    if os.path.isfile(idx):
        raw = os.path.getsize(idx)
        gzp = idx + '.gz'
        if os.path.isfile(gzp):
            print('index.html %.1f MB, gzip %.1f MB' % (raw / 1048576, os.path.getsize(gzp) / 1048576))
        else:
            print('index.html %.1f MB — no .gz found, run: python3 src/build.py' % (raw / 1048576))

    print('\n  Desktop:  http://localhost:%d/' % PORT)
    print('  Phone:    http://%s:%d/\n' % (lan_ip(), PORT))
    with Server(('0.0.0.0', PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nstopped')
