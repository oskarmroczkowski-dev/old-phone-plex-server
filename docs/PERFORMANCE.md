# Performance tests

Measured on 2026-10-01 on the reference phone (realme GT Master Edition, Snapdragon 778G, 8 GB RAM, Android 13, Plex Media Server 1.43.4 in Ubuntu/PRoot). Nobody was watching during the tests, and the test files were deleted afterwards.

## Software transcoding

Plex's own transcoder (`Plex Transcoder`, run with the exact options Plex used: `libx264 -preset veryfast`, scale, audio to MP3) on real H.264 files from the library, 60 s of video per stream, output discarded. Speed > 1.0× means the transcode keeps up with playback.

| Test | Speed of each stream | Whole CPU (8 cores) | Max CPU temp |
|---|---|---|---|
| 1 × 1080p (8.5 Mb/s) → 720p | 1.29× | 49 % | 49 °C |
| 2 × 1080p → 720p at once | 1.52× and 1.49× | 75 % | 66 °C |
| 3 × 1080p → 720p at once | 1.26×, 1.22×, 1.17× | 86 % | 71 °C |
| 1 × 720p → 480p | 1.59× | 44 % | 58 °C |
| 3 × 720p → 480p at once | 1.67×, 1.65×, 1.35× | 75 % | 67 °C |
| 4K HEVC 10-bit (requested by a TV through Plex) | **0.1–0.4×** | – | 64 °C |

- A single transcode is slower than two in parallel: one `ffmpeg` process does not use all 8 cores, and the first run also warmed up the CPU governor and the file cache.
- Each test lasted about a minute. A two-hour film may run warmer; with up to two TVs and 720p/1080p H.264 material there is plenty of headroom, and usually no transcoding is needed at all (Direct Play).
- **4K cannot be transcoded on this phone.** 4K must be Direct Played.

## 4K Direct Play

Free test clips from the Jellyfin project (4K HEVC 10-bit, SDR, 29 s, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)) played on a 2021 Samsung 4K TV (Tizen, Plex app), with quality set to Original:

| File | What Plex did | Result |
|---|---|---|
| 4K HEVC 40 Mb/s | **Direct Play** | ✅ smooth; phone stayed at 35–38 °C |
| 4K HEVC 100 Mb/s | the TV requested a transcode | ❌ endless buffering (transcode at 0.1–0.4×) |
| 4K HEVC 150 Mb/s | the TV requested a transcode | ❌ endless buffering |

**Why:** the TV's Plex app sends a client profile to the server. For HEVC it declared: up to 4096×2160, 10-bit, 60 fps, **max 80 Mb/s**, HDR10 allowed, **no Dolby Vision profile 5**. Above those limits the TV itself disables Direct Play, and the Plex log shows `MDE: … Direct Play is disabled`. Image-based subtitles (PGS) also force a transcode. Other TVs have other limits; check the `add-limitation(...)` entries in the Plex log after starting playback.

## 4K HDR10 and a second TV (2026-10-02)

Jellyfin 4K HEVC HDR10 clips (~30 s each, plus the SDR 10-bit 40 Mb/s clip), copied to the drive with a checksum check, played with quality set to Original. "On screen" is what a person saw; the decision and bitrate come from the server (`/status/sessions` every 3 s and the Plex log).

| Clip | 2021 Samsung TV (Tizen) | realme Smart TV (Android TV 11, 4K panel) |
|---|---|---|
| 4K HEVC 10-bit **SDR 40 Mb/s** | ✅ smooth (2026-10-01) | ❌ does not start |
| 4K **HDR10 40 Mb/s** | – | ❌ does not start |
| 4K **HDR10 70 Mb/s** | ✅ **Direct Play, picture OK** (68.9 Mb/s, phone 34–36 °C) | ❌ does not start |
| 4K **HDR10 80 Mb/s** | ❌ **black screen** with a moving progress bar, although the server reports Direct Play (78.8 Mb/s) | – |
| 4K **HDR10 90 Mb/s** | ❌ the TV disables Direct Play ("no direct play video profile exists for http/mp4/hevc"); transcode at 0.2–0.3×, phone 53–58 °C | – |

- **Samsung: the practical 4K HDR10 limit is 70 Mb/s.** The 80 Mb/s cap in its profile is nominal: an average of 78.8 Mb/s (with peaks above 80) is accepted but not displayed.
- **realme:** its Plex app reports a **3840×2160** screen and H.264/HEVC support (`videoResolution=3840x2160` in the Plex log), yet for every 4K HEVC 10-bit clip it only fetched the item details and **never asked the server to play** (no `decision` request, no `/library/parts` request): a spinner forever. Ordinary films play by Direct Play: 480p H.264 in this test, 1080p in the owner's test the day before. Its player simply cannot handle 4K HEVC 10-bit; 4K H.264 was not tested.
- **Server Direct Play is not proof of a picture.** Always confirm on the TV itself.
- **Why the phone cannot help by transcoding:** Plex for Linux (inside Ubuntu/PRoot) has no access to the phone's hardware video encoder, so a 4K transcode runs on the CPU at 0.2–0.3× (HDR → SDR tone mapping included). Root would mostly bring a real chroot and a fixed high CPU clock; we estimate that at 10–20 % (not measured), far from the ~4× needed.

The phone itself was not the bottleneck.

## Throughput

| Path | Result |
|---|---|
| USB drive → Wi-Fi → PC (the Direct Play path; Wi-Fi at -56 dBm) | **25 MB/s ≈ 200 Mb/s** |
| PC → phone over Wi-Fi with SSH encryption (no disk write) | 95.5 MB/s |
| Phone internal storage → USB drive (`cp`) | 20–23 MB/s |
| Phone USB 2.0 port → USB drive (read) | ~27 MB/s |

200 Mb/s covers 4K up to the Samsung's practical 70 Mb/s HDR10 limit, and two TVs at typical 4K bitrates (15–40 Mb/s).

## Status dashboard animation

Measured on the phone through ADB (`top`) on 2026-10-01, landscape layout, daytime:

| Version | Whole phone CPU |
|---|---|
| Dashboard without the background animation | 6–9 % |
| First version with the spinning Earth | ~21 % |
| After optimising (own timer instead of `requestAnimationFrame`, 8 fps, static layers drawn once, lighter outlines, canvases at 2× instead of 3×) | **15–21 %**; app process ~34 % of one core + page renderer ~23 %; CPU 33–45 °C |

The phone's display refreshes at 120 Hz, and `requestAnimationFrame` woke the renderer on every refresh; the own timer runs the Earth at 8 fps and the stars and zodiac sign at 4 fps. Everything stops at night and in portrait. To save more, lower `GLOBE.fps` in `index.html` from 8 to 6.

## Radio

| What | Result (2026-10-02) |
|---|---|
| Stations streaming from the phone (nightly `check-stations.py`, all 90) | all playing; the check takes ~15 s (6 in parallel) |
| Internet cut while playing (emulator, Wi-Fi and data off) | waits; playing again **6 s** after the network returned |
| Typical stream bitrate | 48 kb/s AAC+ (Bauer) to 128 kb/s MP3 (Global, 181.FM, Radio Paradise): negligible next to Plex |

## How to reproduce

**Transcoding.** Start any transcode in Plex, then copy the exact command from `Logs/Plex Media Server.log` (lines with `Job running: … "Plex Transcoder" …`). Run it inside Ubuntu with:
```
export FFMPEG_EXTERNAL_LIBS="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Codecs/<version>-linux-aarch64/"
export LD_LIBRARY_PATH=/usr/lib/plexmediaserver/lib
cd /usr/lib/plexmediaserver
./"Plex Transcoder" -ss 600 -i "<file>" -t 60 … -f null -      # time it; speed = 60 s / wall time
```
Run several in parallel with `&` and `wait`.

**CPU load.** Measure through ADB (`adb shell head -1 /proc/stat` before and after). Inside Termux, `top` and `/proc/stat` do not show other processes' load on Android 13, so CPU appears as 0 %.

**Temperature.** Read the `cpu-*` zones in `/sys/class/thermal/thermal_zone*/` from Termux.

**Direct Play or transcode?** Poll `http://127.0.0.1:32400/status/sessions` (with the token, on the phone). If there is no `TranscodeSession` element, it is Direct Play. The reason for a transcode is in the Plex log (`MDE:` lines).

> Driving transcodes through Plex's HLS API (`/video/:/transcode/universal/start.m3u8`) from a script proved unreliable for benchmarking: segment timing depends on seeking and throttling, and later sessions returned 404. Running the transcoder directly is reproducible.

**Copying test files safely.** The phone downloaded the files itself into a staging folder in internal storage (`/storage/emulated/0/<folder>`), verified SHA-256, then copied them to the USB drive one at a time under a `.part` name with `nice -n 19` and renamed them only after the checksum matched. Neither the PC nor the network drive was involved.
