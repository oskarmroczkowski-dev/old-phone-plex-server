#!/data/data/com.termux/files/usr/bin/bash
# Starts the status page server (port 8099) if it is not running.
# With --open it also opens the status page in Chrome on the phone (legacy option; the
# "Server Status" app now opens itself, so this option is normally not used).
# Called by start-server.sh (at boot, every 5 min from cron, when Termux is opened).
LOG=~/status/server.log

if ! pgrep -f "^python[0-9.]* .*status-server[.]py" >/dev/null; then
  echo "$(date '+%F %T') starting status server" >> "$LOG"
  nohup python ~/status/status-server.py >> "$LOG" 2>&1 &
fi

# wait until the page responds (max 15 s)
for i in $(seq 1 15); do
  curl -s -o /dev/null http://127.0.0.1:8099/ && break
  sleep 1
done

if [ "$1" = "--open" ]; then
  . ~/status/open-status.conf 2>/dev/null
  if [ -n "$WEBAPK" ]; then
    am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p "$WEBAPK" >/dev/null 2>&1
  else
    am start -a android.intent.action.VIEW -d "http://127.0.0.1:8099/" -p com.android.chrome >/dev/null 2>&1
  fi
  echo "$(date '+%F %T') opened status screen (${WEBAPK:-Chrome tab})" >> "$LOG"
fi

# keep the log from growing forever
tail -n 500 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
