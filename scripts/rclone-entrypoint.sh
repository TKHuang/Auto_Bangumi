#!/bin/sh
set -e

# Install jq if not available (Alpine-based image)
if ! command -v jq >/dev/null 2>&1; then
    echo "Installing jq..."
    apk add --no-cache jq >/dev/null 2>&1
fi

# Select config file based on environment
if [ "$AB_ENV" = "dev" ]; then
    CONFIG_FILE="/config/config_dev.json"
    TOKEN_FILE="/config/pikpak_token.json"
else
    CONFIG_FILE="/config/config.json"
    TOKEN_FILE="/config/pikpak_token.json"
fi

echo "=== AB Rclone Sidecar ==="
echo "Environment: ${AB_ENV:-prod}"
echo "Config file: $CONFIG_FILE"

# Wait for config file to exist (with timeout)
echo "Waiting for config file..."
WAIT_TIMEOUT=120
WAIT_COUNT=0
while [ ! -f "$CONFIG_FILE" ]; do
    WAIT_COUNT=$((WAIT_COUNT + 2))
    if [ $WAIT_COUNT -ge $WAIT_TIMEOUT ]; then
        echo "ERROR: Config file $CONFIG_FILE not found after ${WAIT_TIMEOUT}s"
        echo "Check volume mounts in docker-compose"
        exit 1
    fi
    sleep 2
done
echo "Config file found."

# Extract PikPak config using jq
PIKPAK_USER=$(jq -r '.downloader.username // empty' "$CONFIG_FILE")
PIKPAK_PASS=$(jq -r '.downloader.password // empty' "$CONFIG_FILE")
PIKPAK_PATH=$(jq -r '.downloader.path // empty' "$CONFIG_FILE")

# Validate config exists
if [ -z "$PIKPAK_USER" ]; then
    echo "ERROR: PikPak username not found in $CONFIG_FILE"
    echo "Ensure downloader.username is set in config"
    exit 1
fi

if [ -z "$PIKPAK_PATH" ]; then
    echo "ERROR: PikPak path not found in $CONFIG_FILE"
    echo "Ensure downloader.path is set in config"
    exit 1
fi

# Generate rclone.conf
RCLONE_CONF="/tmp/rclone.conf"

# Check if we have an existing token from AutoBangumi
if [ -f "$TOKEN_FILE" ]; then
    echo "Found existing PikPak token from AutoBangumi"

    # Extract token fields
    ACCESS_TOKEN=$(jq -r '.access_token // empty' "$TOKEN_FILE")
    REFRESH_TOKEN=$(jq -r '.refresh_token // empty' "$TOKEN_FILE")
    EXPIRES_AT=$(jq -r '.expires_at // empty' "$TOKEN_FILE")

    if [ -n "$ACCESS_TOKEN" ] && [ -n "$REFRESH_TOKEN" ]; then
        # Convert Unix timestamp to ISO8601 format for rclone
        # rclone expects: 2023-01-01T00:00:00.000000000+00:00
        # Try GNU date, then BSD date, then BusyBox date
        EXPIRY=$(date -u -d "@$EXPIRES_AT" "+%Y-%m-%dT%H:%M:%S.000000000+00:00" 2>/dev/null || \
                 date -u -r "$EXPIRES_AT" "+%Y-%m-%dT%H:%M:%S.000000000+00:00" 2>/dev/null || \
                 date -u -D "%s" -d "$EXPIRES_AT" "+%Y-%m-%dT%H:%M:%S.000000000+00:00" 2>/dev/null || \
                 echo "")

        if [ -n "$EXPIRY" ]; then
            # Create token JSON for rclone (compact, single line)
            TOKEN_JSON=$(jq -c -n \
                --arg at "$ACCESS_TOKEN" \
                --arg rt "$REFRESH_TOKEN" \
                --arg exp "$EXPIRY" \
                '{access_token: $at, token_type: "Bearer", refresh_token: $rt, expiry: $exp}')

            # Include password as fallback if token refresh fails
            if [ -n "$PIKPAK_PASS" ]; then
                OBSCURED_PASS=$(rclone obscure "$PIKPAK_PASS")
                cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
pass = ${OBSCURED_PASS}
token = ${TOKEN_JSON}
EOF
                echo "Using existing OAuth token (with password fallback)"
            else
                cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
token = ${TOKEN_JSON}
EOF
                echo "Using existing OAuth token"
            fi
        else
            echo "WARNING: Could not parse token expiry, falling back to password auth"
            OBSCURED_PASS=$(rclone obscure "$PIKPAK_PASS")
            cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
pass = ${OBSCURED_PASS}
EOF
        fi
    else
        echo "WARNING: Token file incomplete, falling back to password auth"
        OBSCURED_PASS=$(rclone obscure "$PIKPAK_PASS")
        cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
pass = ${OBSCURED_PASS}
EOF
    fi
else
    echo "No existing token found, using password authentication"
    echo "NOTE: First run requires AutoBangumi to authenticate first"

    if [ -z "$PIKPAK_PASS" ]; then
        echo "ERROR: PikPak password not found and no token available"
        exit 1
    fi

    OBSCURED_PASS=$(rclone obscure "$PIKPAK_PASS")
    cat > "$RCLONE_CONF" << EOF
[pikpak]
type = pikpak
user = ${PIKPAK_USER}
pass = ${OBSCURED_PASS}
EOF
fi

chmod 600 "$RCLONE_CONF"

echo "Generated rclone config for user: $PIKPAK_USER"
echo "Mounting pikpak:${PIKPAK_PATH} to /mnt/pikpak"
echo "Cache max size: ${RCLONE_CACHE_MAX_SIZE:-10G}"
echo "Cache max age: ${RCLONE_CACHE_MAX_AGE:-1h}"

# Create mount point if it doesn't exist
mkdir -p /mnt/pikpak

# Mount with VFS cache (read-write for bidirectional sync)
exec rclone mount "pikpak:${PIKPAK_PATH}" /mnt/pikpak \
    --config "$RCLONE_CONF" \
    --vfs-cache-mode full \
    --cache-dir /cache \
    --vfs-cache-max-size "${RCLONE_CACHE_MAX_SIZE:-10G}" \
    --vfs-cache-max-age "${RCLONE_CACHE_MAX_AGE:-1h}" \
    --vfs-write-back 5s \
    --allow-other \
    --allow-non-empty \
    --log-level INFO \
    --log-file /dev/stdout
