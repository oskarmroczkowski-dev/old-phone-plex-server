# Operations

Day-to-day reference for the running server: facts, paths, scripts, settings, commands, troubleshooting and security.

- How it works: [HOW-IT-WORKS.md](HOW-IT-WORKS.md) · Installation: [INSTALL-FROM-SCRATCH.md](INSTALL-FROM-SCRATCH.md) · Lessons: [LESSONS-LEARNED.md](LESSONS-LEARNED.md) · App: [../status-app/README.md](../status-app/README.md)

Example values used below: phone IP `192.168.1.50`, Termux user `u0_a123`, USB drive ID `ABCD-1234`, media folder `Media`, Wi-Fi `MyWifi-5G`.

---

## 1. Quick facts

| What | Value |
|---|---|
| Phone | realme GT Master Edition (RMX3363), Snapdragon 778G, 8 GB RAM, 256 GB |
| System | Android 13, realme UI 4.0, **no root**, bootloader locked |
| IP address | `192.168.1.50` (DHCP reservation on the router) |
| MAC address | device MAC (randomisation off), e.g. `aa:bb:cc:dd:ee:ff` |
| Plex in a browser | `http://192.168.1.50:32400/web` |
| SSH | `ssh -p 8022 u0_a123@192.168.1.50` (key only) |
| Linux | Ubuntu 26.04.1 LTS (ARM64) in PRoot inside Termux |
| Plex Media Server | 1.43.4 (updated automatically every week) |
| Media drive | USB, exFAT, ~1 TB, ID `ABCD-1234`, folder `Media` (`Movies/`, `TV Shows/`) |
| Auto-start after reboot | yes: about 1.5 min from power-on to a working Plex |
| Automatic updates | every Sunday 04:00 (Termux + Ubuntu + Plex) |
| Status dashboard | **Server Status** app, full screen, on 06:00–23:00 (section 12) |
| Status page on the LAN | `http://192.168.1.50:8099` |
| Something stopped? | watchdogs restart it (section 13); log `~/watchdog.log` |
| Large films to the server | **not through drive M:**, use `scp` (section 11) |

---

## 2. Architecture

```
Android phone (Android 13)
├── Termux (Linux terminal, a normal Android app)
│   ├── sshd             → SSH server on port 8022
│   ├── crond            → scheduler (Sunday updates, watchdogs every 5 min)
│   ├── wake-lock        → Android does not put the CPU to sleep with the screen off
│   ├── status-server.py → status page on port 8099 (Python)
│   └── proot-distro     → Ubuntu 26.04 (PRoot, no root)
│       └── Plex Media Server (port 32400)
│           └── /media/usb1  ←  bound USB drive /storage/ABCD-1234
└── "Server Status" app (native) → shows the status page full screen
```

- **Android stays a normal phone OS.** Ubuntu is not a separate system or a VM. It is a set of programs running inside the Termux app.
- **PRoot** emulates Ubuntu's file system without root. Computation runs at full CPU speed; operations on many small files are 2–3× slower.
- **Termux:Boot** starts everything automatically after a reboot.

### No-root limitations
- No systemd, no Docker, no regular firewall (`ufw`/`iptables`).
- No ports below 1024 (e.g. 80/443/445).
- **No hardware transcoding** in Plex. TVs should use **Direct Play** (original quality). Software transcoding was measured at up to **three 1080p → 720p streams at once**; **4K cannot be transcoded** ([PERFORMANCE.md](PERFORMANCE.md)).
- Use **exFAT** (or FAT32) for the media drive; it is the factory format of most portable SSDs and has a native kernel driver. NTFS probably works too: the system ships `ntfs-3g`, `mkntfs` and `ntfsfix`, and the kernel supports `fuseblk`. It is untested on a real NTFS drive and slower.
- If the battery ever drains to zero, the phone **will not switch on by itself** when power returns. Press the power button once and everything else comes back automatically.

---

## 3. Installed software

### On the phone (Android)
| App | Version | Source | Purpose |
|---|---|---|---|
| Termux | 0.118.3 | GitHub (`termux-app_v0.118.3+github-debug_arm64-v8a.apk`) | Linux terminal |
| Termux:Boot | 0.8.1 | GitHub (`termux-boot-app_v0.8.1+github.debug.apk`) | start after reboot |
| Server Status | 1.2 | this repository, [`status-app/`](../status-app/) | full-screen dashboard + Termux watchdog |

> Termux and Termux:Boot must come from the **same source** (GitHub). Don't mix them with Google Play or F-Droid builds: different signatures, they won't cooperate.

### In Termux
| Package | Version | Purpose |
|---|---|---|
| openssh | 10.5p1 | SSH server (`sshd`) |
| proot | 5.1.107.95 | running Linux without root |
| proot-distro | 5.9.0 | installing/managing Ubuntu |
| cronie | 1.7.2 | scheduler (`crond`) |
| python | 3.14.6 | status page server |

### In Ubuntu 26.04.1 LTS
- `plexmediaserver` 1.43.4 (official repository `https://repo.plex.tv/deb/ public main`)
- `curl`, `wget`, `git`, `nano`, `net-tools`, `htop`, `jq`, `ca-certificates`, `gnupg`
- Plex keys: `/usr/share/keyrings/plex.gpg`; repository: `/etc/apt/sources.list.d/plexmediaserver.list`

---

## 4. Important paths

### On the phone (Termux)
| Path | What |
|---|---|
| `~` = `/data/data/com.termux/files/home` | Termux home |
| `~/start-server.sh` | **main start script** + watchdog |
| `~/update-server.sh` | weekly update script |
| `~/.termux/boot/10-start-server` | run by Termux:Boot after a reboot |
| `~/.bashrc` | `~/start-server.sh termux-open` (runs when Termux is opened) |
| `~/.termux/termux.properties` | contains `allow-external-apps = true` (needed by the status app watchdog) |
| `~/.ssh/authorized_keys` | the PC's public key |
| `~/status/` | status page: `status-server.py`, `start-status.sh`, `check-app.sh`, `www/`, `server.log`, `app-heartbeat` |
| `~/watchdog.log` | everything the watchdogs (re)started |
| `~/plex.log` | Plex start output |
| `~/update.log` | updates (last 2000 lines) |
| `~/.start-server.lock`, `~/.update-in-progress` | locks (section 5) |
| `$PREFIX/etc/ssh/sshd_config` | SSH configuration (LAN only, no passwords) |
| `$PREFIX/var/lib/proot-distro/containers/ubuntu/rootfs` | Ubuntu's whole file system |
| `/storage/ABCD-1234/Media/` | the USB media drive as seen by Android/Termux |

### In Ubuntu
| Path | What |
|---|---|
| `/root/start-plex.sh` | starts Plex Media Server |
| `/usr/lib/plexmediaserver/` | Plex program files |
| `/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/` | **Plex data** (database, artwork, thumbnails, settings) |
| `…/Plug-in Support/Databases/com.plexapp.plugins.library.db` | library database |
| `…/Preferences.xml` | server settings including the **account token: never share it** |
| `/media/usb1/Media/Movies`, `/media/usb1/Media/TV Shows` | the libraries |

`/media/usb1` in Ubuntu is the same drive as `/storage/ABCD-1234` in Android (bound with `--bind` in `start-server.sh`).

### On the Windows PC
| Path | What |
|---|---|
| `C:\Users\<you>\.ssh\id_ed25519` | **private SSH key** for the phone. Never share it; without it you cannot log in |
| `C:\Users\<you>\.ssh\id_rsa` | copy of the same key for SSHFS-Win |
| `C:\Users\<you>\AppData\Local\Android\Sdk\platform-tools\adb.exe` | ADB |
| `status-app\keystore\` | **signing key** of the Server Status app (created by `build.sh`, not in git). Needed for updates |

---

## 5. Scripts

### `start-server.sh`
Starts whatever is not running. Safe to run any number of times. It is also the **watchdog**: cron runs it every 5 minutes.
1. Lock `~/.start-server.lock`: two copies never run at once. The lock stores its owner's PID; a lock left by a dead process (e.g. Termux killed) is ignored.
2. `termux-wake-lock`: keeps the CPU awake.
3. `sshd`: SSH server. It is detected by full path; `pgrep -x sshd` never matches because sshd re-executes itself with an absolute path.
4. `crond`: scheduler.
5. `~/status/start-status.sh`: status page on port 8099.
6. If the weekly update is running (`~/.update-in-progress` younger than 2 h), it stops here and leaves Plex alone.
7. If neither Plex nor its launcher is running: waits up to 60 s for the USB drive, then starts Ubuntu with the bound drive and `/root/start-plex.sh` inside.

Configure **`USB_ID`** and **`MEDIA_DIR`** at the top. The argument says who called it: `boot`, `termux-open`, `cron`, `status-app`, `update` (default `manual`). Every (re)start goes to `~/watchdog.log` (last 500 lines).

### `ubuntu/start-plex.sh` (inside Ubuntu as `/root/start-plex.sh`)
Sets Plex's environment variables and runs `Plex Media Server`. Needed because PRoot has no systemd.

### `update-server.sh`
Run by cron **every Sunday at 04:00**:
1. Creates `~/.update-in-progress`, so the watchdog won't start Plex mid-update. The file is also removed if the script is interrupted.
2. Stops Plex.
3. `pkg upgrade` (Termux).
4. `apt-get update && upgrade && autoremove && clean` in Ubuntu (Plex comes from the official repository).
5. Removes the lock and runs `start-server.sh update`.
6. Checks that Plex answers and logs the result to `~/update.log`.

### `termux-boot/10-start-server`
Goes to `~/.termux/boot/`. Termux:Boot runs it after every reboot; it calls `~/start-server.sh boot`.

### `crontab.txt`
```
0 4 * * 0   ~/update-server.sh          # updates, Sunday 04:00
*/5 * * * * ~/start-server.sh cron      # watchdog: SSH, cron, status page, Plex
*/5 * * * * ~/status/check-app.sh       # watchdog for the Server Status app
```

### `windows/fix-drive-M.cmd`
One-click repair of the network drive (section 11). Set `PHONE_IP`, `PHONE_USER`, `SSH_PORT`, `USB_ID`, `MEDIA_DIR`, `MOVIES_DIR` at the top.

### `status-screen/`
`status-server.py`, `start-status.sh`, `check-app.sh`, `www/`: the dashboard (section 12) and the app watchdog (section 13).

### `migrate-plex-paths.sql`
Example of a one-off rewrite of Windows paths in a migrated Plex database to `/media/usb1/Media/...`. Adjust it to your old paths and **run it only once**.

---

## 6. Android / realme settings

### Via ADB
- **Phantom process killer off:** `settings put global settings_enable_monitor_phantom_procs false`, `device_config set_sync_disabled_for_tests persistent`, `device_config put activity_manager max_phantom_processes 2147483647`. Without this, Android 12+ kills Termux's processes.
- **Battery optimisation (Doze) exemptions:** `dumpsys deviceidle whitelist +com.termux`, `+com.termux.boot`, `+pl.serwerplex.status`.
- **Storage for Termux:** `termux-setup-storage` → "Allow" (access to the USB drive).

### On screen (realme blocks these from ADB)
`settings put global/secure …`, `pm grant …` and `appops set …` fail with `WRITE_SECURE_SETTINGS` / `GRANT_RUNTIME_PERMISSIONS` / `MANAGE_APP_OPS_MODES`.

| Setting | Termux | Termux:Boot | Server Status |
|---|---|---|---|
| Battery usage → foreground activity | On | On | On |
| … background activity | On | On | On |
| … auto launch | On | On | On |
| … launch other apps | On | – | – |
| Display over other apps | On | – | On |
| "Run commands in Termux environment" permission | – | – | Allow |
| Lock in recent apps (≡ → ⋮ → Lock) | yes | – | yes |

- **Wi-Fi:** `MyWifi-5G` → Privacy → **Use device MAC** (so the router reservation always matches).
- **Screen timeout:** 30 s. During the day the Server Status app keeps the screen on; at night it turns off normally. Brightness: automatic.

### Removed bloatware
50 apps, list in [`lists/removed-apps-realme.txt`](../lists/removed-apps-realme.txt), removed with `pm uninstall -k --user 0`:
- frees RAM/CPU, not storage,
- **a factory reset brings them all back**,
- restore one: `adb shell cmd package install-existing <package>`.

---

## 7. Plex data and migration from Windows (generic)

- Copied from the old Windows server (`%LOCALAPPDATA%\Plex Media Server`): `Plug-in Support` (databases), `Metadata`, `Media` (thumbnails), about 21 GB.
- **Not** copied: `Cache`, `Codecs` (Windows-only), `Logs`, `Crash Reports`, `Updates`, and the server settings (kept in the Windows registry). As a result the phone has its own server identity.
- Paths rewritten with **Plex SQLite** (tables `media_parts`, `directories`, `media_streams`, `section_locations`), with a database backup made first.
- The server was claimed by a fresh Plex account.
- Badly named files were renamed to Plex's scheme, and one title with a non-Latin name was renamed and locked in Plex.

### File naming
```
Movies/Title (Year).mp4
TV Shows/Title (Year)/Season 01/Title - S01E01.mp4
```
After adding files Plex scans automatically, or: library → "…" → **Scan Library Files**.

---

## 8. Everyday commands

### SSH from the PC
```
ssh -p 8022 u0_a123@192.168.1.50
```
Key only. No password is set in Termux.

### Enter Ubuntu
```
proot-distro login ubuntu --bind /storage/ABCD-1234:/media/usb1
```

### Plex: status / stop / start
```
pgrep -fa "[P]lex Media Server"                          # running?
pkill -f "[P]lex Media Server"; pkill -f "[P]lex Plug"   # stop (the watchdog restarts it within 5 min!)
~/start-server.sh                                        # start (also sshd, crond, status page)
tail -50 ~/plex.log                                      # start log
```
> The `[P]lex` pattern is deliberate: without the brackets `pkill -f` would also match and kill your own SSH command.
> To keep Plex stopped for maintenance: `touch ~/.update-in-progress` (valid 2 h), then `rm ~/.update-in-progress`.

### Manual update
```
~/update-server.sh; tail -30 ~/update.log
```

### Schedule, load, temperature
```
crontab -l            # show       crontab -e   # edit
top; free -h
```
Normal idle: CPU ~95% idle, CPU 31–43 °C. A "load average" of 6–7 is an Android artefact, not real load.

### ADB
- USB cable: `adb -s <serial> shell …`
- **Wireless debugging** (no cable): Developer options → Wireless debugging **On** (it turns off after every reboot). With the PC already paired, only the port changes:
  ```
  adb mdns services                     # e.g. 192.168.1.50:39837
  adb connect 192.168.1.50:39837
  ```
  If mDNS finds nothing, scan the phone's ports 30000–50000 for an open one.
- Battery/current (ADB only, Termux has no access): `adb shell dumpsys battery`.

---

## 9. Troubleshooting

| Symptom | What to check / do |
|---|---|
| Plex does not answer | SSH → `pgrep -fa "[P]lex Media Server"`; if missing, `~/start-server.sh` and `tail ~/plex.log` (the watchdog would also restart it within 5 min) |
| SSH does not answer | Open Termux on the phone (runs `start-server.sh termux-open`). Check Wi-Fi and the IP |
| Nothing came back after a reboot | Check the Termux:Boot settings (auto launch, background). Open Termux:Boot once |
| No Wi-Fi after a reboot | Weak signal: Android auto-join rejects networks below a threshold (`adb shell dumpsys wifi` → "filtered out due to low signal strength"). Tap the network once, then improve the signal / add a 2.4 GHz fallback / use Ethernet |
| Films "unavailable" in Plex | Drive disconnected or its ID changed: `ls /storage/`. Update `USB_ID` in `start-server.sh` and `status-server.py` |
| New drive not visible | `adb shell sm list-volumes all` and `adb shell dumpsys mount \| grep fsType`. exFAT/FAT32 always work; NTFS probably does (ntfs-3g) but is untested. As a last resort reformat to **exFAT** (erases data!). Also check the hub's power |
| Phone battery draining | The USB-C hub must have **PD pass-through** (charger → hub → phone + drive) |
| An update broke something | `tail -100 ~/update.log`. Plex can be reinstalled from the plex.tv `.deb` (`dpkg -i`) |
| Buffering on 4K | First check that it is Direct Play: the status screen must say "original quality". If it says "transcoding", the TV cannot play the file natively (e.g. a 2021 Samsung TV accepts HEVC up to 80 Mb/s, no Dolby Vision profile 5, no image-based subtitles), and the phone cannot transcode 4K. If it is Direct Play, the Wi-Fi is weak: move the phone or use Ethernet through the hub |
| Drive M: disappeared | Run `fix-drive-M.cmd` |
| Copy to M: stalls / Windows freezes | Don't copy large files through M:. Use `scp` and verify with SHA-256 (section 11) |
| Dashboard black during the day | The page server is not up yet (the app retries every 10 s) or has died: `~/status/start-status.sh`, log `~/status/server.log` |
| Dashboard did not come back after a reboot | Open Server Status manually; check its settings (auto launch, display over other apps) |
| Dashboard shows the media drive "NOT CONNECTED" | Android unmounted the USB drive. Replug it or reboot the phone |
| Weather missing on the dashboard | No internet when the page loaded; it retries every minute and when the network returns |
| What did the watchdogs do? | `cat ~/watchdog.log` |

---

## 10. Security

- The server is **not exposed to the internet**: no ports forwarded on the router, UPnP off. Never forward 8022, 32400 or 8099.
- SSH: **key only** (`PasswordAuthentication no`) and **only from the LAN**. Appended to `$PREFIX/etc/ssh/sshd_config`:
  ```
  AllowUsers *@192.168.1.* *@127.0.0.1
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  ```
  If your home subnet changes (new router), update `AllowUsers`, or SSH will lock you out. Fix it on the phone in Termux: `nano $PREFIX/etc/ssh/sshd_config`, then `pkill -HUP -o sshd`. If you add a VPN such as Tailscale, add its range (e.g. `*@100.*`).
- Plex account: strong password and 2FA.
- Remote access: prefer a VPN (e.g. Tailscale) over opening ports.
- The status page (8099) is visible **on the LAN without a password**: it shows who watches what, disk space and RAM. It never exposes the Plex token.
- Protect `id_ed25519` like a password; keep the app's `keystore/` out of git.

---

## 11. Network drive M: (SSHFS-Win) and copying files

The phone's USB drive appears in Windows Explorer as **drive M:**.

| | |
|---|---|
| Address | `\\sshfs.kr\u0_a123@192.168.1.50!8022\storage\ABCD-1234\Media` |
| Technology | SSHFS-Win + WinFsp (SFTP over SSH, encrypted) |
| Authentication | `C:\Users\<you>\.ssh\id_rsa` (a copy of `id_ed25519`; SSHFS-Win only looks for that name) |
| Write speed | ~18–24 MB/s over Wi-Fi |
| Why not SMB? | SMB needs port 445; without root Android cannot open ports below 1024 |

Install: `winget install WinFsp.WinFsp` and `winget install SSHFS-Win.SSHFS-Win`.

### Reconnecting M:
**Easiest: run `scripts/windows/fix-drive-M.cmd`.** It:
1. checks that the phone answers on port 8022 (if not, suggests checking Wi-Fi / opening Termux),
2. **changes nothing if M: works** (it won't interrupt a running copy),
3. otherwise remaps M: and shows the result.

Manually:
```
net use M: /delete /y
net use M: "\\sshfs.kr\u0_a123@192.168.1.50!8022\storage\ABCD-1234\Media" /persistent:yes
```
> Known issue: once, after a normal Windows restart, M: disappeared although it was mapped with `/persistent:yes`, because Windows had not stored `HKCU\Network\M`. Most likely the mapping had been created from a restricted automation shell; mapping it from a normal user session should persist.

### Copying large files: NOT through M:
- Copying large films (≈ 1 GB+) through Explorer onto M: **froze Windows twice** (SSHFS-Win/WinFsp hangs; a known upstream issue).
- One file copied through M: had the **correct size but zeros from 200 MB to the end**. Size proves nothing; check SHA-256.
- **`scp` works reliably** (all files verified, ~21 MB/s, no freezes):
  ```
  scp -P 8022 "C:\Users\<you>\Videos\Title (Year).mp4" "u0_a123@192.168.1.50:/storage/ABCD-1234/Media/Movies/"
  certutil -hashfile "C:\Users\<you>\Videos\Title (Year).mp4" SHA256
  ssh -p 8022 u0_a123@192.168.1.50 "sha256sum '/storage/ABCD-1234/Media/Movies/Title (Year).mp4'"
  ```
- Measured: PC → phone over Wi-Fi with SSH encryption **95.5 MB/s**; phone USB 2.0 port → drive **~27 MB/s**. The USB 2.0 port is the bottleneck, not Wi-Fi or encryption.
- Plex "scan my library automatically" is on. A file being copied may get analysed mid-copy, so a script should write `name.part` and rename only after the checksum matches.

### Idea: copying through the phone's internal storage
Send films fast to a staging folder in Termux's internal storage (PC done in ~2 min for 12 GB), and let a phone-side cron script move them to the drive one by one, verify SHA-256 and delete the staging copy. Keep at least ~40 GB free on the phone: realme can switch off "RAM expansion" (swap on internal storage) when free space runs low (`persist.sys.oplus.nandswap.storage.min`). Not implemented yet.

---

## 12. Status dashboard

Full screen on the phone: **clock and date, weather** (now + every 3 h), **Plex** (running? who watches what, quality, progress), **free space** (phone storage and media drive, with warning colours), **RAM, CPU temperature, battery, uptime**.

```
Termux: status-server.py (port 8099)
  ├── /            → the page (~/status/www/index.html)
  ├── /status.json → live data: Plex (127.0.0.1:32400, token read locally), drives (statvfs),
  │                  RAM (/proc/meminfo), CPU (/sys/class/thermal), uptime
  └── /ping        → "ok"; with ?app=1 it also touches ~/status/app-heartbeat
"Server Status" app (pl.serwerplex.status)
  └── full-screen WebView → http://127.0.0.1:8099/
The page → weather from Open-Meteo (no key), clock from the phone
```

### Behaviour
| | |
|---|---|
| 06:00–23:00 | screen stays on; data refreshed every minute, weather every 20 min (after a failure every minute and immediately when the network returns) |
| 23:00 | the app stops holding the screen, so it turns off after the timeout; the page is black anyway |
| 06:00 | an alarm-clock-type alarm (not delayed by realme) turns the screen on and brings the dashboard to the front |
| 05:55 | the page reloads itself (memory hygiene) |
| Reboot | the app starts by itself; the screen stays black until the page server is up (retry every 10 s) |
| Leaving the app | Home button. Back does nothing. Full screen returns automatically when you come back |
| AMOLED protection | dark UI, content shifted a few pixels every minute, screen off at night |
| Other devices | same page at `http://192.168.1.50:8099` (without the phone battery, which only the app provides) |

Configuration at the top of `www/index.html`: `LANG` (`'en'` or `'pl'`), `CITY`, `LAT`, `LON`, `TZ`, `DAY_FROM`, `DAY_TO`.
Colour thresholds: phone storage yellow < 60 GB, red < 40 GB; media drive yellow < 100 GB, red < 50 GB; unmounted drive → red "NOT CONNECTED".

### Common tasks
**Change the page** (no app rebuild): edit `www/index.html`, then
```
scp -P 8022 scripts/status-screen/www/index.html u0_a123@192.168.1.50:status/www/
adb shell am force-stop pl.serwerplex.status; adb shell am start -n pl.serwerplex.status/.MainActivity
```
(or wait for the 05:55 reload).

**Page server state** (SSH): `pgrep -fa "^python.*status-server"`, `curl -s http://127.0.0.1:8099/status.json`, `cat ~/status/server.log`.

**Remove the dashboard permanently:** first delete the `check-app.sh` line from `crontab -e` (otherwise Termux keeps reopening the app), then uninstall the app and remove the `~/status/start-status.sh` line from `~/start-server.sh`.

---

## 13. Watchdogs: what happens when something stops

The parts watch each other. Every restart is logged in `~/watchdog.log`.

| What stops | Who brings it back | How fast | Tested (2026-10-01) |
|---|---|---|---|
| Phone reboot | Termux:Boot (`start-server.sh boot`) + the app (`BOOT_COMPLETED`) | ~1.5 min | ✅ SSH and Plex up 76 s after the reboot command; the app running right after |
| Plex (Termux alive) | cron → `start-server.sh cron` | ≤ 5 min | ✅ stopped, back and answering after 3 min 46 s |
| SSH (`sshd`) | cron → `start-server.sh cron` | ≤ 5 min | logic checked |
| cron itself (`crond`) | nobody right away (cron cannot restart itself); comes back on reboot, when Termux is opened, or when the app calls `start-server.sh` | – | rare |
| Status page server | cron, or the app | ≤ 3–5 min | ✅ the app revived it after ~2 min |
| **All of Termux** (swiped away, force-stopped) | the app: pings the page every minute; after 3 failures it runs `start-server.sh status-app` through Termux's `RUN_COMMAND` (at most once per 10 min) | ≤ 3–4 min | ✅ force-stopped → SSH, cron, page and Plex back after 2 min 44 s |
| **The Server Status app** (closed, force-stopped) | `check-app.sh` from cron: in daytime, if the app has not sent a heartbeat for 15 min, reopens it (at most every 15 min). Never at night, so the screen stays dark | ≤ 20 min | ✅ reopened, its 06:00/23:00 alarm re-created |
| "Close all" in recent apps | the lock on Termux and the app: nothing closes | – | ✅ |
| Sunday update stops Plex | `~/.update-in-progress` lock: the watchdog waits (lock expires after 2 h in case the script dies) | – | logic checked |

**What the watchdogs cannot fix:** Termux and the app dying at the same time (reboot helps), a Plex process that is alive but hung (`pkill -f "[P]lex Media Server"`, the watchdog restarts it), a fully drained battery (power on by hand) and an unmounted USB drive (the dashboard shows "NOT CONNECTED").

---

## 14. Ideas / TODO

- [ ] Remote access via Tailscale instead of open ports (then: Plex → Network → Secure connections: Required; Remote access: off).
- [ ] Ethernet through the USB-C hub (more stable than Wi-Fi).
- [ ] Wi-Fi after reboot: better phone placement or a saved 2.4 GHz fallback network.
- [ ] Copying through internal storage with a phone-side mover script (section 11).
- [ ] Battery permanently at 100 %: realme UI 4.0 has no fixed charge limit. A smart plug driven by a script (charge 40–80 %) would extend battery life.
- [ ] "Update Plex" button on the dashboard (check plex.tv for a newer version, update on tap from the phone only).
- [ ] Optional: Tautulli for watch history and notifications.
- [ ] Turn off USB debugging when no changes are planned.
