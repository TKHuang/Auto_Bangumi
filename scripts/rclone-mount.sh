#!/bin/bash
set -e

if [ "$SKIP_RCLONE" = "true" ]; then
    echo "[rclone] Skipped (no PikPak config)"
    sleep infinity
fi

# Clean up stale FUSE mount from previous crash
fusermount -u /media/pikpak 2>/dev/null || fusermount3 -u /media/pikpak 2>/dev/null || true
mkdir -p /media/pikpak

echo "[rclone] Mounting pikpak:${PIKPAK_PATH} → /media/pikpak"

exec rclone mount "pikpak:${PIKPAK_PATH}" /media/pikpak \
    --config "${RCLONE_CONF}" \
    --vfs-cache-mode full \
    --cache-dir /cache/rclone \
    --vfs-cache-max-size "${RCLONE_CACHE_MAX_SIZE}" \
    --vfs-cache-max-age "${RCLONE_CACHE_MAX_AGE}" \
    --vfs-write-back 60s \
    --allow-other \
    --allow-non-empty \
    --exclude ".DS_Store" \
    --exclude "._**" \
    --disable-http2 \
    --fuse-flag="-o,backend=fskit" \
    --disable-http-keep-alives \
    --log-level INFO
