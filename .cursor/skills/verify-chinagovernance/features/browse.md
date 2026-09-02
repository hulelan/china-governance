# Browse / catalog

The catalog lists every document in a ruled table with site, type, AI score, citation rank, and date, and lets a user narrow the list with GET filters (source type, site, year, importance, document type, AI relevance, 文号, sort).

## Sub-features

- `browse-all` shows `/browse` with a total count and rows linking to `/document/{id}`.
- `browse-site` restricts to one `site` (e.g. `gov`).
- `browse-exclude-news` sets `source_node=!media` (sidebar “Exclude news & media”).
- `browse-year` sets `year=2025` (sidebar year `<select>` values 2026 down to 2015).
- `browse-open` follows a title link into the document record.

## How to get to it (user POV)

- Choose `Catalog` in the subnav (`a[href="/browse"]`).
- From the homepage, choose a fonds name (`a[href="/browse?site=<site_key>"]`).
- Submit the sidebar `form[action="/browse"]` (`select[name="site"]`, `select[name="source_node"]`, `select[name="year"]`, button `Apply`).

## Driving it with curl + Chrome

Preconditions:

- Doctor reports `DOCTOR_OK`.
- Fixture has 6 documents across `gov`, `gd`, `sz`, `xinhua`.

- **Open catalog.** Choose Catalog. Run `curl -sS "$VERIFY_BASE_URL/browse" -o "$VERIFY_EVIDENCE_DIR/browse-all.html"`. The page contains `6 documents`, `form action="/browse"`, `select name="site"`, and `href="/document/1"`.
- **Filter by site.** Choose site State Council (`gov`) and Apply. Run `curl -sS "$VERIFY_BASE_URL/browse?site=gov" -o "$VERIFY_EVIDENCE_DIR/browse-gov.html"`. Count line contains `2 documents` (filtered); both AI opinions and housing ids 1 and 5; no `粤府`.
- **Exclude news.** Choose “Exclude news & media” (`source_node=!media`). Run `curl -sS "$VERIFY_BASE_URL/browse?source_node=!media" -o "$VERIFY_EVIDENCE_DIR/browse-nonews.html"`. Total is `5 documents`; `新华时评` is absent.
- **Open a row.** Choose a title. Run `curl -sS "$VERIFY_BASE_URL/document/1" -o "$VERIFY_EVIDENCE_DIR/document-1.html"`. `ACC. 1` is visible.
- **Proof.** Save the HTML dumps. Optional Chrome screenshot of `/browse` showing `HOLDINGS` in the masthead.

## Gotchas

- The total line only appends `(filtered)` when `site`, `category`, or `year` is set — `source_node` alone does **not** add that suffix (`browse.html`). Assert the numeric total, not the word `filtered`.
- Sort `citation_rank` uses SQL `NULLS LAST` (`web/services/documents.py`). Default sort is `date_written DESC`; use that unless you have confirmed SQLite accepts `NULLS LAST`.
- Year options are hard-coded `range(2026, 2014, -1)`. A fixture doc in 2024 is selectable; there is no 2023 option.
- Empty fixture would make homepage `with_body / total` divide by zero; doctor already requires `total >= 1`.
