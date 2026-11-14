#!/bin/bash
# Remount PikPak when /media/pikpak stops answering. The rclone program runs
# pikpak-session.sh before mounting, which logs in again if PikPak revoked
# the session.
set -u

INTERVAL="${PIKPAK_WATCHDOG_INTERVAL:-60}"
MAX_FAILS="${PIKPAK_WATCHDOG_MAX_FAILS:-3}"

if [ -f /run/rclone.skip ]; then
    echo "[watchdog] Skipped (no PikPak config)"
    exec sleep infinity
fi

fails=0
while sleep "$INTERVAL"; do
    if timeout 30 ls /media/pikpak >/dev/null 2>&1; then
        fails=0
        continue
    fi
    fails=$((fails + 1))
    echo "[watchdog] /media/pikpak unreadable ($fails/$MAX_FAILS)"
    if [ "$fails" -ge "$MAX_FAILS" ]; then
        echo "[watchdog] Restarting rclone"
        supervisorctl restart rclone
        fails=0
    fi
done
