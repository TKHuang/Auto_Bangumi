#!/bin/bash
# Ensure $RCLONE_CONF holds a PikPak session that PikPak still accepts.
#
# rclone keeps its own session, separate from AutoBangumi's token. PikPak can
# revoke a session server-side while token refresh keeps "succeeding", so the
# probe below is the only reliable signal. AutoBangumi and the dev stack use
# the same paid account, and repeated failed logins lock it for 24 h, so a new
# login happens only when PikPak says "unauthenticated", at most once per
# PIKPAK_MIN_LOGIN_INTERVAL seconds, even across container restarts.
set -uo pipefail

STAMP="$(dirname "$RCLONE_CONF")/last-login-attempt"
MIN_LOGIN_INTERVAL="${PIKPAK_MIN_LOGIN_INTERVAL:-3600}"

if [ -f "$RCLONE_CONF" ] && grep -qxF "user = ${PIKPAK_USER}" "$RCLONE_CONF"; then
    if probe_err=$(timeout 60 rclone --config "$RCLONE_CONF" lsf pikpak: --dirs-only --max-depth 1 2>&1 >/dev/null); then
        echo "[pikpak] Session OK"
        exit 0
    fi
    if ! grep -qi unauthenticated <<<"$probe_err"; then
        echo "[pikpak] Probe failed without an auth error, keeping the session: ${probe_err##*$'\n'}"
        exit 0
    fi
    echo "[pikpak] PikPak rejected the session (unauthenticated)"
else
    echo "[pikpak] No session for ${PIKPAK_USER}"
fi

now=$(date +%s)
last=$(cat "$STAMP" 2>/dev/null || echo 0)
if [ $((now - last)) -lt "$MIN_LOGIN_INTERVAL" ]; then
    wait_s=$((MIN_LOGIN_INTERVAL - (now - last)))
    echo "[pikpak] Last login attempt was $((now - last))s ago, waiting ${wait_s}s before the next one"
    sleep "$wait_s"
fi
date +%s >"$STAMP"

echo "[pikpak] Logging in as ${PIKPAK_USER}"
new_conf=$(mktemp)
login_err=$(rclone --config "$new_conf" config create pikpak pikpak \
    user "$PIKPAK_USER" pass "$PIKPAK_PASS_OBSCURED" \
    --no-obscure --non-interactive 2>&1 >/dev/null)
if grep -q '^token = ' "$new_conf"; then
    mv "$new_conf" "$RCLONE_CONF"
    chmod 600 "$RCLONE_CONF"
    echo "[pikpak] Login OK, new session saved"
    exit 0
fi
rm -f "$new_conf"
echo "[pikpak] Login FAILED: ${login_err##*$'\n'}"
exit 1
