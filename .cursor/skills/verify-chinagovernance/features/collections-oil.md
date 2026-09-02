# Collections (oil)

The oil collection is a topical watch: every fixture/live document whose title (or reserve-body query) matches petroleum terms, overlaid with curated annotations from `data/collections/oil.json`. `/collections` redirects to `/collections/oil`.

## Sub-features

- `collections-redirect` sends `/collections` to `/collections/oil`.
- `collections-oil` renders the standalone oil page (`石油 · Oil & Petroleum Policy Watch`) with a document list (`#list`, `#shown`, `#total`).
- `collections-filter` uses in-page controls (`#q`, `#nonews`, `#scope`) — client-side, not a new server round-trip.
- `collections-unknown` for an unknown slug returns `Unknown collection`.

## How to get to it (user POV)

- Choose `Research` in the subnav (`a[href="/collections"]`), which redirects to oil.
- Open `/collections/oil` directly.
- From the Research dropdown, choose `Collections`.

## Driving it with curl + Chrome

Preconditions:

- Doctor reports `DOCTOR_OK`.
- Fixture id 6 is `广东省石油储备管理办法` with `date_published=2026-03-02` (collection query requires `date_published >= 2026-02-01`).

- **Redirect.** Run `curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' "$VERIFY_BASE_URL/collections"`. HTTP `307` (or `302`) to `/collections/oil`.
- **Open oil.** Run `curl -sS "$VERIFY_BASE_URL/collections/oil" -o "$VERIFY_EVIDENCE_DIR/collections-oil.html"`. Contains `石油`, `Oil & Petroleum Policy Watch`, `id="list"`, and the JSON payload includes `广东省石油储备管理办法`.
- **Unknown.** Run `curl -sS -o /dev/null -w '%{http_code}' "$VERIFY_BASE_URL/collections/not-a-real-slug"`. HTTP `404`.
- **Proof.** HTML dump of `/collections/oil`. Chrome is useful here because the list is filled by on-page JS from `data_json`; confirm `#shown` is not `0` after load.

## Gotchas

- This template does **not** extend `base.html`. There is no `中国政策档案` masthead on the oil page. Identity is the `石油 · Oil & Petroleum Policy Watch` title.
- The live SQL also requires `date_published >= 2026-02-01`. Older petroleum titles in a future fixture will be invisible.
- Body reserve terms use FTS `doc_search` when present, else LIKE. The verification fixture has no FTS; title `石油储备` is enough.
- Payload is cached 30 minutes in-process. Restart the launched uvicorn after changing the fixture.
- Curated annotation overlay is keyed by **URL**. Fixture URL `https://www.gd.gov.cn/verify/oil-reserve` will not match production annotation URLs; the doc still appears as unannotated (`auto-classified`). That is success.
