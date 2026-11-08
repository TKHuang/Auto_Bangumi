#!/usr/bin/env bash
# Read-only SQL against the dev DB (inside the backend container, WAL-safe).
# Usage: db.sh "select id, official_title, save_path from bangumi"
source "$(dirname "$0")/_common.sh"
docker exec -i "$BACKEND_CTR" python3 - "$1" <<'PY'
import sqlite3, sys
con = sqlite3.connect("file:/app/data/bangumi.db?mode=ro", uri=True)
cur = con.execute(sys.argv[1])
print(" | ".join(d[0] for d in cur.description or []))
for row in cur.fetchall(): print(" | ".join(str(v) for v in row))
PY
