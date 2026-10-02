# Lessons learned

The non-obvious problems we hit while building and testing the server. Each entry gives the **symptom**, the **root cause** with the evidence that proved it, and the **fix**.
Diagnosis was done together with Claude (Claude Code) using Android `dumpsys`/`logcat`, Plex logs, Windows event logs and targeted tests.

---

## 1. Copying large files to the SSHFS network drive froze Windows and silently corrupted a file

- **Symptom:** while copying several films (~1 GB+) through Explorer onto drive M: (SSHFS-Win), the transfer stalled, Explorer hung and finally all of Windows had to be powered off. Later, a file that "copied fine" had the correct size but contained **zeros from 200 MB to the end**.
- **Root cause:** the SSHFS-Win/WinFsp driver. Evidence: the phone side was idle and healthy (good Wi-Fi, drive mounted, no errors in Android logs). On the PC, `sshfs.exe` had accumulated **~18,500 handles** before the freeze, and the copy dialog was stuck in "Cancelling". Windows logged unexpected shutdowns (Kernel-Power 41) at exactly the moment the copy stopped. The behaviour matches open upstream reports for SSHFS-Win with large files. The corrupted file's size was right because Windows pre-allocates it before writing the data.
- **Fix:** use the network drive only for browsing and small files. Copy films with **`scp`** (no kernel driver, so a failure kills one copy, not the OS) and **verify with SHA-256**, because the file size proves nothing. Every file copied with `scp` matched its checksum.

## 2. Plex "scan on change" during a copy caused a load spike

- **Symptom:** enabling "Scan my library automatically" in the middle of a copy sent the phone's load from ~6–7 to ~17 and made the network drive unresponsive.
- **Root cause:** Plex saw the half-written file and rescanned. Its log showed **488 "Turbo analysis" runs and 372 ffmpeg processes** within a few minutes, all reading from the same USB drive the copy was writing to.
- **Fix:** don't let Plex see unfinished files. Any copy script writes `name.part` and renames only after the checksum matches. Avoid bulk copies while a full scan is running.

## 3. realme blocks many ADB settings

- **Symptom:** `settings put secure …`, `pm grant …` and `appops set …` from `adb shell` fail with `WRITE_SECURE_SETTINGS`, `GRANT_RUNTIME_PERMISSIONS` or `MANAGE_APP_OPS_MODES`, although they work on stock Android.
- **Root cause:** realme/ColorOS restrictions on the shell user.
- **Fix:** toggle these on screen (battery usage: foreground/background/auto launch, "Display over other apps", runtime permissions). Where possible we automated the taps with `uiautomator dump` + `input tap`, checking every label before tapping. The ADB commands that do work: `pm uninstall --user 0`, `device_config`, `dumpsys deviceidle whitelist`, `cmd appops` for background flags.

## 4. Android's "phantom process killer" kills Termux children

- **Symptom:** on Android 12+ long-running processes started from Termux (sshd, Plex in PRoot) can be killed without warning.
- **Root cause:** Android limits "phantom" child processes of apps (default 32).
- **Fix:** `device_config set_sync_disabled_for_tests persistent` + `device_config put activity_manager max_phantom_processes 2147483647` (+ `settings put global settings_enable_monitor_phantom_procs false`), plus a Doze exemption and `termux-wake-lock`.

## 5. `pgrep -x sshd` never finds a running sshd

- **Symptom:** the start script "restarted" sshd every time, and the log filled with `starting sshd` while SSH was obviously working.
- **Root cause:** OpenSSH re-executes itself with an absolute path, so the process name is truncated (`/data/data/com.`) and does not equal `sshd`. Evidence: `ps -A -o pid,comm,args` showed the comm field as the truncated path. The duplicate sshd failed to bind and exited, so it was harmless but noisy.
- **Fix:** `pgrep -f "^(/data/data/com.termux/files/usr/bin/)?sshd( |$)"`.

## 6. A browser "installed app" can't be truly full screen for a localhost page

- **Symptom:** "Install app" in Chrome 154 for `http://127.0.0.1:8099` created only a home-screen shortcut that opens a normal tab with the address bar. Launching it via its intent also landed in a tab.
- **Root cause:** Chrome creates real installed web apps (WebAPKs) through Google's servers, which can't reach a page on the phone's localhost. It falls back to a plain shortcut ("shortcuts open in Chrome"). In a normal tab `requestFullscreen()` needs a user tap every time.
- **Fix:** a small **native Android app** (WebView + immersive mode + keep-screen-on + boot receiver). It was built **without Gradle** (aapt2 → javac → d8 → zipalign → apksigner). Gotcha: compiling against `android.jar` with `javac -source 8` fails on lambdas (`LambdaMetafactory` missing), so the code uses anonymous classes.

## 7. realme delays "exact" alarms by up to an hour

- **Symptom:** an alarm set with `setExactAndAllowWhileIdle` for 23:00 appeared in `dumpsys alarm` with `window=+1h0m`.
- **Root cause:** the OEM alarm policy batches app alarms, even exact ones.
- **Fix:** `AlarmManager.setAlarmClock()`. Alarm-clock alarms showed `window=0` and are not batched. Side effect: an alarm icon in the status bar of other apps.

## 8. A stale lock blocked recovery after Termux was killed

- **Symptom:** in a failure test we force-stopped Termux. The status app correctly called `start-server.sh` through `RUN_COMMAND` after ~3 min, yet nothing came back. The next attempt was 10 min away, so the server would have been down for ~12 min.
- **Root cause:** `start-server.sh` used a time-based lock (`mkdir` lock kept for 3 min after starting Plex, to avoid a double start). Termux was killed one minute after cron had started Plex, so the lock was still "fresh" and the script exited immediately. Evidence: Android logs showed Termux starting `start-server.sh`, `coreutils` and `find`, and then nothing.
- **Fix:** the lock stores the owner's PID and is ignored if that process is dead. Double starts of Plex are prevented by checking the processes themselves (`Plex Media Server` or `/root/start-plex.sh`). The re-run test recovered everything in 2 min 44 s. **Lesson: test watchdogs by actually killing things.**

## 9. Wi-Fi does not reconnect after a reboot when the signal is weak

- **Symptom:** after a reboot the phone stayed offline until someone tapped the saved network.
- **Root cause:** Android's network selector rejects candidates below a signal threshold. `dumpsys wifi` showed, every ~15 s: `Networks filtered out due to low signal strength: MyWifi-5G … (5GHz) -79 … -83` and `No candidates`. A manual tap (`userSelectNetwork`) bypasses the threshold. The 2.4 GHz network of the same router was at -64 dBm but not saved.
- **Fix:** improve the signal (placement), save a 2.4 GHz fallback network (with the device MAC so the IP reservation still applies), or use Ethernet through the USB-C hub. Also: on boot, the dashboard fetched the weather before Wi-Fi was up and waited 20 min. Now it retries every minute and on the browser `online` event.

## 10. Wireless debugging turns off after every reboot

- **Symptom:** after a reboot `adb connect` stops working, and later the port is different.
- **Root cause:** Android's wireless debugging is disabled on reboot and uses a random port each time it is enabled.
- **Fix:** enable it again in Developer options. A PC that was paired once only needs the new port: `adb mdns services` → `adb connect <ip>:<port>`. If mDNS shows nothing, check whether the toggle is really on; scanning ports 30000–50000 confirms it.

## 11. The bottleneck is the phone's USB 2.0 port, not Wi-Fi or SSH encryption

- **Symptom:** copying to the server topped out around 18–24 MB/s, even though the drive is a USB 3 SSD.
- **Root cause:** measured separately: PC → phone over Wi-Fi with SSH encryption and no disk write **95.5 MB/s**, CPU nearly idle (Snapdragon 778G has AES acceleration); reading from the drive on the phone **~27 MB/s**. The phone's USB-C port is **USB 2.0**.
- **Fix:** nothing to tune, since encryption costs nothing here. For many films, staging on the faster internal storage frees the PC sooner (total time is still bound by USB 2.0).

## 12. The phone battery sits at 100 % all the time

- **Symptom:** `dumpsys battery` showed 100 %, 4.43 V, a small top-up current (~130–180 mA) and 27–30 °C.
- **Root cause:** realme UI 4.0 only has *adaptive* options ("Optimized night charging" and "Smart charging"). They pause at 80 % and finish before the predicted unplug time, but there is no permanent 80 % limit. A server is never unplugged.
- **Fix (idea):** a smart plug driven by a script (on at ~40 %, off at ~80 %). Check first whether the drive starts drawing from the phone through the hub when the charger is off.

## 13. realme "RAM expansion" depends on free storage

- **Observation:** swap is ~7.5 GB = zram (~3.5 GB) + "RAM expansion" (nandswap, a 4 GB file on internal storage). The property `persist.sys.oplus.nandswap.storage.min=15` suggests realme disables the expansion when free storage drops below a threshold (unit not confirmed: GB or %).
- **Consequence:** don't fill the internal storage, e.g. with staged films. The dashboard turns phone storage yellow below 60 GB and red below 40 GB.
- RAM itself was never the problem: 3.5–4 GB available at all times. An early "out of RAM" guess came from misreading `free`, and `MemAvailable` is the number to trust.

## 14. Persistent network drive mappings may not persist when created by automation

- **Symptom:** after a normal Windows restart drive M: was gone, although it had been mapped with `net use … /persistent:yes`.
- **Root cause (likely, not confirmed):** the mapping had been created from a restricted automation shell, and Windows never wrote `HKCU\Network\M`.
- **Fix:** a one-click `fix-drive-M.cmd` run from the user's own session. It does nothing if M: already works, so it never interrupts a copy.

## 15. 4K plays at 40 Mb/s but not at 100 Mb/s: the TV decides, not the server

- **Symptom:** a 4K HEVC 10-bit test clip at 40 Mb/s played instantly; the same clip at 100 and 150 Mb/s buffered forever.
- **Evidence:** `/status/sessions` showed Direct Play for 40 Mb/s and a video transcode at 0.1–0.4× for the others. The Plex log showed the request arriving with `directPlay=0` (`MDE: … Direct Play is disabled`). The TV's Plex app had sent a profile limiting HEVC to **80 Mb/s** and excluding **Dolby Vision profile 5**.
- **Root cause:** the client caps what it will Direct Play. Above the cap it asks for a transcode, and a phone cannot transcode 4K in software.
- **Fix:** keep 4K files within the TV's limits (bitrate, HDR10 rather than DV profile 5, text subtitles rather than PGS). Throughput from the phone (~200 Mb/s) was never the bottleneck. See [PERFORMANCE.md](PERFORMANCE.md).

## 16. "This phone doesn't support NTFS" was never tested

- **Symptom:** early notes said the phone could not mount NTFS, so drives "must be exFAT".
- **Evidence:** the drive in use is exFAT from the factory (`dumpsys mount` → `fsType=exfat`, label `PortableSSD`), and it was never reformatted. The system ships `ntfs-3g`, `mkntfs` and `ntfsfix`, and `/proc/filesystems` lists `fuseblk`.
- **Fix:** documentation corrected: exFAT is recommended (native driver, faster), and NTFS probably works through ntfs-3g but is untested. Lesson: write down what was measured and mark guesses as guesses. **Update 2026-10-02:** a second drive formatted NTFS mounts through ntfs-3g and plays to a TV by Direct Play without problems.

## 17. Benchmarking from inside Termux hides the real CPU load

- **Symptom:** a transcoding benchmark reported 0 % CPU while the transcoder was clearly busy.
- **Root cause:** on Android 13, Termux (an ordinary app) cannot see other processes' CPU time in `/proc/stat`/`top`. Driving Plex's HLS API from a script was also unreliable: segment timing depends on seeking and throttling, and later sessions returned 404.
- **Fix:** run the `Plex Transcoder` command from the Plex log directly, time it, and read `/proc/stat` through ADB (`adb shell head -1 /proc/stat`). Temperatures from `/sys/class/thermal` are readable from Termux.

## 18. realme's MediaPlayer never finishes preparing an Icecast radio stream

- **Symptom:** the app's radio worked for HLS stations, but every Icecast MP3/AAC stream stayed in "connecting" forever.
- **Root cause:** realme's media player (OplusNuPlayer) waits for the end of the file before it reports "prepared". An endless Icecast stream reports `getSize=-1` and never gets there. HLS (a playlist of short segments) plays at once.
- **Fix:** two engines in the app. HLS goes to Android's `MediaPlayer`; everything else plays in a hidden WebView `<audio>` element (Chromium), which handles Icecast fine.

## 19. Chromium refuses AAC+ sent as `audio/aacp`

- **Symptom:** a few stations failed in the WebView engine only, although `curl` received audio data.
- **Root cause:** the server sends the MIME type `audio/aacp`, which Chromium does not accept, even though the data itself is ordinary AAC+.
- **Fix:** `/radio-proxy/<id>` in `status-server.py` relays the station's `upstream` stream and labels it `audio/aac`.

## 20. A UK radio "geoblock" was really a missing timestamp

- **Symptom:** every Bauer/Rayo stream (Magic, Mellow Magic, Absolute, KISS, Greatest Hits…) returned **HTTP 500** from outside the UK, for MP3, AAC and the HLS variant playlist alike, while a non-existent stream name returned 404. It looked exactly like a geoblock. Yet the station's own web player played fine in a browser on the same PC.
- **Root cause:** the web player's `modifying-urls.js` appends `aw_0_1st.skey=<current Unix time>` (plus listener and player IDs) to every stream address. Without a recent `skey` the server answers 500: a fixed value, one from a month ago or one from the future all fail; an hour-old one still works.
- **Fix:** the proxy fills in `{now}` = the current time on every connection. Because the stream names can change too, the proxy also reads the current addresses from the Rayo API once a day. Lesson: before concluding "geoblocked", compare with the official player's real request.

## 21. iHeart stream addresses expire

- **Symptom:** popular US stations found in directories (iHeart: e.g. Z100, KROQ) played for a while, then stopped.
- **Root cause:** their addresses carry a short-lived token (`rj-tok`, `rj-ttl`).
- **Fix:** skipped them; picked stations with fixed addresses (181.FM, Radio Paradise, KEXP, WSM and others) and added Radio Browser `uuid`s where possible, so the app can look up a new address when an old one dies.

## 22. Losing the internet for a minute killed the radio for good

- **Symptom:** after a short router or ISP outage the radio showed "⚠ error" and stayed silent until someone pressed play again.
- **Root cause:** the player gave up after 6 retries 5 s apart (~30 s).
- **Fix (app 1.3.3):** after the quick retries the app checks whether there is internet at all. Without it, it waits for Android's network callback (plus a check every minute) and resumes by itself; with internet but a silent station it retries with growing pauses for ~30 min, re-reading the station's addresses each time. Tested in the emulator by switching Wi-Fi and data off: playing again 6 s after the network came back.

## 23. A script saved on Windows failed with "bad interpreter"

- **Symptom:** `check-stations.py` would not run in Termux: `/data/data/com.termux/files/usr/bin/python^M: bad interpreter`.
- **Root cause:** the file had Windows line endings (CRLF), so the shebang line ended in an invisible carriage return. Files written by Python in text mode on Windows get CRLF too.
- **Fix:** keep every file for the phone in LF (`newline='\n'` when writing from Python; `sed -i 's/\r$//' file` on the phone).

## 24. `pkill -f status-server.py` killed its own SSH session

- **Symptom:** a one-line SSH command "restart the server, then check it" stopped halfway, and the server stayed down for a minute.
- **Root cause:** `pkill -f` matches the full command line of every process, including the remote shell running that very SSH command, whose text contained `status-server.py`.
- **Fix:** a pattern that cannot match itself: `pkill -f "python.*status-serve[r][.]py"`.

## 25. The emulator showed clipped text that the phone never had

- **Symptom:** previewing the dashboard in the Android emulator showed texts cut off and overflowing, which looked like layout bugs.
- **Root cause:** the emulator's system font scale was 1.25 while the phone uses 1.0; the WebView scales every font with it.
- **Fix:** set the emulator up like the phone: `settings put system font_scale 1.0`, `wm size 1080x2400`, `wm density 480`. Compare with a real phone screenshot before "fixing" a layout.

## 26. The Moon's orbit line ran under the cards

- **Symptom:** a thin ellipse around the spinning Earth crossed the translucent weather and radio cards and seemed to end abruptly at their edges.
- **Root cause:** on the phone the orbit is ~200 px wide while the free gap between the two cards is ~140 px; the Earth canvas lies under the cards.
- **Fix:** the orbit line is hidden (`GLOBE.orbitLine: false`); the Moon keeps orbiting on the invisible path and simply passes behind the cards at the far ends.

## 27. "Direct Play" on the server, black screen on the TV

- **Symptom:** a 4K HDR10 clip at 80 Mb/s showed a black screen with a moving progress bar on a 2021 Samsung TV.
- **Evidence:** the server reported Direct Play (78.8 Mb/s) and sent the file; the TV's Plex profile declared HEVC up to 80 Mb/s. The same clip at 70 Mb/s played fine.
- **Root cause:** the TV's decoder limit in practice is below the cap its app declares (the clip peaks above its 78.8 Mb/s average).
- **Fix:** none on the server. Keep 4K HDR10 files at or below ~70 Mb/s for this TV, and always confirm results on the screen, not only in the server's session list.

## 28. A 4K TV that never asks for the 4K file

- **Symptom:** a realme Android TV with a 4K panel spun forever on every 4K HEVC 10-bit clip (HDR10 and SDR, 40–70 Mb/s), while normal films played.
- **Evidence:** the Plex log showed the TV fetching the item details and reporting a 3840×2160 screen, but no playback decision and no file request at all.
- **Root cause:** the TV's player rejects 4K HEVC 10-bit on its own side before contacting the server; nothing the server or phone could change.
- **Fix:** give that TV lower-resolution (e.g. 1080p) versions. When a client "hangs" before playback, check whether it requested anything at all before blaming the server.
