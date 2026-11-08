#!/usr/bin/env bash
# Block until the stack is usable: backend health 200 (startup + migrations done) and webui serves /.
# Gives up after ~3 min. Usage: wait-ready.sh
source "$(dirname "$0")/_common.sh"
check_guard_alive || die "start guard.sh before make dev"
curl -sf --retry 90 --retry-delay 2 --retry-all-errors -o /dev/null "$BACKEND/api/v1/health" || die "backend never became healthy; see: make logs-backend"
curl -sf --retry 90 --retry-delay 2 --retry-all-errors -o /dev/null "$WEBUI/" || die "webui never served /; see: make logs-webui"
docker logs "$BACKEND_CTR" 2>&1 | grep -E "Application startup complete|alembic upgrade head" | tail -2
echo "READY"
