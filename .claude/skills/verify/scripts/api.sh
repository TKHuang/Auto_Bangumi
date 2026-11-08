#!/usr/bin/env bash
# Call the AB API as a logged-in user. Logs in to AB (not PikPak) once per run dir.
# Usage: api.sh <run-dir> <METHOD> <path> [json-body]
#   api.sh "$RUN" GET  /api/v1/bangumi/get/all
#   api.sh "$RUN" POST /api/v1/rss/analysis '{"url":"https://mikanani.me/RSS/Bangumi?bangumiId=3519&subgroupid=583"}'
source "$(dirname "$0")/_common.sh"
run="$1"; method="$2"; path="$3"; body="${4:-}"
jar="$run/cookies.txt"
if [ ! -s "$jar" ]; then
  curl -s -c "$jar" -o /dev/null -w '' -X POST "$BACKEND/api/v1/auth/login" -d "username=$AB_USER&password=$AB_PASS"
fi
log="$run/api.log"
{ echo ">>> $method $path"; [ -n "$body" ] && echo "$body"; } >> "$log"
if [ -n "$body" ]; then
  out=$(curl -s -b "$jar" -X "$method" -H 'Content-Type: application/json' -d "$body" -w '\n[http %{http_code}]' "$BACKEND$path")
else
  out=$(curl -s -b "$jar" -X "$method" -w '\n[http %{http_code}]' "$BACKEND$path")
fi
echo "$out" | tee -a "$log"; echo >> "$log"
