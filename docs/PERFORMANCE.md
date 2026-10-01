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

The phone itself was not the bottleneck.

## Throughput

| Path | Result |
|---|---|
| USB drive → Wi-Fi → PC (the Direct Play path; Wi-Fi at -56 dBm) | **25 MB/s ≈ 200 Mb/s** |
| PC → phone over Wi-Fi with SSH encryption (no disk write) | 95.5 MB/s |
| Phone internal storage → USB drive (`cp`) | 20–23 MB/s |
| Phone USB 2.0 port → USB drive (read) | ~27 MB/s |

200 Mb/s covers 4K up to the TV's 80 Mb/s cap, and two TVs at typical 4K bitrates (15–40 Mb/s).

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
