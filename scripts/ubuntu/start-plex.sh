#!/bin/bash
# Starts Plex Media Server inside Ubuntu (proot-distro). Lives at /root/start-plex.sh.
# Needed because PRoot has no systemd, so "service plexmediaserver start" does not work.
export PLEX_MEDIA_SERVER_APPLICATION_SUPPORT_DIR="/var/lib/plexmediaserver/Library/Application Support"
export PLEX_MEDIA_SERVER_HOME=/usr/lib/plexmediaserver
export PLEX_MEDIA_SERVER_MAX_PLUGIN_PROCS=6
export LD_LIBRARY_PATH=/usr/lib/plexmediaserver/lib
mkdir -p "$PLEX_MEDIA_SERVER_APPLICATION_SUPPORT_DIR"
cd /usr/lib/plexmediaserver
exec ./"Plex Media Server"
