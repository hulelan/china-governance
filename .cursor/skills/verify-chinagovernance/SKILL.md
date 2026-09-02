---
name: verify-chinagovernance
description: Drive the China Governance Archive web app (chinagovernance.com corpus search, browse/catalog, Policy Lens, document pages) the way a user does. Use when verifying UI/search/lens/document behavior, after web/ or template changes, or when asked to prove a feature in the running app.
---

# Verify chinagovernance (Governance Archive)

Agent-facing control skill for the **China Governance Archive** FastAPI app (`web.app:app`). Primary user surface is the server-rendered web UI: catalog search, browse, Policy Lens, document records, topical collections. JSON under `/api/v1/` mirrors several pages (including `/api/v1/stats`).

Write for the next agent. Do not copy production `documents.db` from the droplet (`104.236.88.45`) or a Mac. Do not point `SQLITE_PATH` at `documents.db`. Public `https://www.chinagovernance.com` is behind nginx basic auth (unauthenticated fetch → 401). Do not hunt or embed credentials. Live production is read-only context, not the drive target.

Feature map: [`features/README.md`](features/README.md). Prove one mapped feature per run; the map is the coverage source.

## Interview (this repo)

- **Surface:** Server-rendered HTML (`web/templates/`, `web/routers/pages.py`) plus `/api/v1/*` (`web/routers/api.py`). Nav in `web/templates/base.html`: Catalog `/browse`, Search `/search`, Lens `/lens`, Research `/collections`, Citations `/network`, Structure `/structure`, Officials `/officials`, Admin `/admin`. Masthead brand: `中国政策档案` / `Governance Archive`.
- **Run:** Documented local command is `uvicorn web.app:app --reload --port 8001` (CLAUDE.md). README also shows `--port 8000`. App is SQLite-only, opens `SQLITE_PATH` or `documents.db` read-only (`file:…?mode=ro` in `web/database.py`). This skill **does not** use 8001 or `documents.db`.
- **Drive:** No Playwright/Cypress suite in-repo. Search/browse/lens forms are GET — curl of the same query string **is** the user path. Chrome (`google-chrome --headless=new`) and Playwright MCP are optional for screenshots/ARIA. Prefer `form[action="/search"]`, `input[name="q"]`, `a[href^="/document/"]`, `#doc-body`, nav `a[href="/search"]` — the templates have almost no ARIA names or `data-testid`.
- **Observe:** HTML bodies, `/api/v1/stats` and `/api/v1/search` JSON, Chrome screenshots, uvicorn log. Fixture SQLite via `sqlite3`/`python3` for row checks. Evidence directory named below.
- **Isolate:** Bind `127.0.0.1` + `VERIFY_PORT` (default **18001**) + `SQLITE_PATH` to a per-run fixture. Two runs need two ports and two `VERIFY_RUN_DIR`s. Never attach to a shared `--port 8001` process. Officials (`officials.db`) is optional; missing file → page still renders.

## Launch

From the repo root, with `python3 -m uvicorn` available (`pip install -r requirements.txt`; `PyYAML` is imported by `web.services.ontology` and is required to boot pages).

```bash
export VERIFY_PORT=18001          # not 8001
export VERIFY_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
.cursor/skills/verify-chinagovernance/helpers/launch.sh
```

What it does:

1. Writes scratch under `/tmp/verify-chinagovernance-$VERIFY_RUN_ID/` (fixture DB, pid, log).
2. Seeds a **verification-only** SQLite via `helpers/seed_fixture.py` (`_verify_scaffold.kind = VERIFICATION_SCAFFOLDING_NOT_PRODUCTION`). Six synthetic documents. Refuses `SQLITE_PATH` ending in `documents.db`.
3. Starts `python3 -m uvicorn web.app:app --host 127.0.0.1 --port $VERIFY_PORT` **without** `--reload` (reload forks a watcher; cleanup kills only the pid we started).
4. Waits until `GET $VERIFY_BASE_URL/api/v1/stats` returns HTTP 200.

Ready signal: helper prints `ready: GET http://127.0.0.1:18001/api/v1/stats -> 200` and writes `VERIFY_EVIDENCE_DIR/launch.txt`. Meta for later helpers: `$VERIFY_RUN_DIR/meta.env`.

Teardown: `helpers/cleanup.sh` (not `pkill uvicorn`).

If port 18001 is taken, set `VERIFY_PORT` to a free port and rerun. If boot fails, read `$VERIFY_RUN_DIR/uvicorn.log`, then run cleanup.

## Doctor

Run first whenever anything looks off, and immediately after launch:

```bash
# same VERIFY_* as launch (or source $VERIFY_RUN_DIR/meta.env)
.cursor/skills/verify-chinagovernance/helpers/doctor.sh
```

Checks (read-only):

1. Pid in `$VERIFY_RUN_DIR/uvicorn.pid` is alive.
2. `/proc/$pid/cmdline` contains `uvicorn` and `$VERIFY_PORT`.
3. `ss` shows that port owned by **that pid**.
4. Process `SQLITE_PATH` exists, is **not** `documents.db`, and has `_verify_scaffold` marker `VERIFICATION_SCAFFOLDING_NOT_PRODUCTION`.
5. `GET /api/v1/stats` → 200 with `total >= 1` (homepage divides `with_body / total`).
6. `GET /` → 200 and contains `中国政策档案` and `HOLDINGS`.

Pass line: `DOCTOR_OK http://127.0.0.1:18001`. Do not drive an instance doctor rejects.

## Drive

Harness: **curl + Chrome** (Playwright MCP if the agent has it). Helpers: `helpers/drive-search.sh`. Forms are GET; do not invent POST bodies or hit test-only endpoints (there are none).

Stable handles from this repo (not coordinates):

| Handle | Where |
| --- | --- |
| `a[href="/search"]` | `base.html` subnav, label `Search` |
| `a[href="/browse"]` | subnav `Catalog` |
| `a[href="/lens"]` | subnav `Lens` |
| `form[action="/search"]` `input[name="q"]` | `search.html` and homepage `index.html` |
| `input[name="exclude_news"]` value `1` | search checkbox |
| `button` text `Search` | search submit |
| `a[href^="/document/"]` | result rows |
| `#doc-body` | `document.html` full text |
| `form[action="/lens"]` `input[name="q"][type="search"]` | Policy Lens |
| `button` text `Open dossier` | lens submit |
| `form[action="/browse"]` `select[name="site"]` `button` Apply | catalog filters |
| Masthead `中国政策档案` | identity that this is our app |

Fixture Search query: `人工智能`. Expected hits (ids 1–4): State Council AI+ opinions, Guangdong implementation, Shenzhen action plan, Xinhua commentary. Negative control: 住房保障 (id 5) must not appear. `exclude_news=1` drops Xinhua → 3 hits.

```bash
.cursor/skills/verify-chinagovernance/helpers/drive-search.sh
```

Playwright MCP (optional, same URLs/selectors): navigate to `$VERIFY_BASE_URL/search`, fill `input[name="q"]` with `人工智能`, click `Search`, snapshot, click `a[href="/document/1"]`. Save ARIA/screenshot into `VERIFY_EVIDENCE_DIR`. Do not drive `https://www.chinagovernance.com`.

Other features: follow [`features/`](features/) recipes; only Search has a helper today.

## Evidence

Directory (survives cleanup):

```
.cursor/skills/verify-chinagovernance/evidence/<VERIFY_RUN_ID>/
```

Launch sets `VERIFY_EVIDENCE_DIR` to that path. Cleanup **must not** delete it.

Proof standards:

- Exercise the real user path (`GET /search?q=…` is the form in `search.html`, not an internal setter).
- Capture the **action** (empty `/search` HTML, submitted query URL) **and** the **resulting state** (hits page, then `/document/{id}`).
- Verify side effects alongside the visible page: `/api/v1/search?q=人工智能` total and ids must match the HTML; fixture table `_verify_scaffold` documents expected ids. Mocks only at production boundaries — here the boundary **is** the fixture SQLite; do not stub FastAPI routes.
- Do not invent corpus counts. Stats in evidence come from the fixture or a query you actually ran. Fixture `GET /api/v1/stats` total is **6**.
- Screenshots (`search-hits.png`, `document-1.png`) when Chrome is present; HTML dumps are sufficient if Chrome is not.

`drive-search.sh` writes: `search-empty.html`, `search-hits.html`, `search-exclude-news.html`, `document-1.html`, `api-search.json`, `drive-search.txt`, optional PNGs.

## Cleanup

```bash
.cursor/skills/verify-chinagovernance/helpers/cleanup.sh
```

Kills **only** the pid in `$VERIFY_RUN_DIR/uvicorn.pid` (`TERM`, then `KILL` if needed). Removes `$VERIFY_RUN_DIR` (fixture DB, log, pid). Leaves `$VERIFY_EVIDENCE_DIR`. Never `pkill uvicorn`, never `killall`, never `fuser -k`. After cleanup, confirm evidence still exists at the named directory.

After a **failed** iteration, run cleanup before the next launch so 18001 is not stranded.

## Helpers

All under `.cursor/skills/verify-chinagovernance/helpers/`. Executable. Invocation is in Launch / Doctor / Drive / Cleanup above.

| Script | Role |
| --- | --- |
| `seed_fixture.py --out PATH` | Write the six-row fixture DB |
| `launch.sh` | Seed + uvicorn + ready wait |
| `doctor.sh` | Read-only instance check |
| `drive-search.sh` | Search feature proof |
| `cleanup.sh` | Stop pid we started; keep evidence |

`common.sh` is sourced, not executed.

## Maintenance

When templates, routes, or search ranking change, update this skill and the feature map via `/maintain-verification-skill`.
