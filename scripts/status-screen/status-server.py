#!/data/data/com.termux/files/usr/bin/python
# Plex server status screen: a small web server on port 8099.
# Serves the files from ~/status/www plus /status.json, computed live on every request.
# The Plex token is read locally from Preferences.xml and never reaches the browser.
import glob
import json
import os
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# --- configuration ---
USB_ID = 'ABCD-1234'   # your USB drive ID, see: ls /storage
MEDIA_DIR = 'Media'    # top folder on the drive (contains Movies/ and TV Shows/)
# ---------------------

PORT = 8099
WWW = os.path.expanduser('~/status/www')
PREFIX = os.environ.get('PREFIX', '/data/data/com.termux/files/usr')
PREFS = PREFIX + ('/var/lib/proot-distro/containers/ubuntu/rootfs/var/lib/plexmediaserver'
                  '/Library/Application Support/Plex Media Server/Preferences.xml')
PLEX = 'http://127.0.0.1:32400'
USB_ROOT = '/storage/' + USB_ID
USB_CHECK = USB_ROOT + '/' + MEDIA_DIR
# heartbeat of the "Server Status" app (checked by ~/status/check-app.sh)
HEARTBEAT = os.path.expanduser('~/status/app-heartbeat')
# name, path, warning threshold (GB), alarm threshold (GB)
DISKS = [
    ('Phone storage', '/storage/emulated', 60, 40),
    ('Media drive', USB_ROOT, 100, 50),
]

_token = {'mtime': None, 'value': ''}


def plex_token():
    try:
        mtime = os.path.getmtime(PREFS)
        if mtime != _token['mtime']:
            with open(PREFS, encoding='utf-8') as f:
                m = re.search(r'PlexOnlineToken="([^"]+)"', f.read())
            _token.update(mtime=mtime, value=m.group(1) if m else '')
    except OSError:
        pass
    return _token['value']


def plex_get(path, token=None):
    req = urllib.request.Request(PLEX + path)
    if token:
        req.add_header('X-Plex-Token', token)
    with urllib.request.urlopen(req, timeout=5) as r:
        return ET.fromstring(r.read())


def plex_status():
    try:
        version = plex_get('/identity').get('version', '')
    except Exception:
        return {'online': False}, []
    sessions = []
    try:
        for v in plex_get('/status/sessions', plex_token()):
            user = v.find('User')
            player = v.find('Player')
            ts = v.find('TranscodeSession')
            if ts is None:
                decision = 'directplay'
            elif ts.get('videoDecision') == 'transcode' or ts.get('audioDecision') == 'transcode':
                decision = 'transcode'
            else:
                decision = 'directstream'
            if v.get('type') == 'episode':
                title = '{} · S{:02d}E{:02d}'.format(v.get('grandparentTitle', ''),
                                                     int(v.get('parentIndex', 0)), int(v.get('index', 0)))
                year = None
            else:
                title = v.get('title', '')
                year = v.get('year')
            duration = int(v.get('duration') or 0)
            offset = int(v.get('viewOffset') or 0)
            sessions.append({
                'user': user.get('title') if user is not None else '',
                'title': title,
                'year': int(year) if year else None,
                'player': player.get('title') if player is not None else '',
                'state': player.get('state') if player is not None else '',
                'decision': decision,
                'progress': round(offset / duration, 3) if duration else 0,
            })
    except Exception:
        pass
    return {'online': True, 'version': version}, sessions


def disks():
    out = []
    for name, path, warn, crit in DISKS:
        d = {'name': name, 'warn_gb': warn, 'crit_gb': crit}
        if path == USB_ROOT and not os.path.isdir(USB_CHECK):
            d['missing'] = True
        else:
            try:
                st = os.statvfs(path)
                d['total_kb'] = st.f_blocks * st.f_frsize // 1024
                d['free_kb'] = st.f_bavail * st.f_frsize // 1024
            except OSError:
                d['missing'] = True
        out.append(d)
    return out


def meminfo():
    mem = {}
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                k, v = line.split(':', 1)
                if k in ('MemTotal', 'MemAvailable'):
                    mem[k] = int(v.split()[0])
    except OSError:
        return None
    return {'total_kb': mem.get('MemTotal'), 'avail_kb': mem.get('MemAvailable')}


def cpu_temp():
    temps = []
    for z in glob.glob('/sys/class/thermal/thermal_zone*'):
        try:
            with open(z + '/type') as f:
                if not f.read().startswith('cpu-'):
                    continue
            with open(z + '/temp') as f:
                temps.append(int(f.read()) / 1000)
        except (OSError, ValueError):
            pass
    return round(sum(temps) / len(temps)) if temps else None


def uptime():
    try:
        out = subprocess.run(['uptime'], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return None
    m = re.search(r'up\s+(.*?),\s+\d+\s+users?', out)
    if not m:
        return None
    up = m.group(1)
    days = re.search(r'(\d+)\s+days?', up)
    hm = re.search(r'(\d+):(\d+)', up)
    mins = re.search(r'(\d+)\s+min', up)
    d = int(days.group(1)) if days else 0
    h = int(hm.group(1)) if hm else 0
    mi = int(hm.group(2)) if hm else (int(mins.group(1)) if mins else 0)
    return '{} d {} h'.format(d, h) if d else '{} h {} min'.format(h, mi)


def status():
    plex, sessions = plex_status()
    return {
        'generated': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'plex': plex,
        'sessions': sessions,
        'disks': disks(),
        'mem': meminfo(),
        'cpu_temp_c': cpu_temp(),
        'uptime': uptime(),
    }


class Handler(SimpleHTTPRequestHandler):
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map,
                          **{'.json': 'application/json', '.webmanifest': 'application/manifest+json'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WWW, **kwargs)

    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path == '/ping':
            if 'app=1' in query:
                with open(HEARTBEAT, 'a'):
                    pass
                os.utime(HEARTBEAT, None)
            body = b'ok'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/status.json':
            body = json.dumps(status(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def end_headers(self):
        if not self.path.startswith(('/status.json', '/ping')):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()
