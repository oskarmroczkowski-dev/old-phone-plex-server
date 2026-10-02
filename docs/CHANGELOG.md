# Changelog

Project timeline. Details of each problem: [LESSONS-LEARNED.md](LESSONS-LEARNED.md).

## 2026-10-02: Radio panel, 70 more stations, radio failsafes, second drive

- **4K HDR10 test** ([PERFORMANCE.md](PERFORMANCE.md)): a 2021 Samsung TV plays 4K HEVC HDR10 up to **70 Mb/s** (80 Mb/s: black screen despite Direct Play; 90 Mb/s: the TV asks for a transcode, which the phone cannot do). A realme Android TV with a 4K panel does not start 4K HEVC 10-bit at all (HDR10 or SDR); ordinary films play.
- **Second USB drive** (NTFS via `ntfs-3g`) as `/media/usb2` in Ubuntu, holding a separate kids library: Plex's age ratings for managed users need Plex Pass, so a library the kids profile alone can see is the free workaround. `start-server.sh` binds it when it is mounted (`KIDS_USB_ID`).
- **Dashboard:**
  - drives shown as **rings** (arc and percent of free space), free GB next to them, a short label below (PHONE, MOVIES, KIDS), separate icons; any extra USB drive is picked up automatically;
  - radio card: **round "physical" copper buttons** (they press in when touched), sleep-timer badge;
  - the **Radio panel** rebuilt: a fixed "Now playing" column (big station logo with a glow in the logo's colour, round − ▶/■ + buttons sized for an adult finger, 10-step volume bar, sleep timer) and **one scrollable list of all stations** with sticky group tabs (tap a tab to jump, scrolling highlights the current group); animated equaliser and a pulsing ring while playing;
  - the **Moon's orbit line is hidden**: the orbit is ~200 px wide but the gap between the weather and radio cards is ~140 px, so the line ran under the translucent cards. The Moon keeps orbiting.
- **70 more stations**, 90 in total: **UK** (Bauer/Rayo: Magic, Mellow Magic, Magic Soul, Absolute + decades, Greatest Hits + decades, Hits Radio, KISS, Jazz FM, Planet Rock, Kerrang!; Global: Smooth, Heart, Capital, Classic FM, Gold, Radio X, LBC; BBC Radio 2 and World Service) and **USA** (pop, rock, country: 181.FM, Radio Paradise, KEXP, WSM 650 Nashville and more). All verified to stream from outside the UK/US.
- **Server Status app 1.3.3, radio failsafes:**
  - **A**: after 6 quick retries with no internet, the radio waits for the network (system callback + a check every minute) and resumes by itself; with internet but a dead station it retries every 30 s…5 min for ~30 min, re-reading the station's addresses each time;
  - **B**: the current address from Radio Browser through three mirrors (de1, nl1, at1);
  - **C**: backup addresses per station (`alt` in `radio.json`);
  - **D**: the status server fetches current Bauer/Rayo stream addresses from their API once a day (`rayo` field) and fills in the required timestamp (`{now}`);
  - **E**: `check-stations.py` tests every station at 04:30; dead ones are greyed out in the Radio panel, stations playing from a backup get a dot.
  - Test in the emulator: network cut while playing → "no internet, waiting for the network" → playing again 6 s after the network came back. On the phone: all stations playing.
- **Tools** for the PC: `tools/dev-server.py` (preview the page in the Android emulator with live data), `make_earth.py`, `stations-uk.py`, `stations-usa.py`, `cpu_once.py`.

## 2026-10-01 (evening): New look, spinning Earth, internet radio

- **Server Status app 1.3 → 1.3.2: internet radio.** A player in the app (`RadioPlayer`) and a small HTTP control server on port 8098 (`ControlServer`), so the page and any device on the LAN can start/stop, change volume and set a sleep timer. HLS goes to Android's MediaPlayer; Icecast MP3/AAC goes to a hidden WebView `<audio>` because realme's MediaPlayer never finishes preparing endless streams. Stops at 23:00 and when a Bluetooth speaker disconnects.
- **Radio on the page:** a radio card (play/stop, volume, sleep timer, the 3 most-played stations) and a panel with all stations; 20 stations in `radio.json`; `/radio-proxy/<id>` in `status-server.py` relays AAC+ streams that Chromium rejects as `audio/aacp`.
- **New look:** black background, smoky grey cards, a copper weather card in a gold frame, copper icons; weather with pressure and its trend; fixed Plex user lines; CPU load (from per-core idle times, because Termux cannot read `/proc/stat`); every extra USB drive detected automatically.
- **Background animation:** a spinning holographic Earth (Natural Earth 1:50m outlines, shaded land, grid, Moon), twinkling stars and the current zodiac constellation next to the clock. Whole-phone CPU: ~21 % with the first version, 15–21 % after optimising (own timer instead of 120 Hz `requestAnimationFrame`, 8 fps, static layers drawn once); 6–9 % without the animation.

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
