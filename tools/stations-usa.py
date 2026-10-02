# Adds US stations (pop, rock, country) to radio.json in the given www folder and downloads their logos.
# All of them use fixed MP3/AAC addresses.
# Logos are trademarks of the stations: downloaded for personal use only, not part of this repository (www/logos is gitignored).
# Usage: python stations-usa.py <www folder>. Replaces the USA groups in radio.json. Run after stations-uk.py (group order).
import json
import os
import sys
import urllib.request

WWW = sys.argv[1]
UA = {'User-Agent': 'Mozilla/5.0'}
L181 = 'https://www.181.fm/images/og181fmlogo.jpg'


def st(sid, name, tag, url, logo, uuid=None):
    s = {'id': sid, 'name': name, 'tag': tag, 'url': url}
    if uuid:
        s['uuid'] = uuid
    s['_logo'] = logo
    return s


groups = [
    {'name': 'USA: pop', 'tab': 'USA pop', 'stations': [
        st('us-power181', 'Power 181', 'top 40', 'https://listen.181fm.com/181-power_128k.mp3', L181),
        st('us-100hitz', '100hitz Top 40', 'top 40', 'http://pureplay.cdnstream1.com/6025_128.mp3',
           'https://100hitz.com/wp-content/uploads/2023/03/100hitz.com-png-08-e1678043645250.png'),
        st('us-star90s', 'Star 90s', '90s', 'https://listen.181fm.com/181-star90s_128k.mp3', L181),
        st('us-awesome80s', 'Awesome 80s', '80s', 'https://listen.181fm.com/181-awesome80s_128k.mp3', L181),
        st('us-mellowgold', 'Mellow Gold', 'mellow 70s–80s', 'https://listen.181fm.com/181-mellow_128k.mp3', L181, '961df1e3-0601-11e8-ae97-52543be04c81'),
        st('us-oldies', '181.FM Classic Hits', 'oldies', 'https://listen.181fm.com/181-greatoldies_128k.mp3', L181),
        st('us-ch109', 'Classic Hits 109', '70s–90s', 'https://broadcast.classichits109.com/70s-90s',
           'https://cdn-profiles.tunein.com/s297004/images/logog.png', '34135e58-c4b4-4aaa-89b3-c42254ba7307'),
        st('us-ch109soft', 'Soft Rock 109', 'yacht rock', 'https://broadcast.classichits109.com/softrock',
           'https://cdn.onlineradiobox.com/img/l/8/83758.v15.png', 'c4481bd4-0a22-44f5-bec0-1b2556ddbe89'),
    ]},
    {'name': 'USA: rock', 'tab': 'USA rock', 'stations': [
        st('us-kexp', 'KEXP Seattle', 'indie, alternative', 'http://live-mp3-128.kexp.org/kexp128.mp3',
           'https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/KEXP_logo_2022_%28one-color%29.svg/330px-KEXP_logo_2022_%28one-color%29.svg.png',
           '6a7508a9-27ab-11e8-91bf-52543be04c81'),
        st('us-rprock', 'Radio Paradise Rock', 'rock, no ads', 'http://stream.radioparadise.com/rock-128',
           'https://radioparadise.com/apple-touch-icon.png', '993bd810-f8e6-11e9-bbf2-52543be04c81'),
        st('us-rpmain', 'Radio Paradise', 'eclectic', 'http://stream.radioparadise.com/mp3-128',
           'https://radioparadise.com/apple-touch-icon.png', '6a61dd1f-e8f1-11e9-a96c-52543be04c81'),
        st('us-eagle', 'The Eagle', 'classic rock', 'https://listen.181fm.com/181-eagle_128k.mp3', L181),
        st('us-rock181', 'Rock 181', 'rock', 'https://listen.181fm.com/181-rock_128k.mp3', L181, '7ae2d6f0-05c3-42c6-9ae6-5c33d052b564'),
        st('us-buzz', 'The Buzz', 'alternative rock', 'https://listen.181fm.com/181-buzz_128k.mp3', L181),
    ]},
    {'name': 'USA: country', 'tab': 'USA country', 'stations': [
        st('us-wsm', 'WSM 650 Nashville', 'Grand Ole Opry', 'http://stream01048.westreamradio.com/wsm-am-mp3',
           'https://wsmradio.com/wp-content/uploads/sites/10/2025/04/cropped-WSM-Logo-Black.png?w=180', '96107c68-0601-11e8-ae97-52543be04c81'),
        st('us-highway', 'Highway 181', 'new country', 'https://listen.181fm.com/181-highway_128k.mp3', L181),
        st('us-kickin', "Kickin' Country", 'country', 'https://listen.181fm.com/181-kickincountry_128k.mp3', L181, 'd142e976-eb1a-4861-9e00-4d2c9fbd9e32'),
        st('us-90scountry', '90s Country', '90s', 'https://listen.181fm.com/181-90scountry_128k.mp3', L181),
        st('us-80scountry', '80s Country', '80s', 'https://listen.181fm.com/181-80scountry_128k.mp3', L181),
        st('us-americas', "America's Country", 'country', 'https://ais-sa2.cdnstream1.com/1976_128.mp3',
           'https://americascountry.us/images/logo-5001.png', '3b92f8c7-deac-4a81-8a9c-3b0f995d73e4'),
    ]},
]

path = os.path.join(WWW, 'radio.json')
d = json.load(open(path, encoding='utf-8'))
d['groups'] = [g for g in d['groups'] if not g['name'].startswith('USA')]
cache = {}
for g in groups:
    for s in g['stations']:
        src = s.pop('_logo')
        ext = '.png' if '.png' in src.lower() else '.jpg'
        name = 'logos/' + ('us-181fm.jpg' if src == L181 else s['id'] + ext)
        try:
            if name not in cache:
                data = urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=20).read()
                open(os.path.join(WWW, name), 'wb').write(data)
                cache[name] = len(data)
            s['logo'] = name
            print('%-16s %7d B  %s' % (s['id'], cache[name], name))
        except Exception as e:
            print('%-16s NO LOGO (%s)' % (s['id'], e))
    d['groups'].append(g)
json.dump(d, open(path, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)   # LF: the file goes to the phone
print('groups:', [(g['name'], len(g['stations'])) for g in d['groups']])
