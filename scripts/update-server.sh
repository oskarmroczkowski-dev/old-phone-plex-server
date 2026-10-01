#!/data/data/com.termux/files/usr/bin/bash
# Weekly update: Termux + Ubuntu + Plex. Log: ~/update.log
exec >> ~/update.log 2>&1
echo "===== $(date '+%F %T') START ====="
# lock: the cron watchdog (start-server.sh) will not start Plex while the update runs
touch ~/.update-in-progress
trap 'rm -f ~/.update-in-progress' EXIT
pkill -f "[P]lex Media Server"; pkill -f "[P]lex Plug"; sleep 5
yes | pkg upgrade -y -o Dpkg::Options::=--force-confold
proot-distro login ubuntu -- bash -c "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get -y -o Dpkg::Options::=--force-confold upgrade && apt-get -y autoremove && apt-get clean"
rm -f ~/.update-in-progress
~/start-server.sh update
sleep 60
curl -s -o /dev/null -w "Plex after update: HTTP %{http_code}\n" http://127.0.0.1:32400/identity
echo "===== $(date '+%F %T') END ====="
tail -n 2000 ~/update.log > ~/update.log.tmp && mv ~/update.log.tmp ~/update.log
