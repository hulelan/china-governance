# China Governance Archive verification map

This directory is the maintained source for verifying user-facing behavior of the Governance Archive web app (`web.app:app`, live at chinagovernance.com behind nginx basic auth). Read this index before driving the app, then use the matching feature file as the recipe.

## Baseline preconditions

- Launch via `.cursor/skills/verify-chinagovernance/helpers/launch.sh` so the app is at `http://127.0.0.1:$VERIFY_PORT` (default **18001**, never the shared `--port 8001` instance).
- `SQLITE_PATH` is the per-run fixture from `helpers/seed_fixture.py`, not `documents.db`. Doctor must report `_verify_scaffold` kind `VERIFICATION_SCAFFOLDING_NOT_PRODUCTION`.
- Seeded titles include `国务院关于深入实施"人工智能+"行动的意见` (id 1) and a housing negative control (id 5, `住房保障`). Search query for proofs: `人工智能`.
- Run `helpers/doctor.sh` and require `DOCTOR_OK` for this URL and fixture path.
- Never drive an instance this run did not start. Never fetch `https://www.chinagovernance.com` as the drive target (401 without credentials; do not hunt creds).
- Put helper scripts on PATH only by calling them from `.cursor/skills/verify-chinagovernance/helpers/`.

## Driving conventions

- Start every recipe from the baseline unless its preconditions say otherwise.
- Prefer route paths, `name=` on GET form fields, and `id=` from templates (`#doc-body`) over CSS position or click coordinates. These templates rarely expose ARIA names.
- Treat every command as literal. Keep `人工智能` and `exclude_news=1` unchanged.
- HTTP drive: curl of the same GET URLs the forms submit (`form[action="/search"] method="get"`).
- Browser drive (optional): Playwright MCP or `google-chrome --headless=new --screenshot=…`.
- Cleanup removes `$VERIFY_RUN_DIR` only. Proof artifacts stay in `.cursor/skills/verify-chinagovernance/evidence/<VERIFY_RUN_ID>/`.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- UI proof: HTML dump of the submitted URL plus (when Chrome is available) a screenshot that shows `中国政策档案` in the masthead.
- Mutation: this app is read-only against SQLite (`?mode=ro`). There is no write side effect to check except the URL/query string and rendered rows. Corroborate HTML totals with `GET /api/v1/search` or `GET /api/v1/stats` on the **same** fixture.
- Record the feature ID and entry point with every artifact.
- Do not report production corpus counts. Fixture `total` is 6 documents / 4 fonds unless you changed the seeder.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with curl + Chrome` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Search](./search.md) covers the catalog search form, result list, exclude-news filter, and opening a hit. **This is the feature proved in the generator run.**
- [Browse / catalog](./browse.md) covers `/browse` filters (site, exclude-news source node, year) and the document table.
- [Policy Lens](./lens.md) covers `/lens` topic dossiers (`?q=`) and document citation neighborhood (`?doc=`).
- [Document detail](./document-detail.md) covers `/document/{id}` record header, `#doc-body`, and citation sidebar.
- [Collections (oil)](./collections-oil.md) covers `/collections/oil` topical watch (live title query + curated annotations).
