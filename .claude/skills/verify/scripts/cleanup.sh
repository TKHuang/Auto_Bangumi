#!/usr/bin/env bash
# Tear down what a verify run started. Keeps evidence in dev-config/verify-evidence/.
# Usage: cleanup.sh
# Delete test bangumi/RSS (with PikPak files) through the API BEFORE this; see SKILL.md Cleanup.
source "$(dirname "$0")/_common.sh"
AGENT_BROWSER_SESSION=ab-verify agent-browser close >/dev/null 2>&1 || true
(cd "$REPO" && make down)
echo "evidence kept in: $EVIDENCE_ROOT"; ls -1 "$EVIDENCE_ROOT" | tail -5
