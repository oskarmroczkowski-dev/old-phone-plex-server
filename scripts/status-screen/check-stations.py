#!/data/data/com.termux/files/usr/bin/python
# Nightly radio station check (cron, 4:30): does audio flow from every station in ~/status/www/radio.json?
# Result: ~/status/www/radio-health.json (the Radio panel greys out dead stations with ⚠) and ~/status/stations.log.
# A station behind the proxy (upstream) is tested through /radio-proxy/<id>, i.e. together with the proxy.
# When the main address fails, the backups are tried ("alt" and the current address from Radio Browser by uuid):
# if one of them plays, the station is "on backup" (the app uses it by itself), not dead. radio.json is never changed.
import concurrent.futures
import json
import os
import time
import urllib.parse
import urllib.request

WWW = os.path.expanduser('~/status/www')
LOG = os.path.expanduser('~/status/stations.log')
PROXY = 'http://127.0.0.1:8099/radio-proxy/'
RB_HOSTS = ['de1', 'nl1', 'at1']
UA = {'User-Agent': 'ServerStatus/1.3.3', 'Icy-MetaData': '0'}


def get(url, n, timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(n)


def plays(url):
    """True if audio data arrives within a few seconds (HLS: playlist and the first segment)."""
    try:
        if '.m3u8' in url:
            for _ in range(3):   # master playlist -> variant playlist -> segment
                text = get(url, 65536).decode('utf-8', 'replace')
                lines = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith('#')]
                if not lines:
                    return False
                nxt = urllib.parse.urljoin(url, lines[-1])
                if '.m3u8' not in nxt:
                    return len(get(nxt, 4096)) >= 1024
                url = nxt
            return False
        return len(get(url, 16384)) >= 8192
    except Exception:
        return False


def rb_url(uuid):
    for h in RB_HOSTS:
        try:
            return json.loads(get('https://%s.api.radio-browser.info/json/url/%s' % (h, uuid), 1 << 16, 8)).get('url', '')
        except Exception:
            continue
    return ''


def check(st):
    main = PROXY + st['id'] if st.get('upstream') else st.get('url', '')
    if main and plays(main):
        return st, 'ok'
    backups = list(st.get('alt', []))
    if st.get('uuid'):
        backups.append(rb_url(st['uuid']))
    for u in backups:
        if u and u != main and plays(u):
            return st, 'backup'
    return st, 'dead'


if __name__ == '__main__':
    with open(os.path.join(WWW, 'radio.json'), encoding='utf-8') as f:
        stations = [s for g in json.load(f)['groups'] for s in g['stations']]
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(check, stations))
    dead = [s['id'] for s, r in res if r == 'dead']
    backup = [s['id'] for s, r in res if r == 'backup']
    stamp = time.strftime('%Y-%m-%d %H:%M')
    tmp = os.path.join(WWW, 'radio-health.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'checked': stamp, 'total': len(res), 'dead': dead, 'backup': backup}, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(WWW, 'radio-health.json'))
    names = {s['id']: s['name'] for s in stations}
    line = '%s  stations %d, playing %d, on backup %d%s, dead %d%s' % (
        stamp, len(res), len(res) - len(dead) - len(backup), len(backup),
        (' (' + ', '.join(names[i] for i in backup) + ')') if backup else '', len(dead),
        (' (' + ', '.join(names[i] for i in dead) + ')') if dead else '')
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    try:   # keep the log from growing forever
        with open(LOG, encoding='utf-8') as f:
            lines = f.readlines()[-200:]
        with open(LOG, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception:
        pass
