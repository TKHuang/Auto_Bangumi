#!/usr/bin/env bash
# Start in the background BEFORE `make dev`, and keep it running for the whole session.
# Fail-closed: if a PikPak login fails, OR the guard can no longer watch a running
# backend, it runs `make down`. Re-attaches after a container restart.
# Exit 0 = backend container removed (make down). Exit 1 = login failed (stop marker written; tell the user).
# Exit 5 = could not watch; stack stopped as a precaution.
source "$(dirname "$0")/_common.sh"
set +e
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
fired="$EVIDENCE_ROOT/.guard-fired.$$"
rm -f "$fired"
if [ -f "$GUARD_PID_FILE" ] && kill -0 "$(cat "$GUARD_PID_FILE")" 2>/dev/null; then
  echo "guard: another guard is running (pid $(cat "$GUARD_PID_FILE"))"; exit 0
fi
echo $$ > "$GUARD_PID_FILE"
fifo="$EVIDENCE_ROOT/.guard-fifo.$$"
logs_pid=""
trap '[ -n "$logs_pid" ] && kill "$logs_pid" 2>/dev/null; rm -f "$GUARD_PID_FILE" "$fired" "$fifo"' EXIT

stop_stack() { (cd "$REPO" && make down) >&2; }
running() { [ "$(docker inspect -f '{{.State.Running}}' "$BACKEND_CTR" 2>/dev/null)" = "true" ]; }
exists() { docker inspect "$BACKEND_CTR" >/dev/null 2>&1; }

echo "guard: started $since, waiting for $BACKEND_CTR"
for _ in $(seq 1 600); do exists && break; sleep 1; done
exists || { echo "guard: $BACKEND_CTR never appeared"; exit 4; }

attach_failures=0
while exists; do
  # No pipeline: bash would wait for `docker logs -f` to exit, which only happens
  # on the NEXT log line. Run it in the background and kill it when we are done.
  rm -f "$fifo"; mkfifo "$fifo"
  docker logs -f --since "$since" "$BACKEND_CTR" > "$fifo" 2>&1 & logs_pid=$!
  while IFS= read -r line; do
    case "$line" in
      *"PikPak login failed"*|*"PikPak login on cooldown"*)
        { echo "time: $(date '+%F %T')"; echo "log: $line"; } > "$STOP_MARKER"
        touch "$fired"; break ;;
    esac
  done < "$fifo"
  kill "$logs_pid" 2>/dev/null; wait "$logs_pid" 2>/dev/null; logs_pid=""; rm -f "$fifo"
  if [ -f "$fired" ]; then
    echo "guard: PikPak login failed -> stopping dev stack" >&2
    stop_stack
    echo "VERIFY-STOP: PikPak login failed. Stack stopped. Tell the user. Do not relaunch." >&2
    exit 1
  fi
  # Stream ended. Only a removed container (make down) is a normal shutdown.
  # A container that exists but is not running may be in restart backoff
  # (up to 1 min): keep waiting, never leave it unwatched.
  while exists && ! running; do sleep 1; done
  exists || break
  # Backend running again (restart, or stream error): re-attach, but not forever.
  # A crash loop also counts here, and ends in make down (fail-closed).
  attach_failures=$((attach_failures + 1))
  echo "guard: log stream ended while backend runs; re-attach #$attach_failures"
  if [ $attach_failures -ge 5 ]; then
    echo "VERIFY-STOP: guard cannot keep watching the backend log; stopping stack as a precaution." >&2
    stop_stack; exit 5
  fi
done
echo "guard: backend container removed; guard exits"
