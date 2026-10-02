# "Server Status" app (pl.serwerplex.status)

A small **native Android app** (Java, no external libraries, no Gradle) that runs on the server phone and:
- shows the status page `http://127.0.0.1:8099/` **full screen** (WebView, no status bar or navigation buttons),
- keeps the screen **on 06:00–23:00**, lets it turn off at night and **turns it back on at 06:00**,
- **starts by itself after a reboot**,
- **guards Termux**: if the status page does not answer for 3 minutes, it asks Termux to run `~/start-server.sh`,
- gives the page **battery** data (level, charging, temperature),
- plays **internet radio** controlled from the status page, also from other devices at home (HTTP control on port 8098), with a **failsafe** for lost internet and changed station addresses.

Version **1.3.3** (versionCode 7). APK size ~29 KB. Android 11+ (minSdk 30), targetSdk 33.

It is not a Bubblewrap/TWA wrapper and does not use Chrome or Google's servers. The content (HTML) is rendered by the system WebView, while full screen, screen control, alarms, start-up and the watchdog are native code.

Related: [../docs/HOW-IT-WORKS.md](../docs/HOW-IT-WORKS.md) (the whole system), [../docs/OPERATIONS.md](../docs/OPERATIONS.md) (sections 12–13). The page and its server: [`../scripts/status-screen/`](../scripts/status-screen/).

---

## 1. Files

```
status-app/
├── AndroidManifest.xml        permissions, components, full-screen theme
├── build.sh                   builds and signs the APK (Git Bash)
├── res/mipmap-xxxhdpi/ic_launcher.png   icon (amber "play" on black)
├── src/pl/serwerplex/status/
│   ├── MainActivity.java      screen: WebView, full screen, screen on 06–23, reload retries
│   ├── Schedule.java          06:00/23:00 logic, system alarm, bringing the screen to front
│   ├── AlarmReceiver.java     alarm: at 06:00 turns the screen on and shows the dashboard; sets the next alarm
│   ├── BootReceiver.java      after boot / app update: alarm + dashboard
│   ├── Bridge.java            window.StatusApp.battery() for the page
│   ├── Watchdog.java          Termux watchdog (/ping?app=1 every minute, RUN_COMMAND)
│   ├── RadioPlayer.java       radio: HLS → native MediaPlayer, other streams → hidden WebView with <audio>;
│   │                          sleep timer, 23:00 stop, Bluetooth disconnect stop; failsafe (backup addresses,
│   │                          waiting for the network, slow retries)
│   └── ControlServer.java     HTTP server on :8098 (whole home network) to control the radio, with a CORS header
├── keystore/                  created by build.sh: status.jks + password.txt (gitignored, KEEP IT SAFE)
└── server-status.apk          build output (gitignored)
```

---

## 2. How it works (class by class)

### MainActivity
- **`onCreate`**: the window also uses the display cutout (`LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES`), has a black background and creates the WebView. It sets the alarm (`Schedule.scheduleNext`), starts the `Watchdog` and the radio `ControlServer`, and asks for `com.termux.permission.RUN_COMMAND` (a one-time "Allow" dialog).
- **WebView**: JavaScript and `localStorage` on, zoom off, long press does nothing (no context menu), no scrollbars. `Bridge` is exposed to JS as `window.StatusApp`.
- **Load error** (`onReceivedError` / `onReceivedHttpError` for the main frame): shows a black page and retries every **10 s**. This happens right after a reboot, before `status-server.py` is up.
- **Renderer crash** (`onRenderProcessGone`): the WebView is recreated and the app keeps running.
- **Full screen**: `WindowInsetsController.hide(statusBars | navigationBars)` with `BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE` (bars appear briefly after a swipe from the edge). It is applied in `onResume`, `onNewIntent` and `onWindowFocusChanged`, so **full screen comes back by itself when you return to the app**.
- **Day/night**: `applyDayNight()` every minute. Between 06:00 and 23:00 `FLAG_KEEP_SCREEN_ON` is set; at night it is cleared and the screen turns off after the system timeout.
- **Back** does nothing (`onBackPressed` is empty). Leave with the Home button.
- Manifest: `launchMode="singleTask"` (always one instance), `showWhenLocked`, `turnScreenOn`, `configChanges` (rotation does not reload the page).

### Schedule
- `isDay()`: 6 ≤ hour < 23 (phone time zone).
- `scheduleNext()`: an alarm for the next 06:00 or 23:00. It uses **`setAlarmClock`**, because realme gave a normal exact alarm a 1-hour window (visible in `dumpsys alarm`) but does not delay alarm clocks. Side effect: an alarm icon appears in other apps' status bar.
- `openStatus()`: `startActivity` with `FLAG_ACTIVITY_NEW_TASK | REORDER_TO_FRONT`. From the background this works only with the **"Display over other apps"** permission.

### AlarmReceiver
- Always schedules the next alarm.
- At 06:00 it takes a 15 s `SCREEN_BRIGHT_WAKE_LOCK | ACQUIRE_CAUSES_WAKEUP` (turns the screen on) and brings the dashboard to the front. At 23:00 it stops the radio if it is playing; the screen turns off by itself once `FLAG_KEEP_SCREEN_ON` is cleared.

### BootReceiver
- Handles `BOOT_COMPLETED` (phone start) and `MY_PACKAGE_REPLACED` (app update): sets the alarm and opens the dashboard.
- realme delivers `BOOT_COMPLETED` only to apps with **auto launch** enabled.

### Bridge (`window.StatusApp`)
- `battery()` returns JSON like `{"level":100,"charging":true,"temp":29}` from `ACTION_BATTERY_CHANGED`. The page uses it instead of `navigator.getBattery()`.
- When `window.StatusApp` exists, the page knows it runs inside the app: it shows no "tap for full screen" hint and does not use the Wake Lock API.

### Watchdog
- Runs on its own thread (`HandlerThread`) and calls `GET http://127.0.0.1:8099/ping?app=1` every **60 s** (5 s timeout).
- Each successful call is also the **app's heartbeat**: the server touches `~/status/app-heartbeat`, and `check-app.sh` (cron) reopens the app if, during the day, there has been no heartbeat for 15 min.
- **3 failures in a row** (Termux closed or force-stopped) → an intent `com.termux.RUN_COMMAND` to `com.termux.app.RunCommandService`:
  ```
  RUN_COMMAND_PATH       = /data/data/com.termux/files/home/start-server.sh
  RUN_COMMAND_ARGUMENTS  = ["status-app"]
  RUN_COMMAND_BACKGROUND = true
  ```
  It is sent with `startForegroundService`, at most once every **10 min**. Log entry in `~/watchdog.log`: `[status-app] …`; logcat tag `StatusWatchdog`.
- Requires `allow-external-apps = true` in `~/.termux/termux.properties`, the runtime permission `com.termux.permission.RUN_COMMAND`, and `<queries><package android:name="com.termux"/></queries>` in the manifest (package visibility on Android 11+).

### ControlServer (port 8098)
- A plain `ServerSocket` on all interfaces (home network, no password, like the status page). Each request runs on its own thread.
- `GET /radio/state`, `/radio/play?id=<station id>`, `/radio/stop`, `/radio/volume?v=0..100`, `/radio/sleep?min=0..` (0 = no sleep timer). Every answer is the radio state as JSON: `state` (`stopped` / `connecting` / `playing` / `error`), `id`, `name`, `info` (what the failsafe is doing), `sleepUntil`, `volume`, `output` (`speaker` / `wired` / `bt:<name>`).
- `Access-Control-Allow-Origin: *`, so the page on port 8099 (on the phone or any other device) can call it.

### RadioPlayer
- Station list: `http://127.0.0.1:8099/radio.json`, re-read on every start; a copy is kept in the app's storage for when the page server is down.
- **Two engines**: HLS (`.m3u8`) plays in the native `MediaPlayer`; plain Icecast MP3/AAC plays in a hidden WebView with `<audio>`, because realme's native player never finishes preparing endless streams. Chromium does not accept `audio/aacp`, so such stations go through the page server's `/radio-proxy/<id>` (see the radio section of the docs).
- Wi-Fi lock and partial wake lock while playing, so it keeps playing with the screen off.
- Stops on: the sleep timer, 23:00 (`AlarmReceiver`), a Bluetooth speaker disconnecting (`ACTION_AUDIO_BECOMING_NOISY`), another app taking the audio. Started at night, it sets a 1 h sleep timer by itself.
- **Failsafe** (1.3.3):

| Situation | What happens |
|---|---|
| Stream broke, error, buffering > 20 s | reconnect every 5 s, 6 attempts; each attempt takes the next address: `url` → `alt` (backup list in `radio.json`) → the current address from Radio Browser by `uuid` (servers `de1`, `nl1`, `at1` in turn) |
| After 6 attempts, **no internet** | `info` = "no internet, waiting for network": waits with no limit (`ConnectivityManager.NetworkCallback` + a check every minute) and resumes by itself a few seconds after the network returns. Ends with Stop, the sleep timer or 23:00 |
| After 6 attempts, internet works but the **station does not answer** | "station not responding, retrying in …": attempts after 30 s, 1, 2 and 5 × 5 min (about 30 min), each time with freshly read addresses; then `error` |

  Tested in the emulator: network cut while playing → "no internet, waiting for network" → playing again 6 s after the network returned.

---

## 3. Permissions and settings (and why)

| Permission / setting | Why | How it is granted |
|---|---|---|
| `INTERNET` | WebView (page and weather), Watchdog, radio | automatic |
| `ACCESS_NETWORK_STATE` (1.3.3) | radio: is there internet, and a signal when the network returns | automatic |
| `usesCleartextTraffic="true"` | the page is plain `http://` on localhost | manifest |
| `WAKE_LOCK` | turning the screen on at 06:00 | automatic |
| `RECEIVE_BOOT_COMPLETED` | start after reboot | automatic |
| `USE_EXACT_ALARM` (Android 13) / `SCHEDULE_EXACT_ALARM` (≤ 12) | exact 06:00/23:00 alarm | automatic on Android 13 |
| `SYSTEM_ALERT_WINDOW` "Display over other apps" | coming to the front from the background (boot, 06:00) and starting Termux's service from the background | **on screen in Settings** (realme blocks `appops` via ADB) |
| `com.termux.permission.RUN_COMMAND` | Termux watchdog | dialog on first start → **Allow** |
| realme: foreground / background activity / auto launch | so realme neither freezes the app nor withholds `BOOT_COMPLETED` | **on screen**: Apps → Server Status → Battery usage |
| Doze: `dumpsys deviceidle whitelist +pl.serwerplex.status` | alarms and network with the screen off | ADB |
| Lock in recent apps | "Close all" won't close it | on screen: ≡ → ⋮ → Lock |

---

## 4. Build (no Gradle)

Requirements on the PC: Git Bash, **JDK 17** (`javac`, `java`, `keytool` on PATH), Python 3, and the Android SDK (default `%LOCALAPPDATA%\Android\Sdk`, override with `ANDROID_SDK`) with **build-tools 36.0.0** and **platforms/android-36**.

```
bash status-app/build.sh
```
What `build.sh` does:
1. `aapt2 compile` + `aapt2 link`: resources + manifest → `build/base.apk` (minSdk 30, targetSdk 33, version from `VERSION_CODE`/`VERSION_NAME`).
2. `javac -source 8 -target 8 -bootclasspath android.jar`. **No lambdas**: `android.jar` lacks `LambdaMetafactory` and javac fails, so the code uses anonymous classes.
3. `d8` (from `build-tools/lib/d8.jar`): bytecode → `classes.dex`.
4. Python adds `classes.dex` to the APK, then `zipalign -p 4`.
5. Signing key: if `keystore/status.jks` does not exist, `keytool` creates one (RSA 2048, valid 100 years) with a random password in `keystore/password.txt`.
6. `apksigner sign` (one password for store and key, so only `--ks-pass` is passed) + `apksigner verify`.

Output: `status-app/server-status.apk`.

> **Bump `VERSION_CODE`** (and `VERSION_NAME`) in `build.sh` whenever you change the code; otherwise Android refuses the update.
> **Never lose or publish `keystore/`.** Updates must be signed with the same key. Without it you would have to uninstall the app (losing its permissions and the settings from section 3) and install it again.

---

## 5. Install and update

**Ready-made APK:** download `server-status-1.3.3.apk` from [Releases](https://github.com/oskarmroczkowski-dev/old-phone-plex-server/releases/latest) (signed with this project's release key; check the SHA-256 listed there). Or build your own (section 4); an APK you sign with your own key cannot be installed over the release one, and vice versa, so uninstall first when switching.

```
adb mdns services                                      ← wireless debugging port
adb connect 192.168.1.50:<port>
adb -s 192.168.1.50:<port> install -r status-app/server-status.apk
```
- After an update (`install -r`) the app **comes back to the screen by itself** (`MY_PACKAGE_REPLACED` → `BootReceiver`). Permissions and settings are kept.
- First install on a new phone: also `adb shell dumpsys deviceidle whitelist +pl.serwerplex.status` and the settings from section 3, then open the app once.
- Uninstall: first remove the `check-app.sh` line from Termux's crontab (otherwise Termux keeps reopening the app), then `adb uninstall pl.serwerplex.status`.

---

## 6. The page shown by the app

The page is **not** bundled in the APK. It lives on the phone in `~/status/www/` (source: [`../scripts/status-screen/www/`](../scripts/status-screen/www/)) and is served by `status-server.py`. As a result:
- **you can change the look without rebuilding the app**: edit `index.html` → `scp` it to the phone → reload (force-stop and reopen the app, or wait for the daily 05:55 reload),
- the same page is available to other devices on the LAN: `http://192.168.1.50:8099`.

Configuration at the top of `index.html`: `LANG` (`'en'`/`'pl'`), `CITY`, `LAT`, `LON`, `TZ`, `DAY_FROM`, `DAY_TO`.
Behaviour: `/status.json` every minute, weather every 20 min (every minute after a failure), black 23:00–06:00, content shifted ±8 px every minute, reload at 05:55. A service worker (`sw.js`) keeps a copy of the page in case the server is not up yet.

---

## 7. Diagnostics

| Command | Shows |
|---|---|
| `adb shell dumpsys activity activities \| grep topResumedActivity` | whether the app is in front |
| `adb shell dumpsys alarm \| grep -A3 "pl.serwerplex"` | the alarm (time; `window=0` = exact) |
| `adb shell dumpsys package pl.serwerplex.status \| grep -E "versionName\|granted"` | version and permissions |
| `adb shell appops get pl.serwerplex.status SYSTEM_ALERT_WINDOW` | "display over other apps" (`allow`) |
| `adb logcat -s StatusWatchdog` | the Termux watchdog |
| `adb logcat -s StatusRadio StatusControl` | the radio and its control server |
| `curl http://192.168.1.50:8098/radio/state` (from the PC) | radio state; `info` shows what the failsafe is doing |
| `cat ~/watchdog.log` (Termux) | `[status-app] …` and `[cron] … Status app …` entries |
| `ls -la ~/status/app-heartbeat` (Termux) | the app's last heartbeat |
| `adb shell am force-stop pl.serwerplex.status; adb shell am start -n pl.serwerplex.status/.MainActivity` | restart the app (the alarm is re-created) |

---

## 8. Version history

| Version | Date | Changes |
|---|---|---|
| 1.0 (1) | 2026-10-01 | first: full screen, WebView, 06–23 screen control, alarm, start after boot, battery for the page |
| 1.1 (2) | 2026-10-01 | `setAlarmClock` instead of `setExactAndAllowWhileIdle` (realme applied a window of up to 1 h) |
| 1.2 (3) | 2026-10-01 | `Watchdog`: heartbeat `/ping?app=1` and reviving Termux through `RUN_COMMAND`; `RUN_COMMAND` permission, `<queries>` |
| 1.3 (4) | 2026-10-01 | radio: `RadioPlayer` (MediaPlayer, sleep timer, 23:00 stop, Bluetooth disconnect → stop, Wi-Fi lock), `ControlServer` (:8098) |
| 1.3.1 (5) | 2026-10-01 | second engine: plain streams (Icecast MP3/AAC) through a hidden WebView, because realme's MediaPlayer never finishes preparing them |
| 1.3.2 (6) | 2026-10-01 | playback number in the WebView engine's events: an error while stopping the previous station no longer counts as an error of the new one |
| 1.3.3 (7) | 2026-10-02 | radio failsafe: address list `url` → `alt` (new `radio.json` field) → Radio Browser by `uuid` (servers `de1`, `nl1`, `at1`); after 6 quick attempts without internet it waits for the network and resumes by itself; with a working network, slow retries 30 s…5 min for about 30 min with freshly read addresses. New permission `ACCESS_NETWORK_STATE` |

Rejected earlier attempt: installing the page as a web app from Chrome ("Install"). Chrome 154 creates real installed web apps (WebAPKs) only through Google's servers, which cannot reach a page on the phone's `127.0.0.1`. The result was a plain shortcut that opens a tab with the address bar.
