# Changelog

Project timeline. Details of each problem: [LESSONS-LEARNED.md](LESSONS-LEARNED.md).

## 2026-10-01: Status dashboard, watchdogs, failure tests, documentation

- **Power check via ADB:** battery 100 %, ~130–180 mA into the battery (~0.6–0.8 W), 27–28 °C. Whole setup estimated at 2–3 W. Looked at realme charge-protection options: only adaptive ones, no permanent limit.
- **Swap/RAM check:** 7.5 GB swap (zram + realme "RAM expansion"), 3.5–4 GB RAM available; RAM is not a bottleneck.
- **Network drive:** remapped; added the one-click `fix-drive-M.cmd`.
- **Status dashboard:**
  - `status-server.py` in Termux (port 8099, live `/status.json`, Plex token stays on the phone), started with the server and kept alive by cron;
  - the page: clock, date, weather (Open-Meteo), Plex now playing, both drives, RAM, CPU, battery, uptime; dark UI with a pixel shift every minute; black at night;
  - a browser "installed app" was tried and dropped (Chrome can't make a real web app for a localhost page);
  - **Server Status app 1.0**: native WebView app, immersive full screen, screen on 06:00–23:00, starts on boot, built without Gradle;
  - **1.1**: alarm-clock-type alarm (`setAlarmClock`), because realme delayed exact alarms by up to 1 h;
  - **1.2**: Termux watchdog (heartbeat `/ping?app=1`, revives Termux through `RUN_COMMAND`).
- **Watchdogs:** `start-server.sh` run by cron every 5 min, with an update lock and `~/watchdog.log`; `check-app.sh` reopens the app; recent-apps locks on Termux and the app; fixed sshd detection (`pgrep -x sshd` never matched).
- **Failure tests** (when nobody was watching): Plex crash (back in 3 min 46 s), status page server killed (revived by the app in ~2 min), Termux force-stopped (first attempt exposed a stale-lock bug, which was fixed; the re-test recovered in 2 min 44 s), app force-stopped (reopened), phone reboot (Plex up after 76 s). All passed.
- **Wi-Fi finding:** after the reboot the phone did not rejoin Wi-Fi by itself, because a weak 5 GHz signal (~-80 dBm) was filtered out by Android's auto-join.
- **Dashboard fix:** weather retries every minute after a failure and as soon as the network returns.
- **Documentation:** how it works, install from scratch, operations, app docs.
- **Public release** on GitHub (this repository) and the prebuilt app v1.2 in Releases.
- **Performance tests** ([PERFORMANCE.md](PERFORMANCE.md)): software transcoding up to three 1080p → 720p streams at once; 4K transcoding impossible (0.1–0.4×); 4K HEVC 10-bit Direct Play at 40 Mb/s smooth on a 2021 Samsung TV, whose Plex app caps HEVC at 80 Mb/s; USB drive → Wi-Fi 25 MB/s (~200 Mb/s).
- **Correction:** the media drive is exFAT from the factory, and NTFS is probably supported too (`ntfs-3g` is in the system). The earlier "no NTFS" note had never been tested.
- **Dashboard:** new landscape layout (clock and weather left; Plex, disks and phone right; sized by screen height; clears the camera cutout).

## 2026-09-29 → 2026-09-30: Copying large files

- Diagnosed Windows freezes while copying large files to the SSHFS-Win drive. The driver hung, the phone was healthy, and one file was silently corrupted.
- Switched large copies to `scp` with SHA-256 verification, and re-copied and verified the affected file.
- Measured the transfer chain: Wi-Fi + SSH 95.5 MB/s, phone USB 2.0 → drive ~27 MB/s, `scp` end-to-end ~21 MB/s.

## 2026-09-29: Installation

- Removed 50 preinstalled apps (`pm uninstall --user 0`); disabled the phantom process killer and animations.
- Termux (GitHub build) + OpenSSH with key-only login; proot-distro Ubuntu 26.04; Plex Media Server (ARM64 `.deb`, later the official apt repository).
- Moved the existing Plex library from a Windows PC (database, metadata, thumbnails) and rewrote the media paths with Plex SQLite.
- USB drive bound into Ubuntu; files renamed to Plex's naming scheme.
- Fixed device MAC + DHCP reservation; Termux:Boot auto-start; weekly auto-updates with cron; first reboot test (~1.5 min to a working Plex).
- Windows network drive via SSHFS-Win; SSH restricted to the LAN with password login disabled.
