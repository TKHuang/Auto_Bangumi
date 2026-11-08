#!/usr/bin/env bash
# Self-test for guard.sh with a throwaway busybox container. Touches no PikPak and no real stack
# (guard's `make down` runs, but the dev stack must already be down: this test refuses otherwise).
# Usage: guard-selftest.sh   -> prints PASS/FAIL per case; exit 0 only if all pass.
set -u
D="$(cd "$(dirname "$0")" && pwd)"
docker inspect ab-backend-dev >/dev/null 2>&1 && { echo "dev stack is up; run make down first"; exit 2; }
export AB_VERIFY_BACKEND_CTR=ab-guard-selftest
export AB_VERIFY_EVIDENCE_ROOT="$(mktemp -d)"
C=$AB_VERIFY_BACKEND_CTR; fails=0
pass() { echo "PASS: $1"; }; fail() { echo "FAIL: $1"; fails=$((fails+1)); }
rmc() { docker rm -f "$C" >/dev/null 2>&1; }

# Case 1: container restarts (crash + restart policy), guard keeps watching, then fires on a later failure.
rmc; docker run -d --name "$C" --restart unless-stopped busybox sh -c 'echo boot; sleep 4; exit 1' >/dev/null
"$D/guard.sh" > "$AB_VERIFY_EVIDENCE_ROOT/g1.log" 2>&1 & g=$!
sleep 12
kill -0 $g 2>/dev/null && pass "guard survives container restart" || fail "guard exited after restart: $(tail -2 "$AB_VERIFY_EVIDENCE_ROOT/g1.log")"
docker update --restart no "$C" >/dev/null; docker rm -f "$C" >/dev/null
docker run -d --name "$C" busybox sh -c 'sleep 2; echo "PikPak login failed: selftest"; sleep 120' >/dev/null
t0=$(date +%s); wait $g; rc=$?; dt=$(( $(date +%s) - t0 ))
# The backend stays silent after the failure line; the guard must not wait for more log output.
[ $dt -lt 20 ] && pass "guard stops ${dt}s after failure (silent backend)" || fail "guard hung ${dt}s after failure line"
[ $rc = 1 ] && pass "guard exits 1 on login failure" || fail "guard exit code $rc, want 1"
[ -f "$AB_VERIFY_EVIDENCE_ROOT/PIKPAK_LOGIN_FAILED" ] && pass "stop marker written" || fail "no stop marker"
( source "$D/_common.sh"; check_stop_marker ) >/dev/null 2>&1; [ $? = 3 ] && pass "marker blocks relaunch" || fail "marker does not block"
rm -f "$AB_VERIFY_EVIDENCE_ROOT/PIKPAK_LOGIN_FAILED"; rmc

# Case 2: normal shutdown -> guard exits 0.
docker run -d --name "$C" busybox sleep 300 >/dev/null
"$D/guard.sh" > "$AB_VERIFY_EVIDENCE_ROOT/g2.log" 2>&1 & g=$!
sleep 3; docker stop -t 1 "$C" >/dev/null
wait $g; rc=$?
[ $rc = 0 ] && pass "guard exits 0 on normal stop" || fail "guard exit $rc on normal stop"
rmc

# Case 3: no guard -> doctor/wait-ready refuse.
( source "$D/_common.sh"; check_guard_alive ) >/dev/null 2>&1 && fail "check_guard_alive passed without guard" || pass "no guard -> check fails"

rm -rf "$AB_VERIFY_EVIDENCE_ROOT"
[ $fails = 0 ] && echo "ALL PASS" || { echo "$fails FAILED"; exit 1; }
