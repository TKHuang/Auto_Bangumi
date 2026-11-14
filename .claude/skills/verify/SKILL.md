---
name: verify
description: Drive the real AutoBangumi dev stack (Vue WebUI on :5173, FastAPI on :7893, PikPak downloader) the way a user does, and capture proof that a change works. Use after any backend or WebUI change that a user can see or that touches RSS, subscribe, download, rename, or delete; and when asked to "verify", "run the app", or "prove it works".
---

# Verify AutoBangumi in the real dev stack

The dev stack uses the user's **one paid PikPak account. Production uses the same account.** Three rules come before everything else:

1. **At most one PikPak login per run. Never retry a failed login.** Repeated failed logins ban the account for 24 h and break production. If the guard fires, or you see `PikPak login failed`, stop all work, do not relaunch, and tell the user.
2. **A successful dev login logs production out.** Production AutoBangumi and the dev stack both log in through pikpakapi, and PikPak keeps one such session per account: on 2026-11-14 each dev login (`Performing full PikPak authentication` in `ab-backend-dev`) made the production container `ab` fail with `invalid refresh token` on its next call. Jellyfin's rclone mount uses a different client and was not affected. Tell the user before a run whose token is expired (`preflight.sh` prints it), and after teardown check `docker logs --since 10m ab 2>&1 | grep -E 'invalid refresh token|Performing full'`. Production builds with the session-recovery fix log in again on their own within 10 minutes; older builds need `ab-config/pikpak_token.json` moved aside and `docker restart ab`, which the user must approve.
3. **Downloads go only to `Bangumi-dev`.** `dev-config/backend/config_dev.json` → `downloader.path` must be exactly `Bangumi-dev`. `preflight.sh` and `doctor.sh` refuse anything else. Never change it to the production folder.

All helpers are in `.claude/skills/verify/scripts/`. Run them from the repo root. Variables below: `S=.claude/skills/verify/scripts`.

## Launch

```bash
S=.claude/skills/verify/scripts
$S/preflight.sh                      # stop marker, Bangumi-dev path, ports, token state
$S/guard.sh                          # run_in_background: true — START BEFORE make dev
make dev                             # canonical; never run uvicorn/vite/docker compose by hand
$S/wait-ready.sh                     # prints READY when backend health=200 and webui serves /
$S/doctor.sh                         # prints DOCTOR OK
```

- Start `guard.sh` **before** `make dev`. The rename job runs right after startup and is the first PikPak call. When the access token has expired, that call does the full login. A guard started later misses it.
- `make dev` printing "ready" only means the containers started. `wait-ready.sh` waits until Alembic migrations are done and the API answers.
- The stack uses `dev-config/` (bind-mounted): config `dev-config/backend/config_dev.json`, DB `dev-config/data/bangumi.db`, PikPak token `dev-config/backend/pikpak_token.json`. These are separate from production (container `ab`, port 7892). Do not read or touch the `ab` container.
- A fresh DB has one user: `admin` / `adminadmin`.
- Teardown: see Cleanup.

**Guard is fail-closed.** It re-attaches when the backend container restarts (crash + `restart: unless-stopped` resets the in-process login cooldown, so an unwatched restart is the dangerous case). If it cannot keep watching a running backend, it runs `make down` and exits 5. `wait-ready.sh` and `doctor.sh` fail when the guard is not running (pid in `dev-config/verify-evidence/.guard.pid`). If the guard task ends while the stack is up, run `make down` at once.

While the backend container exists but is not running (restart backoff can last up to 1 min), the guard waits; it leaves only when `make down` removes the container. A crash loop (5 re-attaches) also ends in `make down`.

Guard exit codes: `0` backend container removed (`make down`), `1` PikPak login failed, `4` backend never appeared, `5` could not watch, stack stopped.

**Stop marker.** When the guard sees a login failure, it runs `make down` and writes `dev-config/verify-evidence/PIKPAK_LOGIN_FAILED`. While that file exists, `preflight.sh` and `doctor.sh` exit 3. Only the user deletes it. Do not delete it yourself.

## Doctor

`$S/doctor.sh` — read-only, and it does **not** call PikPak. It checks the stop marker, that the guard is running, the `Bangumi-dev` path, both containers, `GET /api/v1/health`, the WebUI, AB login, and prints the last PikPak auth log lines. Run it first whenever anything looks wrong.

Do not use `GET /api/v1/check/downloader` as a health check. It calls PikPak auth.

## Drive

Two harnesses. Use the WebUI for user journeys and the API helper for setup, cleanup, and side-effect checks.

**WebUI — agent-browser**, in its own session so it does not touch the user's browser:

```bash
export AGENT_BROWSER_SESSION=ab-verify
agent-browser open "http://localhost:5173/#/login"
agent-browser wait 'input[placeholder="username"]'
agent-browser fill 'input[placeholder="username"]' admin
agent-browser fill 'input[placeholder="password"]' adminadmin
agent-browser find role button click --name Login      # CSS :has-text() does not work here
agent-browser get url                                   # -> http://localhost:5173/#/bangumi
agent-browser snapshot -i                               # refs for the next click
agent-browser screenshot "$RUN/NN-name.png"
```

- The router uses hash history: routes are `/#/bangumi`, `/#/rss`, `/#/series`, `/#/config`, `/#/log`, `/#/pending-resolution`, `/#/merge-history`, `/#/calendar`, `/#/player`.
- Sidebar links have names: `HomePage`, `RSS Manager`, `Series`, `Config`, `Log`, `Pending Resolution`, `Merge History`.
- The top-bar "Add RSS" icon has no name. Click it with `agent-browser click '.i-icon-add-one'`.
- Buttons with text: `agent-browser find role button click --name <Text>`. Text matches: `agent-browser find text "<substring>" click`.

**API — `api.sh`** (logs in to AB once per run dir, keeps a cookie jar, and appends every call to `$RUN/api.log`):

```bash
$S/api.sh "$RUN" GET    /api/v1/bangumi/get/all
$S/api.sh "$RUN" DELETE "/api/v1/bangumi/delete/<id>?file=true"
```

**DB — `db.sh`** (read-only SQL inside the backend container):

```bash
$S/db.sh "select state, count(*), min(pikpak_cloud_path) from torrent group by state"
```

`bangumi` has no `save_path` column. The PikPak folder of each download is `torrent.pikpak_cloud_path`, which must start with `Bangumi-dev/`.

**Logs:** `docker logs --since 5m ab-backend-dev 2>&1 | grep -v health`. PikPak auth lines: `PikPak token expiring soon, refreshing...`, `Token refresh failed`, `Performing full PikPak authentication`, `Loaded valid PikPak token`, `PikPak login failed`.

The feature map is in [`features/README.md`](features/README.md). Drive every entry point it lists for the feature you changed.

## Evidence

```bash
RUN=$($S/new-run.sh <short-name>)    # dev-config/verify-evidence/<timestamp>-<name>/, records the commit
```

Put everything for one run in `$RUN`: numbered screenshots, `api.log`, DB query output (`| tee "$RUN/db-*.txt"`), and the PikPak auth log lines (`| tee "$RUN/pikpak-auth.log"`).

Proof standards:

- Use the real user path: the WebUI, or the same API calls the WebUI makes. Do not call internal functions or set DB rows by hand.
- Capture the action and the result: a screenshot before and after, plus the API response.
- Check side effects, not only the screen. For a download: a `torrent` row with `pikpak_cloud_path` under `Bangumi-dev/`, and the task id in the DEBUG line `Download added, result: {... 'task': {'id': '<task id>' ...`. For a delete: `Batch deleting N offline tasks (delete_files=True)`, then the DEBUG line `Delete tasks request: ... params={'task_ids': '<task id>' ...` with the same task id, and the rows removed. `Adding download to PikPak` and `Batch deleting` do not carry the id. DEBUG lines print only because `dev-config/backend/config_dev.json` sets `log.debug_enable: true`; keep it on.
- Record how many PikPak logins the run did (`pikpak-auth.log`). The answer must be 0 or 1.
- Keep PikPak usage small: every subscribe downloads real files into the user's paid storage. In the subscribe dialog, keep one episode and exclude the rest (see `features/rss-subscribe.md`).

## Cleanup

1. Delete every bangumi and RSS the run created, through the API. This also deletes the PikPak tasks and files in `Bangumi-dev`:
   ```bash
   $S/api.sh "$RUN" DELETE "/api/v1/bangumi/delete/<id>?file=true"
   $S/api.sh "$RUN" DELETE "/api/v1/rss/delete/<rss_id>"
   $S/db.sh "select (select count(*) from bangumi) b, (select count(*) from torrent) t, (select count(*) from rssitem) r"
   ```
   Check the DEBUG line `Delete tasks request: ... params={'task_ids': '<id>' ...`: the id must be the one this run created.
2. `$S/cleanup.sh` — closes the `ab-verify` browser session and runs `make down`. The guard exits when the log stream ends.
3. Confirm `ls dev-config/verify-evidence/<run>` still lists the evidence.

Do not use `make clean`: it removes the WebUI node_modules volume, and the next start reinstalls everything. Do not delete `dev-config/` files. Never stop containers by name except through `make`.

## Helpers

| Script | Use |
|---|---|
| `preflight.sh` | Before launch. Exit 0 = safe. |
| `guard.sh` | Background, before `make dev`. Exit 1 = PikPak login failed; stop and tell the user. |
| `guard-selftest.sh` | Proves the guard with a throwaway busybox container (stack must be down). Run after editing `guard.sh` or `_common.sh`. Prints ALL PASS. |
| `wait-ready.sh` | After `make dev`. Prints READY. |
| `doctor.sh` | Read-only health check. Prints DOCTOR OK. |
| `new-run.sh <name>` | Make an evidence dir and print its path. |
| `api.sh <run> <METHOD> <path> [json]` | Logged-in API call. |
| `db.sh "<sql>"` | Read-only SQL on the dev DB. |
| `cleanup.sh` | Close browser session, `make down`. |
