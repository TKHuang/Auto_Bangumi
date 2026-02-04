#!/bin/bash
set -e

# ===========================================================================
# Jellyfin + Rclone Combined Entrypoint
#
# 1. Reads PikPak credentials from AutoBangumi config
# 2. Generates rclone.conf with OAuth token or password auth
# 3. Hands off to supervisord which manages both rclone and jellyfin
#
# If AB config is missing or PikPak is not configured, jellyfin starts
# standalone (no rclone mount).
# ===========================================================================

AB_CONFIG_DIR="${AB_CONFIG_DIR:-/ab-config}"
RCLONE_CONF="/run/rclone.conf"

# Select config file based on environment
if [ "$AB_ENV" = "dev" ]; then
    CONFIG_FILE="${AB_CONFIG_DIR}/config_dev.json"
else
    CONFIG_FILE="${AB_CONFIG_DIR}/config.json"
fi
TOKEN_FILE="${AB_CONFIG_DIR}/pikpak_token.json"

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
# Generate rclone.conf (token-based or password-based auth)
# ---------------------------------------------------------------------------
if [ "$SKIP_RCLONE" = "false" ]; then
    echo "[entrypoint] Generating rclone config..."

    # Check for existing OAuth token from AutoBangumi
    if [ -f "$TOKEN_FILE" ]; then
        echo "[entrypoint] Found existing PikPak token from AutoBangumi"

        ACCESS_TOKEN=$(jq -r '.access_token // empty' "$TOKEN_FILE")
        REFRESH_TOKEN=$(jq -r '.refresh_token // empty' "$TOKEN_FILE")
        EXPIRES_AT=$(jq -r '.expires_at // empty' "$TOKEN_FILE")

        if [ -n "$ACCESS_TOKEN" ] && [ -n "$REFRESH_TOKEN" ]; then
            # Convert Unix timestamp to ISO8601 for rclone
            EXPIRY=$(date -u -d "@$EXPIRES_AT" "+%Y-%m-%dT%H:%M:%S.000000000+00:00" 2>/dev/null || \
                     date -u -r "$EXPIRES_AT" "+%Y-%m-%dT%H:%M:%S.000000000+00:00" 2>/dev/null || \
                     date -u -D "%s" -d "$EXPIRES_AT" "+%Y-%m-%dT%H:%M:%S.000000000+00:00" 2>/dev/null || \
                     echo "")

            if [ -n "$EXPIRY" ]; then
                TOKEN_JSON=$(jq -c -n \
                    --arg at "$ACCESS_TOKEN" \
                    --arg rt "$REFRESH_TOKEN" \
                    --arg exp "$EXPIRY" \
                    '{access_token: $at, token_type: "Bearer", refresh_token: $rt, expiry: $exp}')

                if [ -n "$PIKPAK_PASS" ]; then
                    OBSCURED_PASS=$(rclone obscure "$PIKPAK_PASS")
                    cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
pass = ${OBSCURED_PASS}
token = ${TOKEN_JSON}
EOF
                    echo "[entrypoint] Auth: OAuth token + password fallback"
                else
                    cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
token = ${TOKEN_JSON}
EOF
                    echo "[entrypoint] Auth: OAuth token only"
                fi
            fi
        fi
    fi

    # Fallback: password-only auth if token wasn't usable
    if [ ! -f "$RCLONE_CONF" ]; then
        if [ -z "$PIKPAK_PASS" ]; then
            echo "[entrypoint] ERROR: No token and no password — cannot mount PikPak"
            SKIP_RCLONE=true
        else
            OBSCURED_PASS=$(rclone obscure "$PIKPAK_PASS")
            cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
pass = ${OBSCURED_PASS}
EOF
            echo "[entrypoint] Auth: password only"
        fi
    fi

    if [ -f "$RCLONE_CONF" ]; then
        chmod 600 "$RCLONE_CONF"
    fi
fi

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
