# Shared settings for the verify helpers. Source this file; do not run it.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CONFIG="$REPO/dev-config/backend/config_dev.json"
TOKEN="$REPO/dev-config/backend/pikpak_token.json"
EVIDENCE_ROOT="${AB_VERIFY_EVIDENCE_ROOT:-$REPO/dev-config/verify-evidence}"   # override only in guard self-tests
STOP_MARKER="$EVIDENCE_ROOT/PIKPAK_LOGIN_FAILED"
REQUIRED_PATH="Bangumi-dev"
BACKEND="http://localhost:7893"
WEBUI="http://localhost:5173"
BACKEND_CTR="${AB_VERIFY_BACKEND_CTR:-ab-backend-dev}"   # override only in guard self-tests
WEBUI_CTR="ab-webui-dev"
AB_USER="${AB_USER:-admin}"
AB_PASS="${AB_PASS:-adminadmin}"
mkdir -p "$EVIDENCE_ROOT"

die() { echo "VERIFY-STOP: $*" >&2; exit 2; }

# Refuse to continue after a PikPak login failure. Only the user removes the marker.
check_stop_marker() {
  if [ -f "$STOP_MARKER" ]; then
    echo "VERIFY-STOP: a PikPak login failed earlier. Do NOT launch or log in again." >&2
    echo "Tell the user. Only the user deletes: $STOP_MARKER" >&2
    cat "$STOP_MARKER" >&2
    exit 3
  fi
}

# The downloader path must be the dev folder. Production uses the same account.
check_dev_path() {
  python3 - "$CONFIG" "$REQUIRED_PATH" <<'PY' || die "downloader.path is not '$REQUIRED_PATH' in $CONFIG. Fix it before launch."
import json, sys
d = json.load(open(sys.argv[1]))["downloader"]
ok = d.get("path") == sys.argv[2]
print(f"downloader.type={d.get('type')} downloader.path={d.get('path')!r} -> {'OK' if ok else 'WRONG'}")
sys.exit(0 if ok else 1)
PY
}

GUARD_PID_FILE="$EVIDENCE_ROOT/.guard.pid"

# The guard must be alive while the stack runs. Without it, a login failure is not seen.
check_guard_alive() {
  if [ -f "$GUARD_PID_FILE" ] && kill -0 "$(cat "$GUARD_PID_FILE")" 2>/dev/null; then
    echo "guard: running (pid $(cat "$GUARD_PID_FILE"))"
  else
    echo "VERIFY-STOP: guard.sh is not running. Run 'make down' now, then relaunch with guard first." >&2
    return 1
  fi
}
