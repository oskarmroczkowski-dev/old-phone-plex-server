#!/data/data/com.termux/files/usr/bin/bash
# Every 5 min (cron): if during the day (6:00-23:00) the "Server Status" app has not sent a heartbeat
# for 15 min (e.g. swiped away from recents or force-stopped), open it again.
# Heartbeat: the app requests http://127.0.0.1:8099/ping?app=1 every minute, the server touches the file below.
HB=~/status/app-heartbeat
H=$(date +%H); H=$((10#$H))
[ "$H" -ge 6 ] && [ "$H" -lt 23 ] || exit 0
[ -f "$HB" ] || exit 0                       # the app has never reported yet
[ -n "$(find "$HB" -mmin -15)" ] && exit 0   # it reported within the last 15 min
echo "$(date '+%F %T') [cron] Status app silent for 15 min, reopening it" >> ~/watchdog.log
am start -n pl.serwerplex.status/.MainActivity >/dev/null 2>&1
touch "$HB"                                  # next attempt in 15 min at the earliest
