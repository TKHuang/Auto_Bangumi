#!/bin/bash
set -e

# ===========================================================================
# Jellyfin + Rclone Combined Entrypoint
#
# 1. Reads PikPak credentials from AutoBangumi config
# 2. Exports them so rclone keeps its own PikPak session in /config/rclone
# 3. Hands off to supervisord which manages both rclone and jellyfin
#
# If AB config is missing or PikPak is not configured, jellyfin starts
# standalone (no rclone mount).
# ===========================================================================

AB_CONFIG_DIR="${AB_CONFIG_DIR:-/ab-config}"
RCLONE_CONF="/config/rclone/rclone.conf"

# Select config file based on environment
if [ "$AB_ENV" = "dev" ]; then
    CONFIG_FILE="${AB_CONFIG_DIR}/config_dev.json"
else
    CONFIG_FILE="${AB_CONFIG_DIR}/config.json"
fi

echo "=== Jellyfin + Rclone Combined Container ==="
echo "Environment: ${AB_ENV:-prod}"
echo "AB Config:   ${CONFIG_FILE}"

# ---------------------------------------------------------------------------
# Wait for AB config (AB may still be starting up)
# ---------------------------------------------------------------------------
echo "[entrypoint] Waiting for AB config file..."
WAIT_TIMEOUT=120
WAIT_COUNT=0
SKIP_RCLONE=false

while [ ! -f "$CONFIG_FILE" ]; do
    WAIT_COUNT=$((WAIT_COUNT + 2))
    if [ "$WAIT_COUNT" -ge "$WAIT_TIMEOUT" ]; then
        echo "[entrypoint] WARNING: Config $CONFIG_FILE not found after ${WAIT_TIMEOUT}s"
        echo "[entrypoint] Starting Jellyfin without PikPak mount"
        SKIP_RCLONE=true
        break
    fi
    sleep 2
done

# ---------------------------------------------------------------------------
# Extract PikPak credentials
# ---------------------------------------------------------------------------
if [ "$SKIP_RCLONE" = "false" ]; then
    echo "[entrypoint] Config file found, reading PikPak credentials..."

    PIKPAK_USER=$(jq -r '.downloader.username // empty' "$CONFIG_FILE")
    PIKPAK_PASS=$(jq -r '.downloader.password // empty' "$CONFIG_FILE")
    PIKPAK_PATH=$(jq -r '.downloader.path // empty' "$CONFIG_FILE")

    if [ -z "$PIKPAK_USER" ]; then
        echo "[entrypoint] WARNING: PikPak username not found in config"
        echo "[entrypoint] Starting Jellyfin without PikPak mount"
        SKIP_RCLONE=true
    fi

    if [ -z "$PIKPAK_PATH" ] && [ "$SKIP_RCLONE" = "false" ]; then
        PIKPAK_PATH="/"
        echo "[entrypoint] No PikPak path specified, using root"
    fi
fi

# ---------------------------------------------------------------------------
# Credentials for rclone's own PikPak session (see pikpak-session.sh)
# ---------------------------------------------------------------------------
if [ "$SKIP_RCLONE" = "false" ] && [ -z "$PIKPAK_PASS" ]; then
    echo "[entrypoint] ERROR: No PikPak password in config, cannot mount PikPak"
    SKIP_RCLONE=true
fi

if [ "$SKIP_RCLONE" = "true" ]; then
    touch /run/rclone.skip
else
    rm -f /run/rclone.skip
    mkdir -p "$(dirname "$RCLONE_CONF")"
    export PIKPAK_USER
    PIKPAK_PASS_OBSCURED=$(rclone obscure "$PIKPAK_PASS")
    export PIKPAK_PASS_OBSCURED
fi
unset PIKPAK_PASS

# ---------------------------------------------------------------------------
# Export env vars for child processes (supervisord inherits these)
# ---------------------------------------------------------------------------
export PIKPAK_PATH="${PIKPAK_PATH:-/}"
export RCLONE_CONF="${RCLONE_CONF}"
export RCLONE_CACHE_MAX_SIZE="${RCLONE_CACHE_MAX_SIZE:-10G}"
export RCLONE_CACHE_MAX_AGE="${RCLONE_CACHE_MAX_AGE:-1h}"
export SKIP_RCLONE="${SKIP_RCLONE}"

echo "[entrypoint] PIKPAK_PATH=${PIKPAK_PATH}"
echo "[entrypoint] RCLONE_CACHE_MAX_SIZE=${RCLONE_CACHE_MAX_SIZE}"
echo "[entrypoint] RCLONE_CACHE_MAX_AGE=${RCLONE_CACHE_MAX_AGE}"
echo "[entrypoint] SKIP_RCLONE=${SKIP_RCLONE}"

# ---------------------------------------------------------------------------
# Hand off to supervisord
# ---------------------------------------------------------------------------
echo "[entrypoint] Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
