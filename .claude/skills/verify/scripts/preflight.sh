#!/usr/bin/env bash
# Run before every launch. Read-only. Exit 0 = safe to launch.
source "$(dirname "$0")/_common.sh"
check_stop_marker
check_dev_path
docker info >/dev/null 2>&1 || die "Docker is not running."
for p in 7893 5173; do
  owner=$(docker ps --filter "publish=$p" --format '{{.Names}}' | tr '\n' ' ')
  if [ -n "$owner" ] && [[ "$owner" != *"$BACKEND_CTR"* && "$owner" != *"$WEBUI_CTR"* ]]; then
    die "port $p is used by another container: $owner"
  fi
  if [ -z "$owner" ] && lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then
    die "port $p is used by a non-docker process: $(lsof -nP -iTCP:$p -sTCP:LISTEN | tail -1)"
  fi
done
python3 - "$TOKEN" <<'PY'
import json, os, sys, time
p = sys.argv[1]
if not os.path.exists(p):
    print("pikpak token: none -> first PikPak call does ONE full login")
else:
    t = json.load(open(p)); left = t.get("expires_at", 0) - int(time.time())
    print(f"pikpak token: access token {'valid ' + str(left) + 's' if left > 300 else 'expired'}"
          " (expired -> refresh_token first, full login only if refresh fails)")
PY
echo "PREFLIGHT OK"
