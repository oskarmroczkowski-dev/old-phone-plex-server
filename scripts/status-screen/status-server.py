#!/data/data/com.termux/files/usr/bin/python
# Plex server status screen: a small web server on port 8099.
# Serves the files from ~/status/www plus /status.json, computed live on every request.
# The Plex token is read locally from Preferences.xml and never reaches the browser.
# Also: /ping (heartbeat of the "Server Status" app) and /radio-proxy/<id> (radio streams the app cannot play directly).
import collections
import glob
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# --- configuration ---
USB_ID = 'ABCD-1234'   # your media USB drive ID, see: ls /storage
MEDIA_DIR = 'Media'    # top folder on the drive (contains Movies/ and TV Shows/)
KIDS_USB_ID = ''       # optional second drive (e.g. a separate kids library), e.g. 'EFGH-5678'; '' = none
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
# name, path, warning threshold (GB), alarm threshold (GB).
# The page shows these names as short labels (PHONE, MOVIES, KIDS), so keep them as they are.
DISKS = [
    ('Phone storage', '/storage/emulated', 60, 40),
    ('Media drive', USB_ROOT, 100, 50),
]
if KIDS_USB_ID:
    DISKS.append(('Kids drive', '/storage/' + KIDS_USB_ID, 50, 20))

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


def extra_volumes():
    """Other drives plugged into the phone (a flash drive, another USB drive). Termux cannot list /storage,
    but /proc/mounts shows every USB volume as /mnt/media_rw/<ID>."""
    known = {path for _, path, _, _ in DISKS}
    ids = []
    try:
        with open('/proc/mounts') as f:
            for line in f:
                parts = line.split()
                if len(parts) > 1 and parts[1].startswith('/mnt/media_rw/'):
                    vid = parts[1].rsplit('/', 1)[-1]
                    if vid not in ids and '/storage/' + vid not in known:
                        ids.append(vid)
    except OSError:
        pass
    out = []
    for vid in sorted(ids):
        try:
            st = os.statvfs('/storage/' + vid)
            out.append({'name': 'USB drive ' + vid, 'warn_gb': 10, 'crit_gb': 5,
                        'total_kb': st.f_blocks * st.f_frsize // 1024, 'free_kb': st.f_bavail * st.f_frsize // 1024})
        except OSError:
            pass
    return out


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
    return out + extra_volumes()


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


# --- CPU load ---
# Android does not let Termux read /proc/stat or /proc/loadavg, but the per-core idle times
# (/sys/devices/system/cpu/cpuN/cpuidle/stateM/time, in microseconds) are readable.
# Load = 1 - idle time / elapsed time, over a ~30 s window (one sample every 5 s).
CPU_DIR = '/sys/devices/system/cpu'
_cpu_hist = collections.deque(maxlen=7)


def _read_int(path):
    with open(path) as f:
        return int(f.read())


def cpu_idle_snapshot():
    snap = {}
    for c in glob.glob(CPU_DIR + '/cpu[0-9]*'):
        idle = usage = 0
        for st in glob.glob(c + '/cpuidle/state*'):
            try:
                idle += _read_int(st + '/time')
                usage += _read_int(st + '/usage')
            except (OSError, ValueError):
                pass
        try:
            at_min = _read_int(c + '/cpufreq/scaling_cur_freq') <= _read_int(c + '/cpufreq/cpuinfo_min_freq')
        except (OSError, ValueError):
            at_min = True
        snap[c.rsplit('/', 1)[-1]] = (idle, usage, at_min)
    return snap


def cpu_sampler():
    while True:
        _cpu_hist.append((time.monotonic(), cpu_idle_snapshot()))
        time.sleep(5)


def cpu_load():
    if len(_cpu_hist) < 2:
        return None
    (t0, a), (t1, b) = _cpu_hist[0], _cpu_hist[-1]
    dt = (t1 - t0) * 1e6
    loads = []
    for k, (idle, usage, at_min) in b.items():
        if k not in a or dt <= 0:
            continue
        didle, dusage = idle - a[k][0], usage - a[k][1]
        if didle == 0 and dusage == 0:
            # the core stayed in one state for the whole window (the idle counter is only updated on wake-up):
            # at the minimum clock it is asleep, otherwise it is busy the whole time
            loads.append(0.0 if at_min else 1.0)
        else:
            loads.append(1 - min(1.0, didle / dt))
    return round(100 * sum(loads) / len(loads)) if loads else None


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
        'cpu_load': cpu_load(),
        'uptime': uptime(),
    }


class Handler(SimpleHTTPRequestHandler):
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map,
                          **{'.json': 'application/json', '.webmanifest': 'application/manifest+json'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WWW, **kwargs)

    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path.startswith('/radio-proxy/'):
            self.radio_proxy(path.rsplit('/', 1)[-1])
        elif path == '/ping':
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

    def radio_proxy(self, sid):
        """Relays a station's 'upstream' stream from radio.json as audio/aac. Used for stations the app's Chromium
        engine rejects (AAC+ sent as audio/aacp) and for addresses that need the current time ({now}, Bauer/Rayo).
        For a station with a 'rayo' code the current address comes from the Rayo API first."""
        st = None
        try:
            with open(os.path.join(WWW, 'radio.json'), encoding='utf-8') as f:
                for g in json.load(f)['groups']:
                    for x in g['stations']:
                        if x.get('id') == sid:
                            st = x
        except Exception:
            pass
        if not st or not st.get('upstream'):
            self.send_error(404)
            return
        # addresses to try: Rayo station -> current address from the API (then a forced refresh), last the 'upstream'
        ups = []
        if st.get('rayo'):
            ups += [rayo_url(st['rayo']), lambda: rayo_url(st['rayo'], force=True)]
        ups.append(st['upstream'])
        tried = set()
        for up in ups:
            up = up() if callable(up) else up
            if not up or up in tried:
                continue
            tried.add(up)
            req = urllib.request.Request(up.replace('{now}', str(int(time.time()))),
                                         headers={'User-Agent': 'ServerStatus/1.3', 'Icy-MetaData': '0'})
            try:
                r = urllib.request.urlopen(req, timeout=15)
            except Exception:
                continue   # this address does not work: try the next one
            with r:
                self.send_response(200)
                self.send_header('Content-Type', 'audio/aac')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    while True:
                        chunk = r.read(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                except Exception:
                    pass   # the listener disconnected (stop/station change) or the station stopped sending
            return
        self.send_error(502)

    def end_headers(self):
        if not self.path.startswith(('/status.json', '/ping')):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *args):
        pass


# --- Bauer (Rayo) station addresses: from their API, cached for a day; the proxy fills in {now} ---
# Their streams answer HTTP 500 without aw_0_1st.skey = the current Unix time (their own web player sends it).
RAYO_API = 'https://listenapi.planetradio.co.uk/api9.2/stations/GB?premium=1'
_rayo = {'t': 0, 'urls': {}}
_rayo_lock = threading.Lock()


def rayo_url(code, force=False):
    with _rayo_lock:
        if force or time.time() - _rayo['t'] > 86400:
            try:
                req = urllib.request.Request(RAYO_API, headers={'User-Agent': 'ServerStatus/1.3'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                urls = {}
                for x in data:
                    aac = [y['streamUrl'] for y in x.get('stationStreams', [])
                           if not y.get('streamPremium') and y.get('streamType') == 'adts']
                    if aac:
                        sep = '&' if '?' in aac[0] else '?'
                        urls[x.get('stationCode')] = aac[0] + sep + 'aw_0_1st.skey={now}&aw_0_1st.playerid=BMUK_ukrp'
                if urls:
                    _rayo.update(t=time.time(), urls=urls)
            except Exception:
                _rayo['t'] = time.time() - 86400 + 600   # API not answering: try again in 10 min
        return _rayo['urls'].get(code)


if __name__ == '__main__':
    threading.Thread(target=cpu_sampler, daemon=True).start()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()
