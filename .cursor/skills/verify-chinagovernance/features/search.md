# Search

Search lets a user type a Chinese title, 文号, or keyword, see a counted result list with title/publisher/snippet, optionally hide news/media sources, and open a matching catalog record.

## Sub-features

- `search-empty` shows the GET form on `/search` with no result table.
- `search-submit` runs a title/body query and lists matching documents with a `results for "<q>"` count.
- `search-exclude-news` checks `exclude_news=1` and drops News & Media `site_key`s (ontology node `media`).
- `search-open-hit` follows `a[href^="/document/"]` to the record page.
- `search-from-home` submits the same `form[action="/search"]` from `/`.

## How to get to it (user POV)

- Choose `Search` in the teal subnav (`a[href="/search"]`).
- Submit the homepage search field (`form[action="/search"]` `input[name="q"]` on `/`).
- Open `/search?q=<query>` directly (the form is `method="get"`).
- Check `Exclude news` (`input[name="exclude_news"]` value `1`) and submit `Search`.

## Driving it with curl + Chrome

Preconditions:

- Doctor reports `DOCTOR_OK` for this run’s `VERIFY_BASE_URL`.
- Fixture includes ids 1–4 with `人工智能` in the title and id 5 `住房保障` without it.
- Evidence directory is `$VERIFY_EVIDENCE_DIR`.

- **Open form.** Go to Search. Run `curl -sS "$VERIFY_BASE_URL/search" -o "$VERIFY_EVIDENCE_DIR/search-empty.html"`. The HTML contains `form action="/search"`, `input` `name="q"`, and no `results for` line.
- **Submit query.** Type `人工智能` and choose `Search`. Run `curl -sS --get --data-urlencode "q=人工智能" "$VERIFY_BASE_URL/search" -o "$VERIFY_EVIDENCE_DIR/search-hits.html"`. The page contains `4 results for "人工智能"`, links `/document/1` `/document/2` `/document/3` `/document/4`, and does **not** contain `住房保障`.
- **Exclude news.** Check Exclude news and search again. Run `curl -sS --get --data-urlencode "q=人工智能" --data-urlencode "exclude_news=1" "$VERIFY_BASE_URL/search" -o "$VERIFY_EVIDENCE_DIR/search-exclude-news.html"`. Count is `3 results`; `新华时评` is absent; `/document/1` remains.
- **Open a hit.** Choose the State Council title. Run `curl -sS "$VERIFY_BASE_URL/document/1" -o "$VERIFY_EVIDENCE_DIR/document-1.html"`. The page shows `ACC. 1`, the Chinese title, and `#doc-body` with `人工智能赋能千行百业`.
- **Corroborate.** Run `curl -sS --get --data-urlencode "q=人工智能" "$VERIFY_BASE_URL/api/v1/search" -o "$VERIFY_EVIDENCE_DIR/api-search.json"`. JSON `total` is `4` and result ids are `{1,2,3,4}`.
- **Screenshot (optional).** Run `google-chrome --headless=new --no-sandbox --window-size=1280,900 --screenshot="$VERIFY_EVIDENCE_DIR/search-hits.png" "$VERIFY_BASE_URL/search?q=人工智能"`. Masthead must read `中国政策档案`.
- **One-shot helper.** Run `.cursor/skills/verify-chinagovernance/helpers/drive-search.sh`. Exit 0 writes `drive-search.txt` and the files above.

## Gotchas

- Queries shorter than 3 characters skip the FTS trigram path and use LIKE; the fixture has no FTS index, so **all** searches use LIKE. That is expected locally and is still the real `search_documents()` user path.
- `exclude_news` uses the source-type ontology (`data/source_ontology.yaml`). Fixture media key must be `xinhua` (under `media_state`), not an unmapped key that falls into `other`.
- Homepage `/` also has a search form; proving only `/search` does not prove the homepage entry. Record the entry point used.
- Production `https://www.chinagovernance.com/search` is 401 without basic auth. Do not treat that 401 as an app bug and do not embed credentials.
- Do not quote live corpus hit counts in the proof. The fixture total for `人工智能` is 4.
- Headless Chrome on a cloud VM often writes D-Bus errors to `chrome.log`; that is not a failed screenshot if the PNG exists and shows `中国政策档案`.
