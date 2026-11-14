#!/bin/bash
# Healthy only when Jellyfin answers and, when PikPak is configured, the
# PikPak mount can be listed.
curl --noproxy localhost -fsS http://localhost:8096/health >/dev/null || exit 1
[ -f /run/rclone.skip ] && exit 0
timeout 20 ls /media/pikpak >/dev/null 2>&1 || { echo "PikPak mount unreadable"; exit 1; }
