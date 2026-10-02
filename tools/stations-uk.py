# Adds UK stations to radio.json in the given www folder and downloads their logos to www/logos.
# Bauer (Rayo): AAC stream through the proxy /radio-proxy/<id>; {now} in the address = current Unix time (required skey parameter).
# Global: fixed MP3 address with backups. BBC: HLS (Radio 2) and MP3 (World Service).
# Logos are trademarks of the stations: downloaded for personal use only, not part of this repository (www/logos is gitignored).
# Usage (Git Bash): first download the station lists to %TEMP%:
#   curl -s "https://listenapi.planetradio.co.uk/api9.2/stations/GB?premium=1" -o "$TEMP/st.json"
#   curl -s -A Mozilla/5.0 "https://bff-web-guacamole.musicradio.com/globalplayer/brands" -o "$TEMP/gb.json"
# then: python stations-uk.py <www folder>  (e.g. scripts/status-screen/www). Replaces the UK and BBC groups in radio.json.
import json
import os
import sys
import urllib.request

WWW = sys.argv[1]
TEMP = os.environ['TEMP']
UA = {'User-Agent': 'Mozilla/5.0'}

rayo = {s['stationName']: s for s in json.load(open(TEMP + '/st.json', encoding='utf-8'))}
glob = {b['name']: b for b in json.load(open(TEMP + '/gb.json', encoding='utf-8'))}


def bauer(sid, name, tag, rayo_name=None):
    s = rayo[rayo_name or name]
    base = [x['streamUrl'] for x in s['stationStreams'] if not x.get('streamPremium') and x.get('streamType') == 'adts'][0]
    return {'id': sid, 'name': name, 'tag': tag, 'url': 'http://127.0.0.1:8099/radio-proxy/' + sid,
            'upstream': base + '&aw_0_1st.skey={now}&aw_0_1st.playerid=BMUK_ukrp',
            'rayo': s['stationCode'], '_logo': s['stationListenBarLogo']}


def global_(sid, name, tag, code, brand):
    # backups: the same stream on Global's second server (media-ice) and the AAC version
    alt = ['https://media-ice.musicradio.com/' + code]
    if code.endswith('MP3'):
        alt.append('https://media-ssl.musicradio.com/' + code[:-3])
    return {'id': sid, 'name': name, 'tag': tag, 'url': 'https://media-ssl.musicradio.com/' + code, 'alt': alt,
            '_logo': glob[brand]['brandLogo']}


groups = [
    {'name': 'UK: easy listening', 'tab': 'UK relax', 'stations': [
        bauer('mellowmagic', 'Mellow Magic', 'relax'),
        bauer('magic', 'Magic Radio', 'pop, ballads'),
        bauer('magicsoul', 'Magic Soul', 'soul'),
        global_('smooth', 'Smooth Radio', 'relax', 'SmoothUKMP3', 'Smooth UK'),
        global_('smoothchill', 'Smooth Chill', 'chillout', 'SmoothChillMP3', 'Smooth Chill'),
        global_('smoothrelax', 'Smooth Relax', 'easy listening', 'SmoothRelaxMP3', 'Smooth Relax'),
        global_('smoothcountry', 'Smooth Country', 'country', 'SmoothCountryMP3', 'Smooth Country'),
        bauer('jazzfm', 'Jazz FM', 'jazz'),
        global_('classicfm', 'Classic FM', 'classical', 'ClassicFMMP3', 'Classic FM'),
        bauer('magicclassical', 'Magic Classical', 'classical'),
        bauer('magicmusicals', 'Magic Musicals', 'musicals'),
        bauer('magicxmas', 'Magic Christmas', 'Christmas', 'Magic Christmas'),
    ]},
    {'name': 'UK: decades', 'tab': 'UK decades', 'stations': [
        bauer('ghr', 'Greatest Hits Radio', 'hits'),
        bauer('ghr60', 'Greatest Hits 60s', '60s', 'Greatest Hits Radio 60s'),
        bauer('ghr70', 'Greatest Hits 70s', '70s', 'Greatest Hits Radio 70s'),
        bauer('ghr80', 'Greatest Hits 80s', '80s', 'Greatest Hits Radio 80s'),
        bauer('abs70', 'Absolute 70s', '70s', 'Absolute Radio 70s'),
        bauer('abs80', 'Absolute 80s', '80s'),
        bauer('abs90', 'Absolute 90s', '90s', 'Absolute Radio 90s'),
        global_('heart80', 'Heart 80s', '80s', 'Heart80sMP3', 'Heart 80s'),
        global_('heart90', 'Heart 90s', '90s', 'Heart90sMP3', 'Heart 90s'),
        global_('gold', 'Gold', 'oldies', 'GoldMP3', 'Gold Radio'),
    ]},
    {'name': 'UK: hits', 'tab': 'UK hits', 'stations': [
        global_('heart', 'Heart', 'pop', 'HeartUKMP3', 'Heart UK'),
        global_('heart00', 'Heart 00s', '2000s', 'Heart00sMP3', 'Heart 00s'),
        global_('heartdance', 'Heart Dance', 'dance', 'HeartDanceMP3', 'Heart Dance'),
        global_('capital', 'Capital', 'hits', 'CapitalMP3', 'Capital UK'),
        bauer('hits', 'Hits Radio', 'hits'),
        bauer('hits90', 'Hits Radio 90s', '90s', 'Hits Radio 90s'),
        bauer('hits00', 'Hits Radio 00s', '2000s', 'Hits Radio 00s'),
        bauer('hitschilled', 'Hits Radio Chilled', 'chillout'),
        bauer('hitspride', 'Hits Radio Pride', 'pop'),
        bauer('kiss', 'KISS', 'dance, hip-hop'),
        bauer('kisstory', 'KISSTORY', 'dance classics'),
        bauer('kisstoryrnb', 'KISSTORY R&B', 'R&B'),
        bauer('kissdance', 'KISS Dance', 'dance', 'KISS DANCE'),
        bauer('kissxtra', 'KISS Xtra', 'R&B, hip-hop', 'KISS XTRA'),
        bauer('heat', 'heat Radio', 'pop', 'heat Radio'),
        bauer('coololdskool', 'Cool Old Skool', 'old skool'),
        bauer('abs00', 'Absolute 00s', '2000s', 'Absolute Radio 00s'),
        bauer('abs10', 'Absolute 10s', '2010s', 'Absolute Radio 10s'),
        bauer('abs20', 'Absolute 20s', '2020s', 'Absolute Radio 20s'),
    ]},
    {'name': 'UK: rock', 'tab': 'UK rock', 'stations': [
        bauer('absolute', 'Absolute Radio', 'rock'),
        bauer('absclassicrock', 'Absolute Classic Rock', 'classic rock'),
        bauer('abscountry', 'Absolute Country', 'country', 'Absolute Radio Country'),
        bauer('planetrock', 'Planet Rock', 'rock'),
        bauer('kerrang', 'Kerrang! Radio', 'rock, metal'),
        global_('radiox', 'Radio X', 'alternative rock', 'RadioXUKMP3', 'Radio X UK'),
        global_('radioxclassic', 'Radio X Classic Rock', 'classic rock', 'RadioXClassicRockMP3', 'Radio X Classic Rock'),
    ]},
    {'name': 'BBC and LBC', 'tab': 'BBC', 'stations': [
        {'id': 'bbc2', 'name': 'BBC Radio 2', 'tag': 'pop, ballads',
         'url': 'http://as-hls-ww-live.akamaized.net/pool_74208725/live/ww/bbc_radio_two/bbc_radio_two.isml/bbc_radio_two-audio%3d96000.norewind.m3u8',
         'uuid': '3606ef8c-cd58-4440-8c47-dbf1e0cacdac', '_logo': 'https://cdn-radiotime-logos.tunein.com/s24940q.png'},
        {'id': 'bbcws', 'name': 'BBC World Service', 'tag': 'news', 'url': 'https://stream.live.vc.bbcmedia.co.uk/bbc_world_service',
         'uuid': '598c4d0e-6b06-43fb-bff4-717c591213a9', '_logo': 'http://cdn-profiles.tunein.com/s24948/images/logoq.jpg'},
        global_('lbc', 'LBC', 'talk', 'LBCUKMP3', 'LBC UK'),
    ]},
]

path = os.path.join(WWW, 'radio.json')
d = json.load(open(path, encoding='utf-8'))
d['groups'] = [g for g in d['groups'] if not g['name'].startswith('UK') and g['name'] != 'BBC and LBC']
os.makedirs(os.path.join(WWW, 'logos'), exist_ok=True)
for g in groups:
    for s in g['stations']:
        src = s.pop('_logo')
        ext = '.png' if '.png' in src.lower() else '.jpg'
        name = 'logos/uk-' + s['id'] + ext
        try:
            data = urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=20).read()
            open(os.path.join(WWW, name), 'wb').write(data)
            s['logo'] = name
            print('%-16s %6d B  %s' % (s['id'], len(data), name))
        except Exception as e:
            print('%-16s NO LOGO (%s)' % (s['id'], e))
    d['groups'].append(g)
json.dump(d, open(path, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)   # LF: the file goes to the phone
print('groups:', [(g['name'], len(g['stations'])) for g in d['groups']])
