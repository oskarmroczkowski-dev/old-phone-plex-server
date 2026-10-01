# ♻️ Zero-Cost Plex Server on an Old Android Phone

### No root · No new hardware · Built with Claude AI

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Platform: Android](https://img.shields.io/badge/platform-Android%2013-3DDC84?logo=android&logoColor=white)
![Root: not required](https://img.shields.io/badge/root-not%20required-blue)
![Hardware cost: €0](https://img.shields.io/badge/hardware%20cost-%E2%82%AC0-brightgreen)
![Built with Claude](https://img.shields.io/badge/built%20with-Claude%20AI-D97757)

An old phone from a drawer (realme GT Master Edition: Snapdragon 778G, 8 GB RAM) plus an old USB drive turned into a **24/7 Plex Media Server for the whole home**. It streams movies and TV shows to TVs, phones and laptops.
**Total hardware cost: €0.** We only used things we already had. The whole setup draws about **2–3 W**.
No root, no custom ROM, no unlocked bootloader. Android stays a normal Android, and the server runs inside the Termux app.

---

## Why

| | |
|---|---|
| 💸 **Zero cost** | Reuses a retired phone and a spare drive. No NAS, no mini-PC, no subscription. |
| ♻️ **Upcycling** | Gives e-waste a second life. A mid-range phone from a few years ago is a capable little ARM64 server. |
| 🔌 **Low power** | About 2–3 W for phone + SSD + hub, versus tens of watts for a PC or NAS. |
| 🤫 **Silent, tiny** | No fans, no disks spinning (with an SSD), fits on a shelf. |
| 🔋 **Built-in UPS** | The phone battery keeps the server alive through short power cuts. |
| 🔓 **No root** | Works on a stock, locked phone. Termux + Ubuntu in PRoot. |
| 🩺 **Self-healing** | Watchdogs restart whatever stops: Plex, SSH, the status page, even the whole Termux app. |
| 🔄 **Auto-updates** | Termux, Ubuntu and Plex update themselves every Sunday at 04:00. |

---

## Features

- **Plex Media Server** (official ARM64 `.deb`, updated from the official Plex apt repository) in Ubuntu 26.04 running in PRoot inside Termux.
- **Auto-start after reboot**: SSH, cron, the status page and Plex come back by themselves. Plex answered **76 s** after a reboot command.
- **Self-healing watchdogs that guard each other**: cron guards Plex/SSH/the status page every 5 min, the status app revives Termux when it is killed, and Termux reopens the status app when it is closed.
- **Weekly auto-updates** with an update lock so the watchdog does not fight the updater.
- **Full-screen status dashboard app** (native Android app, ~21 KB). It shows a clock, the date, the weather with a 3-hour forecast, Plex status and who is watching what (Direct Play / transcode, progress), free space on both drives, RAM, CPU temperature, battery and uptime. The screen stays on 06:00–23:00 and goes off at night. AMOLED burn-in protection: dark UI and a pixel shift every minute.
- The **same status page for every device on the LAN** (`http://<phone-ip>:8099`). The Plex token never leaves the phone.
- **LAN-only SSH**, key authentication only, passwords disabled.
- **Network drive on Windows** (SSHFS-Win) for browsing, and `scp` + SHA-256 for large files.
- **Direct Play** to TVs: the phone barely works while streaming.

---

## Architecture

```
┌──────────────────── Old Android phone (stock, no root) ────────────────────┐
│                                                                            │
│  Termux                                        "Server Status" app         │
│  ├─ sshd ............ :8022  ◄── SSH/SFTP       ├─ full-screen WebView       │
│  ├─ crond ........... watchdogs + updates       │   └─ http://127.0.0.1:8099 │
│  ├─ status-server.py  :8099  ◄── status page    ├─ 06:00/23:00 alarm         │
│  └─ proot-distro → Ubuntu 26.04                 ├─ starts on boot            │
│        └─ Plex Media Server :32400              └─ Termux watchdog           │
│              └─ /media/usb1 ── USB drive (exFAT) via USB-C hub (PD)        │
│                                                                            │
│  Termux:Boot ── runs start-server.sh after every reboot                    │
└────────────────────────────────────────────────────────────────────────────┘
          ▲ Wi-Fi (fixed MAC + DHCP reservation)
          │
   ┌──────┴──────┐   ┌──────────────┐   ┌───────────────────────────────┐
   │ TVs, phones │   │ Any browser  │   │ Windows PC: drive M: (SSHFS),  │
   │ (Plex app)  │   │ :8099 status │   │ scp, ADB (wireless debugging)  │
   └─────────────┘   └──────────────┘   └───────────────────────────────┘
```

More detail: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

---

## What you need

| Item | Notes |
|---|---|
| An old Android phone | Android 12+, ARM64. Tested on realme GT Master Edition (RMX3363, Android 13, realme UI 4.0, Snapdragon 778G, 8 GB RAM, 256 GB). |
| A USB drive | **exFAT** (this phone does not mount NTFS). An SSD is quieter and uses less power. |
| A USB-C hub with **PD pass-through** | So the phone charges while the drive is connected. |
| Wi-Fi | A decent signal matters (see [docs/LESSONS-LEARNED.md](docs/LESSONS-LEARNED.md)). Ethernet through the hub is even better. |
| A Windows PC (for setup) | `adb` (Android platform-tools), OpenSSH, Git Bash, Python 3. To build the status app: JDK 17 and Android SDK (build-tools 36, platform android-36). |
| A free Plex account | |

---

## Quick start

1. Follow **[docs/INSTALL-FROM-SCRATCH.md](docs/INSTALL-FROM-SCRATCH.md)**. It is step by step, with the exact commands used.
2. Set your values at the top of the scripts: `USB_ID` and `MEDIA_DIR` in `scripts/start-server.sh` and `scripts/status-screen/status-server.py`; `CITY`, `LAT`, `LON`, `TZ` and `LANG` in `scripts/status-screen/www/index.html`; your phone IP and user in `scripts/windows/fix-drive-M.cmd`.
3. Build and install the status app: [status-app/README.md](status-app/README.md).
4. Run the final tests (reboot, kill Plex, kill Termux) listed at the end of the install guide.

```
git clone https://github.com/oskarmroczkowski-dev/old-phone-plex-server.git
```

---

## Documentation

| Document | What's inside |
|---|---|
| [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) | Components, ports, the boot sequence second by second, data flows, watchdogs, updates |
| [docs/INSTALL-FROM-SCRATCH.md](docs/INSTALL-FROM-SCRATCH.md) | Full setup with real commands, from a stock phone to a tested server |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Day-to-day: paths, scripts, commands, Android settings, troubleshooting, security, network drive |
| [docs/LESSONS-LEARNED.md](docs/LESSONS-LEARNED.md) | Non-obvious problems we hit, how we diagnosed them and what fixed them |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Project timeline |
| [status-app/README.md](status-app/README.md) | The native "Server Status" app: classes, permissions, build without Gradle, install |

Repository layout:
```
scripts/
├── start-server.sh            starts whatever is not running + watchdog (cron every 5 min)
├── update-server.sh           weekly update (Sunday 04:00)
├── termux-boot/10-start-server   run by Termux:Boot after every reboot
├── crontab.txt                Termux cron table
├── ubuntu/start-plex.sh       starts Plex inside Ubuntu (no systemd in PRoot)
├── migrate-plex-paths.sql     example: rewrite Windows library paths after moving a Plex database
├── windows/fix-drive-M.cmd    one-click repair of the network drive on Windows
└── status-screen/             status-server.py, start-status.sh, check-app.sh, www/ (the dashboard page)
status-app/                    the native Android app (Java, built without Gradle)
lists/removed-apps-realme.txt  bloatware removed with `pm uninstall --user 0`
```

---

## Measured results

| What | Result |
|---|---|
| Plex reachable after a reboot command | **76 s** |
| Plex crashed (Termux alive) → restarted by cron | ≤ 5 min (test: answering again after 3 min 46 s) |
| Whole Termux force-stopped → revived by the status app | test: **2 min 44 s** (SSH, cron, status page and Plex back) |
| Status page server killed → revived by the status app | test: ~2 min |
| Status app force-stopped → reopened by Termux (daytime) | ≤ 20 min |
| PC → phone over Wi-Fi with SSH encryption (no disk write) | **95.5 MB/s** |
| Phone USB 2.0 port → USB drive (read) | ~27 MB/s (the real bottleneck) |
| Copying a film with `scp` | ~21 MB/s, verified with SHA-256 |
| Power | phone ~0.6–0.8 W into the battery (measured via ADB); whole setup estimated at 2–3 W |
| Idle load | CPU ~95% idle, CPU 31–43 °C, ~3.5 GB RAM available |

---

## 🤖 Built with Claude AI

This project was designed, debugged and documented together with **Claude** (Claude Code by Anthropic), which worked on the phone through ADB and SSH:

- **diagnosis from evidence**: Android `dumpsys`/`logcat`, Plex logs and Windows event logs. For example, it found why Wi-Fi did not reconnect after a reboot and why copies to the network drive froze;
- **watchdog design and failure testing**: killing Plex, force-stopping Termux and rebooting, which uncovered and fixed a stale-lock bug;
- **a native Android app**, written and built **without Gradle** (aapt2 + javac + d8 + apksigner), after the browser route turned out to be a dead end;
- **all of this documentation**.

The human set the goals, made the decisions and approved changes; the AI executed, explained its findings and tested the failure cases. The detailed story is in [docs/LESSONS-LEARNED.md](docs/LESSONS-LEARNED.md).

---

## Limitations

- **No hardware transcoding** without root. Software transcoding handles about one 1080p stream. Use **Direct Play** (original quality) on TVs.
- The phone's **USB-C port is USB 2.0**: ~27 MB/s to the drive. Enough for several streams, slow for bulk copying.
- **Wi-Fi signal matters**: with a weak signal (≈ -80 dBm on 5 GHz) Android will not auto-reconnect after a reboot. Place the phone well, or use Ethernet through the hub.
- **No-root constraints**: no systemd, Docker or firewall, and no ports below 1024 (so no SMB share; SSHFS instead).
- **The phone battery sits at 100 %** all the time. realme UI 4.0 has no permanent charge limit; consider a smart plug.
- If the battery ever fully drains, the phone must be switched on by hand. After that everything comes back automatically.

---

*Not affiliated with or endorsed by Plex Inc. "Plex" is a trademark of Plex Inc. Use only media you have the rights to.*

**License:** [MIT](LICENSE)
