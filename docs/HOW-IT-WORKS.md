# How it works

How the whole system fits together: components, what happens after the phone is switched on, how data flows, and who watches whom.

- How it was installed: [INSTALL-FROM-SCRATCH.md](INSTALL-FROM-SCRATCH.md)
- Day-to-day operation, paths, troubleshooting: [OPERATIONS.md](OPERATIONS.md)
- The status app's code: [../status-app/README.md](../status-app/README.md)

Example values used in all docs: phone IP `192.168.1.50`, LAN `192.168.1.x`, Termux user `u0_a123` (check yours with `whoami`), USB drive ID `ABCD-1234`, media folder `Media`.

---

## 1. Components

```
┌────────────────────── Old Android phone (Android 13, stock, no root) ──────────────────────┐
│                                                                                            │
│  Termux (Android app, Linux userland without root)       "Server Status" app (native)      │
│  ├─ sshd ............ port 8022 ◄── SSH / SFTP / drive M:  ├─ full-screen WebView          │
│  ├─ crond ........... scheduler (watchdogs, updates)       │    └─ http://127.0.0.1:8099/  │
│  ├─ termux-wake-lock  CPU never sleeps                      ├─ alarm at 06:00 / 23:00      │
│  ├─ status-server.py  port 8099 ◄── status page (LAN)       ├─ starts after reboot         │
│  │                    + /radio-proxy/<id>                   ├─ Termux watchdog (ping/min)  │
│  └─ proot-distro → Ubuntu 26.04                             └─ radio player, port 8098     │
│        └─ Plex Media Server ... port 32400 ◄── TVs, phones, browsers                       │
│              ├─ /media/usb1 = /storage/ABCD-1234 (USB drive, exFAT)                        │
│              └─ /media/usb2 = /storage/EFGH-5678 (optional second drive, e.g. NTFS)        │
│                                                                                            │
│  Termux:Boot ── after boot runs ~/.termux/boot/10-start-server                             │
└────────────────────────────────────────────────────────────────────────────────────────────┘
        ▲ Wi-Fi, IP 192.168.1.50 (DHCP reservation for the phone's fixed MAC)
        │
  Windows PC: drive M: (SSHFS-Win → SFTP), scp, ADB (wireless debugging), this repository
```

| Port | Listener | Purpose | Access |
|---|---|---|---|
| 8022 | `sshd` in Termux | SSH, SFTP, drive M: | only from 192.168.1.x, key auth only |
| 32400 | Plex Media Server | playback, Plex Web | home network (nothing forwarded on the router) |
| 8099 | `status-server.py` | status page, `/status.json`, `/ping`, `radio.json`, `/radio-proxy/<id>` | home network, no password, no Plex token exposed |
| 8098 | "Server Status" app (`ControlServer`) | radio control: `/radio/state`, `/radio/play?id=`, `/radio/stop`, `/radio/volume?v=`, `/radio/sleep?min=` | home network, no password (anyone at home can start the radio) |
| random (e.g. 39837) | Android wireless debugging | ADB from the PC | paired PC only; switches off after a reboot |

**Why it is built this way:** without root there is no systemd, no Docker and no ports below 1024 (so no SMB on port 445). Hence PRoot (Ubuntu running as a userland inside Termux), SSHFS instead of SMB, and our own start scripts instead of system services.

---

## 2. What happens after the phone is switched on

Measured on 2026-10-01 (times from the `reboot` command):

| Time | Event |
|---|---|
| 0 s | Android boots (no lock screen) |
| ~25 s | Wi-Fi turns on and scans. **Note:** with a weak signal (worse than ≈ -75 dBm) Android will not join on its own (see section 7) |
| ~50 s | Android sends `BOOT_COMPLETED` |
| | → **Termux:Boot** runs `~/.termux/boot/10-start-server` → `~/start-server.sh boot` |
| | → **Server Status** app (`BootReceiver`) sets its alarm and opens the dashboard (black until the page server is up; retries every 10 s) |
| ~50 s | `start-server.sh`: wake-lock → `sshd` → `crond` → `start-status.sh` (page on 8099) → waits for the USB drive (up to 60 s) → starts Ubuntu with `/root/start-plex.sh` |
| ~76 s | Plex answers on port 32400 |
| ~1.5 min | the dashboard shows live data; watchdogs are active (cron every 5 min, app every minute) |

Everything `start-server.sh` (re)starts is logged in `~/watchdog.log`:
```
2026-10-01 11:53:57 [boot] starting sshd
2026-10-01 11:53:58 [boot] starting Plex
```

---

## 3. Playing a film

```
TV (Plex app) ──► 192.168.1.50:32400 (Plex in Ubuntu/PRoot) ──► /media/usb1/... (USB drive over USB 2.0)
```
- **Direct Play (original quality)**: the file is streamed as-is and the phone barely works. TVs should use this.
- **Transcoding**: software only (no hardware transcoding without root). Measured: **up to three 1080p → 720p streams at once** (1.2–1.5× real time, CPU up to 86 %, max 71 °C). **4K cannot be transcoded** (0.1–0.4×).
- **4K needs Direct Play.** A 2021 Samsung TV plays 4K HEVC 10-bit **HDR10 up to 70 Mb/s** (SDR 40 Mb/s also smooth). Its Plex app declares a cap of 80 Mb/s, but at 80 Mb/s the screen stayed black; above the cap the TV asks for a transcode and playback fails. No Dolby Vision profile 5. A realme Android TV (4K panel) could not start 4K HEVC 10-bit at all, while 1080p plays fine, so give it 1080p versions.
- Throughput: USB drive → Wi-Fi **25 MB/s ≈ 200 Mb/s** (USB 2.0 port ~27 MB/s); Wi-Fi depends on the signal and on how the phone is placed. Details: [PERFORMANCE.md](PERFORMANCE.md).

---

## 4. Status dashboard: where the data comes from

```
WebView in the app ──every 1 min──► GET http://127.0.0.1:8099/status.json ──► status-server.py computes live:
                                                                         ├─ Plex: /identity (version), /status/sessions (who is watching; token read from Preferences.xml)
                                                                         ├─ drives: statvfs(/storage/emulated), statvfs(/storage/<USB_ID>), optional second
                                                                         │  drive, plus every other USB volume from /proc/mounts (/mnt/media_rw/<ID>)
                                                                         ├─ RAM: /proc/meminfo, CPU temperature: /sys/class/thermal/*/cpu-*
                                                                         ├─ CPU load: a thread reads per-core idle times every 5 s
                                                                         │  (/sys/devices/system/cpu/cpu*/cpuidle; /proc/stat is blocked for Termux), ~30 s average
                                                                         └─ uptime: `uptime` command
WebView ──once at start──► /earth.json (land outlines for the spinning Earth, Natural Earth 1:50m, ~32 KB)
WebView ──every 20 min (every 1 min after a failure)──► https://api.open-meteo.com (weather, no API key)
WebView ──every 15 s (5 s with the Radio panel open)──► http://127.0.0.1:8098/radio/state (radio state; listening time per
                                                     station is kept in localStorage → the 3 most-played stations)
WebView ──on demand──► window.StatusApp.battery() (battery level, charging, temperature; only inside the app)
Clock and date ──► the phone's clock, configurable time zone
```
- **The Plex token never leaves the phone**: only `status-server.py` reads it, and the page receives finished data.
- At night (23:00–06:00) the page is black and the app stops holding the screen on, so it turns off after the system timeout. At 06:00 an alarm turns it back on.
- AMOLED protection: dark UI, and the content shifts by a few pixels every minute.
- Drives are shown as rings: the arc and the percentage are the free space; copper normally, yellow at the warning threshold, red at the alarm threshold. Thresholds: phone storage yellow < 60 GB, red < 40 GB (realme may disable "RAM expansion" below that); media drive yellow < 100 GB, red < 50 GB; second drive 50/20 GB; any other USB drive 10/5 GB. An unmounted media drive shows an empty ring with a red "!" and "NOT CONNECTED".
- The background animation (Earth at 8 fps, stars and the zodiac sign at 4 fps) runs only in the daytime and in landscape; it costs the phone about 8–12 CPU points ([PERFORMANCE.md](PERFORMANCE.md)).

### Radio

```
page (phone or any LAN device) ──GET──► Status app :8098 (ControlServer) ──► RadioPlayer
                                                                ├─ HLS (.m3u8) → Android's native MediaPlayer
                                                                └─ other streams (Icecast MP3/AAC) → hidden Chromium <audio>
RadioPlayer ──► http://127.0.0.1:8099/radio.json (station list; a copy is kept in the app in case the server is down)
            ──► Radio Browser (de1 → nl1 → at1): the current address by uuid, as a backup
Stations with "upstream" ──► http://127.0.0.1:8099/radio-proxy/<id>: status-server.py relays the stream as audio/aac,
                            fills in {now} (current time) and, for Bauer/Rayo stations, takes the current address from their API
cron 04:30 ──► ~/status/check-stations.py ──► ~/status/www/radio-health.json (Radio panel) + ~/status/stations.log
```
- **Two engines** because realme's MediaPlayer never finishes preparing endless Icecast streams, while HLS works at once. Chromium plays Icecast fine but rejects the `audio/aacp` type, hence the proxy.
- **Failsafes** (app 1.3.3): quick retries every 5 s through all addresses (`url` → `alt` → Radio Browser); then, with no internet, it waits for the network without a limit and resumes by itself; with internet but a silent station it retries every 30 s…5 min for ~30 min, re-reading the addresses each time. Stop, the sleep timer and 23:00 end the waiting.
- The radio stops at 23:00 and when a Bluetooth speaker disconnects. Turned on at night, it sets a 1-hour sleep timer by itself.

---

## 5. Watchdogs: who guards whom

```
          cron (every 5 min) ──► start-server.sh cron ──► restarts: sshd, status page, Plex
          cron (every 5 min) ──► check-app.sh ──────────► daytime: reopens the Status app if silent for 15 min
                                                         (heartbeat: file ~/status/app-heartbeat)
   Status app (every 1 min) ──► GET /ping?app=1 ──► server touches app-heartbeat
                            └─ 3 failures in a row ──► RUN_COMMAND to Termux: start-server.sh status-app
                                                       (revives all of Termux: SSH, cron, page, Plex)
   update-server.sh (Sunday 04:00) ──► file ~/.update-in-progress ──► start-server.sh leaves Plex alone
          cron (04:30) ──► check-stations.py ─────► tests every radio station → www/radio-health.json, stations.log
   Status app, radio (1.3.3) ──► internet lost: waits for the network and resumes the station by itself;
                                 dead station: backup addresses (alt, Radio Browser), slow retries for ~30 min
```

**Protection against double starts:**
- `~/.start-server.lock`: two copies of `start-server.sh` never run at once. The lock stores the owner's PID. If that process is dead (for example Termux was killed), the lock is ignored.
- Plex is started only if neither Plex nor its launcher (`/root/start-plex.sh`) is already running.

Full table with timings and test results: [OPERATIONS.md, section 13](OPERATIONS.md#13-watchdogs-what-happens-when-something-stops).

---

## 6. Updates

| What | When | How |
|---|---|---|
| Termux packages | Sunday 04:00 | `update-server.sh`: `pkg upgrade` |
| Ubuntu + **Plex** | Sunday 04:00 | `apt-get upgrade` (Plex from `repo.plex.tv`) |
| Status page | manually | `scp` the new `index.html` |
| Status app | manually | `build.sh` + `adb install -r` |
| Android and its apps | not automatic | – |

Weekly update sequence: lock `~/.update-in-progress` → stop Plex → `pkg upgrade` → `apt upgrade` → remove the lock → `start-server.sh update` → check that Plex answers → write to `~/update.log`.

---

## 7. Network and its weak spots

- The phone uses its real (non-random) MAC address, and the router reserves `192.168.1.50` for it.
- **Wi-Fi is the weakest link.** When the 5 GHz signal dropped to about -80 dBm, Android did not reconnect by itself after a reboot: auto-join drops networks below a signal threshold. Tapping the network manually bypasses the threshold. Fixes: a better spot for the phone, a saved 2.4 GHz fallback network, or Ethernet through the USB-C hub.
- Wireless debugging (ADB) switches off after every reboot. Turn it on again in Developer options and find the port with `adb mdns services`.

---

## 8. Getting files onto the server

| Method | For | Notes |
|---|---|---|
| **Drive M:** (SSHFS-Win) | browsing, small files | large copies froze Windows and once corrupted a file silently ([LESSONS-LEARNED.md](LESSONS-LEARNED.md)) |
| **`scp`** | large films | ~21 MB/s, no freezes; verify with SHA-256 |
| (idea) via phone storage | many films at once | send fast to internal storage, a phone-side script moves files to the drive one by one ([OPERATIONS.md](OPERATIONS.md)) |

After adding files Plex scans by itself ("scan my library automatically" is on), or: library → "…" → Scan Library Files.

---

## 9. Where to look when something is wrong

| Log / command | Shows |
|---|---|
| `~/watchdog.log` | what the watchdogs restarted and who triggered it (cron, status app, boot) |
| `~/plex.log` | Plex start output |
| `~/update.log` | weekly updates |
| `~/status/server.log` | status page server starts |
| `~/status/stations.log` | nightly radio station checks (how many play, which are dead) |
| `curl http://192.168.1.50:8098/radio/state` | radio state; `info` says what the failsafe is doing |
| `crontab -l` | the schedule |
| `adb logcat -s StatusWatchdog` | the watchdog inside the Status app |
| `adb shell dumpsys alarm \| grep -A3 serwerplex` | the app's 06:00/23:00 alarm |
| `adb shell dumpsys wifi` | Wi-Fi, including why a network was rejected ("filtered out") |
