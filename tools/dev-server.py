# Development server for previewing the status page in the Android emulator: the page comes from the repo folder
# (edits show up on reload), the data comes live from the real status server on the phone.
# /ping is answered locally so the emulator does not fake the phone app's heartbeat.
# Usage (Git Bash): python dev-server.py [www_folder]
# Emulator set up like the phone: adb reverse tcp:8099 tcp:8099, adb shell settings put system font_scale 1.0,
# adb shell wm size 1080x2400, adb shell wm density 480 (the emulator's default font scale 1.25 makes all text 25% bigger).
import json
import os
import sys
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WWW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'scripts', 'status-screen', 'www')
PHONE = 'http://192.168.1.50:8099'   # your phone's status server


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WWW, **k)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/ping':
            self.reply(b'ok', 'text/plain')
        elif path == '/status.json':
            try:
                with urllib.request.urlopen(PHONE + self.path, timeout=20) as r:
                    s = json.loads(r.read())
                self.reply(json.dumps(s, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')
            except Exception:
                self.send_error(502)
        elif path.startswith('/radio-proxy/'):
            # radio stations behind the proxy play through the phone's proxy (the station must be in the phone's radio.json)
            try:
                with urllib.request.urlopen(PHONE + self.path, timeout=20) as r:
                    self.send_response(200)
                    self.send_header('Content-Type', r.headers.get('Content-Type', 'audio/aac'))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    while True:
                        chunk = r.read(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception:
                try:
                    self.send_error(502)
                except Exception:
                    pass
        else:
            super().do_GET()

    def reply(self, body, ctype):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *a):
        pass


ThreadingHTTPServer.allow_reuse_address = True
print('dev server: http://127.0.0.1:8099 ->', os.path.abspath(WWW), flush=True)
ThreadingHTTPServer(('127.0.0.1', 8099), Handler).serve_forever()
