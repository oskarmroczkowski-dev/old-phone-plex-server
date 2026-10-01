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
