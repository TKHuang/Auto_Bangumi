#!/usr/bin/env bash
# Create an evidence dir for one verification run and print its path.
# Usage: RUN=$(.claude/skills/verify/scripts/new-run.sh <short-name>)
source "$(dirname "$0")/_common.sh"
d="$EVIDENCE_ROOT/$(date +%Y%m%d-%H%M%S)-${1:-run}"
mkdir -p "$d"; git -C "$REPO" rev-parse --short HEAD > "$d/commit.txt"; echo "$d"
