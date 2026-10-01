#!/data/data/com.termux/files/usr/bin/bash
# Starts everything that is not running: wake-lock, SSH, cron, the status page, Plex.
# Called: at phone boot (Termux:Boot), when Termux is opened (.bashrc), every 5 min by cron,
# by the "Server Status" app (when Termux was killed) and at the end of the weekly update.
# Argument = who called it; written to ~/watchdog.log whenever something gets (re)started.

# --- configuration ---
USB_ID="ABCD-1234"   # your USB drive ID, see: ls /storage
MEDIA_DIR="Media"    # top folder on the drive (contains Movies/ and TV Shows/)
# ---------------------

WHO="${1:-manual}"
LOCK=~/.start-server.lock
log() { echo "$(date '+%F %T') [$WHO] $*" >> ~/watchdog.log; }

# never run twice at once; a lock left by a dead process (e.g. killed Termux) is ignored
if ! mkdir "$LOCK" 2>/dev/null; then
  PID=$(cat "$LOCK/pid" 2>/dev/null)
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then exit 0; fi
  rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 0
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

[ "$WHO" = "status-app" ] && log "status page did not respond for 3 min, checking server"

termux-wake-lock
pgrep -f "^(/data/data/com.termux/files/usr/bin/)?sshd( |$)" >/dev/null || { log "starting sshd"; sshd; }
pgrep -x crond >/dev/null || { log "starting crond"; crond; }
~/status/start-status.sh   # status page (port 8099)

# during the weekly update (update-server.sh) leave Plex alone; a lock older than 2 h is ignored
if [ -n "$(find ~/.update-in-progress -mmin -120 2>/dev/null)" ]; then exit 0; fi

# Plex running or just starting (Ubuntu with /root/start-plex.sh already launched)? Then do nothing.
if ! pgrep -f "[P]lex Media Server" >/dev/null && ! pgrep -f "[/]root/start-plex[.]sh" >/dev/null; then
  # wait up to 60 s for the USB drive
  for i in $(seq 1 30); do [ -d "/storage/$USB_ID/$MEDIA_DIR" ] && break; sleep 2; done
  log "starting Plex"
  nohup proot-distro login ubuntu --bind "/storage/$USB_ID:/media/usb1" -- /root/start-plex.sh > ~/plex.log 2>&1 &
fi

tail -n 500 ~/watchdog.log > ~/watchdog.log.tmp 2>/dev/null && mv ~/watchdog.log.tmp ~/watchdog.log
