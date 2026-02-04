#!/bin/bash
set -e

if [ "$SKIP_RCLONE" != "true" ]; then
    echo "[jellyfin] Waiting for PikPak mount..."
    MOUNT_TIMEOUT=60
    ELAPSED=0
    while [ "$ELAPSED" -lt "$MOUNT_TIMEOUT" ]; do
        if mountpoint -q /media/pikpak 2>/dev/null; then
            echo "[jellyfin] PikPak mount ready"
            break
        fi
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done

    if ! mountpoint -q /media/pikpak 2>/dev/null; then
        echo "[jellyfin] WARNING: PikPak mount not ready after ${MOUNT_TIMEOUT}s, starting anyway"
    fi
fi

echo "[jellyfin] Starting Jellyfin..."
exec /jellyfin/jellyfin \
    --datadir /config \
    --cachedir /cache/jellyfin \
    --ffmpeg /usr/lib/jellyfin-ffmpeg/ffmpeg
