#!/usr/bin/env bash
# Read-only health check. Does NOT call PikPak. Run first whenever anything looks off.
source "$(dirname "$0")/_common.sh"
fail=0
check_stop_marker
check_guard_alive || fail=1
check_dev_path || fail=1
for c in "$BACKEND_CTR" "$WEBUI_CTR"; do
  s=$(docker inspect -f '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$c" 2>/dev/null || echo missing)
  echo "container $c: $s"; [[ "$s" == running* ]] || fail=1
done
code=$(curl -s -o /dev/null -w '%{http_code}' "$BACKEND/api/v1/health" || true); echo "backend /api/v1/health: $code"; [ "$code" = 200 ] || fail=1
code=$(curl -s -o /dev/null -w '%{http_code}' "$WEBUI/" || true); echo "webui /: $code"; [ "$code" = 200 ] || fail=1
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BACKEND/api/v1/auth/login" -d "username=$AB_USER&password=$AB_PASS" || true)
echo "AB login ($AB_USER): $code"; [ "$code" = 200 ] || fail=1
echo "--- last PikPak auth lines in backend log:"
docker logs --since 6h "$BACKEND_CTR" 2>&1 | grep -E "PikPak (token|login|authentication)|Performing full PikPak|Loaded valid PikPak" | tail -5 || echo "(none)"
[ $fail = 0 ] && echo "DOCTOR OK" || { echo "DOCTOR FAIL"; exit 1; }
