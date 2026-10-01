# Install from scratch

How the server was built step by step (2026-09-29 → 2026-10-01), with the commands that were actually used.
Use it to rebuild after a factory reset, or on another Android phone.

- How the finished system works: [HOW-IT-WORKS.md](HOW-IT-WORKS.md)
- Day-to-day operation: [OPERATIONS.md](OPERATIONS.md)
- The status app: [../status-app/README.md](../status-app/README.md)

> `adb` commands run on the PC (PowerShell or Git Bash). Lines marked **Termux:** run in Termux on the phone (over SSH or on screen); lines marked **Ubuntu:** run inside `proot-distro login ubuntu`.
> Example values (replace with yours): ADB serial `<serial>` (from `adb devices`) or `192.168.1.50:<port>` for wireless debugging; phone IP `192.168.1.50`; Termux user `u0_a123` (`whoami`); USB drive ID `ABCD-1234`; media folder `Media`.

---

## 0. What you need

| On the PC (Windows) | On the phone |
|---|---|
| Android SDK platform-tools (`adb`), e.g. `C:\Users\<you>\AppData\Local\Android\Sdk\platform-tools\` | Android 12+ (here: Android 13, realme UI 4.0), **no root** |
| OpenSSH (built into Windows) and Git Bash | Developer options → **USB debugging** on |
| Python 3 (helper scripts) | USB drive, preferably **exFAT** (the factory format of most portable SSDs; NTFS probably works too via the system's `ntfs-3g`, but untested and slower) + a USB-C hub with **PD pass-through** |
| For the status app: JDK 17 + Android SDK (build-tools 36.0.0, platform android-36) | Wi-Fi with a good signal (see section 8) |

---

## 1. Prepare Android (ADB over a USB cable)

**1.1. Check the phone**
```
adb devices -l
adb -s <serial> shell "getprop ro.build.version.release; getprop ro.build.display.id; grep MemTotal /proc/meminfo; df -h /data | tail -1"
```

**1.2. Remove bloatware** (for user 0 only, no root needed). The list of 50 packages removed on the realme: [`lists/removed-apps-realme.txt`](../lists/removed-apps-realme.txt).
```
adb -s <serial> shell pm uninstall -k --user 0 <package>
```
To bring one back: `adb shell cmd package install-existing <package>`. A factory reset restores all of them.

**1.3. Disable the "phantom process killer"** (Android 12+ kills Termux child processes) and animations:
```
adb -s <serial> shell "settings put global settings_enable_monitor_phantom_procs false; device_config set_sync_disabled_for_tests persistent; device_config put activity_manager max_phantom_processes 2147483647"
adb -s <serial> shell "settings put global window_animation_scale 0; settings put global transition_animation_scale 0; settings put global animator_duration_scale 0"
```

**1.4. Install Termux from GitHub** (not from Google Play): `termux-app_v0.118.3+github-debug_arm64-v8a.apk` from https://github.com/termux/termux-app/releases
```
adb -s <serial> install termux-app_v0.118.3+github-debug_arm64-v8a.apk
adb -s <serial> shell "dumpsys deviceidle whitelist +com.termux; cmd appops set com.termux RUN_ANY_IN_BACKGROUND allow; cmd appops set com.termux RUN_IN_BACKGROUND allow"
```
> Termux and Termux:Boot must come from the **same source** (GitHub). Different sources have different signatures and will not work together.

---

## 2. Termux and SSH

**2.1. First Termux start** (on the phone screen, needs internet):
```
Termux:  pkg update -y && yes | pkg upgrade -y
Termux:  pkg install -y openssh
```

**2.2. An SSH key on the PC**, **without a passphrase** (SSHFS-Win and the scripts need it that way):
```
ssh-keygen -t ed25519 -N "" -f C:\Users\<you>\.ssh\id_ed25519
```
Add the content of `id_ed25519.pub` on the phone:
```
Termux:  mkdir -p ~/.ssh && echo "<public key>" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
Termux:  termux-wake-lock && sshd
```

**2.3. Test** (first over the cable with port forwarding, later over Wi-Fi):
```
adb -s <serial> forward tcp:8022 tcp:8022
ssh -p 8022 u0_a123@127.0.0.1 "whoami; nproc; free -h"
```
`u0_a123` is the Termux user. Check yours with `whoami`; it differs per phone.

**2.4. SSH only from the home network, no passwords** (`$PREFIX/etc/ssh/sshd_config`):
```
Termux:  C=$PREFIX/etc/ssh/sshd_config; cp $C $C.bak
Termux:  printf "\nAllowUsers *@192.168.1.* *@127.0.0.1\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n" >> $C
Termux:  sshd -t && pkill -HUP -o sshd
```

---

## 3. Ubuntu (PRoot) and Plex Media Server

**3.1. Ubuntu**
```
Termux:  pkg install -y proot-distro
Termux:  proot-distro install ubuntu
```
Ubuntu's file system lives in `$PREFIX/var/lib/proot-distro/containers/ubuntu/rootfs`.

**3.2. Tools and Plex** (first install from the `.deb` published by plex.tv):
```
Ubuntu:  export DEBIAN_FRONTEND=noninteractive
Ubuntu:  apt-get update && apt-get upgrade -y && apt-get install -y curl wget git nano net-tools htop jq ca-certificates gnupg
Ubuntu:  URL=$(curl -s https://plex.tv/api/downloads/5.json | jq -r '.computer.Linux.releases[] | select(.build=="linux-aarch64" and .distro=="debian") | .url')
Ubuntu:  wget -O /tmp/plex.deb "$URL" && dpkg -i /tmp/plex.deb
```

**3.3. Official Plex apt repository** (so Plex updates with `apt`):
```
Ubuntu:  for u in https://downloads.plex.tv/plex-keys/PlexSign.v2.key https://downloads.plex.tv/plex-keys/PlexSign.key; do curl -fsSL $u; echo; done | gpg --dearmor --yes -o /usr/share/keyrings/plex.gpg
Ubuntu:  echo "deb [signed-by=/usr/share/keyrings/plex.gpg] https://repo.plex.tv/deb/ public main" > /etc/apt/sources.list.d/plexmediaserver.list
Ubuntu:  apt-get update && apt-cache policy plexmediaserver
```

**3.4. Plex launcher inside Ubuntu**: `/root/start-plex.sh` ([`scripts/ubuntu/start-plex.sh`](../scripts/ubuntu/start-plex.sh)). PRoot has no systemd, so `service plexmediaserver start` does not work.
```bash
#!/bin/bash
export PLEX_MEDIA_SERVER_APPLICATION_SUPPORT_DIR="/var/lib/plexmediaserver/Library/Application Support"
export PLEX_MEDIA_SERVER_HOME=/usr/lib/plexmediaserver
export PLEX_MEDIA_SERVER_MAX_PLUGIN_PROCS=6
export LD_LIBRARY_PATH=/usr/lib/plexmediaserver/lib
mkdir -p "$PLEX_MEDIA_SERVER_APPLICATION_SUPPORT_DIR"
cd /usr/lib/plexmediaserver
exec ./"Plex Media Server"
```
Then `chmod +x /root/start-plex.sh`.

**3.5. First Plex setup** (claim the server for your account): forward the port and open Plex Web on the PC:
```
adb -s <serial> forward tcp:32400 tcp:32400      →   http://127.0.0.1:32400/web
```
A fresh Plex server can only be claimed from a local address, and `127.0.0.1` through the ADB forward counts as local.

---

## 4. USB drive

**4.1. Storage access for Termux** (the USB drive shows up as `/storage/<ID>`):
```
adb shell "pm grant com.termux android.permission.READ_EXTERNAL_STORAGE; pm grant com.termux android.permission.WRITE_EXTERNAL_STORAGE"
Termux:  termux-setup-storage        → tap "Allow" on the phone
```

**4.2. Find the drive and its ID**:
```
adb shell "sm list-volumes all; ls /storage"            → e.g. ABCD-1234
Termux:  ls "/storage/ABCD-1234/Media"
Termux:  ln -sfn "/storage/ABCD-1234/Media" ~/Media
```
Ubuntu sees the drive as `/media/usb1` because of `--bind /storage/ABCD-1234:/media/usb1` in `start-server.sh`. Put your drive ID in **`USB_ID`** and your top folder in **`MEDIA_DIR`** at the top of `scripts/start-server.sh` and `scripts/status-screen/status-server.py`.

**4.3. File naming** (Plex identifies films and episodes by it):
```
Movies/Title (Year).mp4
TV Shows/Title (Year)/Season 01/Title - S01E01.mp4
```

---

## 5. Moving an existing Plex library from Windows (optional)

1. On Windows, stop Plex and copy **`Plug-in Support`**, **`Metadata`** and **`Media`** from `%LOCALAPPDATA%\Plex Media Server` (about 21 GB here; a USB stick works). Do not copy `Cache`, `Codecs`, `Logs`, `Crash Reports` or `Updates`; this way the phone gets its own server identity.
2. Stop Plex on the phone and stream the data over SSH (example: the copy is on drive `J:`):
   ```
   cd "/j/Plex Media Server" && tar -cf - "Plug-in Support" Metadata Media | ssh -p 8022 u0_a123@127.0.0.1 'D="$PREFIX/var/lib/proot-distro/containers/ubuntu/rootfs/var/lib/plexmediaserver/Library/Application Support/Plex Media Server"; mkdir -p "$D"; cd "$D" && tar -xf -'
   ```
3. Back up the database first (e.g. `lib.db.before-migration` in `Plug-in Support/Databases`).
4. Rewrite the Windows paths to `/media/usb1/Media/...` with **Plex SQLite** (tables `media_parts`, `directories`, `media_streams`, `section_locations`). Example: [`scripts/migrate-plex-paths.sql`](../scripts/migrate-plex-paths.sql); adjust the drive letters and folders. **Run it once only.**
5. Start Plex, scan the libraries and empty the trash:
   ```
   curl "http://127.0.0.1:32400/library/sections/1/refresh"   (and /2/)
   curl -X PUT "http://127.0.0.1:32400/library/sections/1/emptyTrash"
   ```

---

## 6. Auto-start, updates, schedule

**6.1. Termux:Boot from GitHub** (`termux-boot-app_v0.8.1+github.debug.apk`, https://github.com/termux/termux-boot/releases):
```
adb install termux-boot-app_v0.8.1+github.debug.apk
adb shell "dumpsys deviceidle whitelist +com.termux.boot; am start -n com.termux.boot/.BootActivity"   ← open it once
```

**6.2. Scripts in Termux** (descriptions in [OPERATIONS.md, section 5](OPERATIONS.md#5-scripts)):

| On the phone | In this repository |
|---|---|
| `~/start-server.sh` | [`scripts/start-server.sh`](../scripts/start-server.sh) |
| `~/update-server.sh` | [`scripts/update-server.sh`](../scripts/update-server.sh) |
| `~/.termux/boot/10-start-server` | [`scripts/termux-boot/10-start-server`](../scripts/termux-boot/10-start-server) |
| `~/.bashrc` | one line: `~/start-server.sh termux-open` |

```
scp -P 8022 scripts/start-server.sh scripts/update-server.sh u0_a123@192.168.1.50:
scp -P 8022 scripts/termux-boot/10-start-server u0_a123@192.168.1.50:.termux/boot/
Termux:  sed -i 's/\r$//' ~/start-server.sh ~/update-server.sh ~/.termux/boot/10-start-server
Termux:  chmod +x ~/start-server.sh ~/update-server.sh ~/.termux/boot/10-start-server
Termux:  echo "~/start-server.sh termux-open" > ~/.bashrc
```
> Files copied from Windows may have CRLF line endings, so `sed -i 's/\r$//'` removes them.

**6.3. Cron** ([`scripts/crontab.txt`](../scripts/crontab.txt)):
```
Termux:  pkg install -y cronie
Termux:  crontab crontab.txt        (or crontab -e and paste the 3 lines)
```

---

## 7. realme settings (on screen; ADB cannot change these)

realme blocks `settings put secure/global …`, `pm grant …` and `appops set …` from ADB (`WRITE_SECURE_SETTINGS`, `MANAGE_APP_OPS_MODES`). These have to be tapped:

| Where | Termux | Termux:Boot | Server Status |
|---|---|---|---|
| Apps → … → Battery usage: foreground activity | On | On | On |
| … background activity | On | On | On |
| … auto launch | On | On | On |
| … launch other apps | On | – | – |
| Display over other apps | On | – | On |
| Permission "Run commands in Termux environment" | – | – | Allow |
| Recent apps → ⋮ on the card → **Lock** | yes | – | yes |

Screen: Settings → Display & brightness → Auto screen-off (15–30 s). During the day the Server Status app keeps the screen on.

---

## 8. Network

1. **Fixed MAC**: Settings → Wi-Fi → `MyWifi-5G` → Privacy → **"Use device MAC"** (example MAC `aa:bb:cc:dd:ee:ff`).
2. **DHCP reservation** on the router for that MAC → `192.168.1.50`.
3. **No port forwarding** on the router, UPnP off.

> **Signal matters:** with the 5 GHz signal at about -80 dBm, Android will **not** reconnect by itself after a reboot ("filtered out due to low signal strength"). Put the phone where the signal is better than about -75 dBm, or save a 2.4 GHz fallback network (`MyWifi-2G`, also with the device MAC), or use Ethernet through the hub.

---

## 9. Windows PC: drive M:

```
winget install -e --id WinFsp.WinFsp
winget install -e --id SSHFS-Win.SSHFS-Win
copy C:\Users\<you>\.ssh\id_ed25519 C:\Users\<you>\.ssh\id_rsa        (SSHFS-Win only looks for id_rsa)
net use M: "\\sshfs.kr\u0_a123@192.168.1.50!8022\storage\ABCD-1234\Media" /persistent:yes
```
Optional Explorer label: registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2\##sshfs.kr#u0_a123@192.168.1.50!8022#storage#ABCD-1234#Media`, value `_LabelFromReg`.
One-click repair: [`scripts/windows/fix-drive-M.cmd`](../scripts/windows/fix-drive-M.cmd). Set the variables at the top and copy it to your desktop.
> **Copy large files with `scp`, not through M:** ([LESSONS-LEARNED.md](LESSONS-LEARNED.md)).

---

## 10. Status dashboard

**10.1. Page server in Termux** ([`scripts/status-screen/`](../scripts/status-screen/)):
```
Termux:  pkg install -y python
Termux:  mkdir -p ~/status/www
scp -P 8022 scripts/status-screen/status-server.py scripts/status-screen/start-status.sh scripts/status-screen/check-app.sh u0_a123@192.168.1.50:status/
scp -P 8022 scripts/status-screen/www/* u0_a123@192.168.1.50:status/www/
Termux:  sed -i 's/\r$//' ~/status/*.sh ~/status/*.py && chmod +x ~/status/*.sh ~/status/*.py
Termux:  ~/status/start-status.sh && curl -s http://127.0.0.1:8099/status.json
```
Set `LANG`, `CITY`, `LAT`, `LON`, `TZ` (and optionally `DAY_FROM`/`DAY_TO`) at the top of `www/index.html`.

**10.2. The Server Status app**: build and install as described in [../status-app/README.md](../status-app/README.md):
```
bash status-app/build.sh
adb -s <phone> install -r status-app/server-status.apk
adb -s <phone> shell dumpsys deviceidle whitelist +pl.serwerplex.status
```
Then apply the settings from section 7 (column "Server Status") and open the app once. It asks for the Termux permission; tap Allow.

**10.3. Watchdogs**:
```
Termux:  echo "allow-external-apps = true" >> ~/.termux/termux.properties && termux-reload-settings
```
Also needed: the 3 cron lines from `scripts/crontab.txt`, and "Display over other apps" for Termux.

---

## 11. Final tests

| Test | How | Expected |
|---|---|---|
| Plex from the LAN | `curl http://192.168.1.50:32400/identity` | HTTP 200 |
| Status page | http://192.168.1.50:8099 | live data |
| Reboot | `adb reboot` (when nobody is watching) | after ~1.5 min SSH, Plex and the dashboard are back |
| Plex crash | `pkill -f "[P]lex Media Server"` | within 5 min `~/watchdog.log` shows `[cron] … Plex` |
| Termux killed | `adb shell am force-stop com.termux` | within 3–4 min `[status-app] …` and everything is back |
| Status app closed | `adb shell am force-stop pl.serwerplex.status` | reopened within 20 min (daytime) |

All of these passed on 2026-10-01 (results in [OPERATIONS.md, section 13](OPERATIONS.md#13-watchdogs-what-happens-when-something-stops)).
