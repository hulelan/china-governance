# Policy Lens

Policy Lens builds a one-page dossier for a topic from **title** matches: attention-over-time, admin level, issuers, genres, and most-cited anchors; or shows one document’s inbound/outbound citations.

## Sub-features

- `lens-empty` shows `/lens` with suggested topic chips (`人工智能`, `算力`, …).
- `lens-topic` submits `q` and renders `Policy Lens · 政策透镜` with a records count and “Attention over time”.
- `lens-empty-query` for a title that matches nothing shows `No document titles match`.
- `lens-doc` opens `?doc=<id>` (Focus record, Cites outbound, Cited by inbound) and links `Full record & body text` to `/document/{id}`.

## How to get to it (user POV)

- Choose `Lens` in the subnav (`a[href="/lens"]`).
- Type a topic in `form[action="/lens"]` `input[name="q"][type="search"]` and choose `Open dossier`.
- Choose a suggestion chip (`a[href="/lens?q=人工智能"]` etc.).
- From a topic dossier, choose an anchor title (`a[href="/lens?doc=<id>"]`).

## Driving it with curl + Chrome

Preconditions:

- Doctor reports `DOCTOR_OK`.
- Fixture titles for `人工智能` are ids 1–4; id 1 has `citation_rank=6`.

- **Empty state.** Run `curl -sS "$VERIFY_BASE_URL/lens" -o "$VERIFY_EVIDENCE_DIR/lens-empty.html"`. Contains `Start a dossier`, `Open dossier`, and a chip `人工智能`.
- **Open topic.** Type `人工智能` and Open dossier. Run `curl -sS --get --data-urlencode "q=人工智能" "$VERIFY_BASE_URL/lens" -o "$VERIFY_EVIDENCE_DIR/lens-ai.html"`. Contains `Policy Lens`, `records · title match`, `Attention over time`, and the State Council title.
- **Miss.** Run `curl -sS --get --data-urlencode "q=不存在的议题XYZ" "$VERIFY_BASE_URL/lens"`. Contains `No document titles match`.
- **Document neighborhood.** Run `curl -sS "$VERIFY_BASE_URL/lens?doc=1" -o "$VERIFY_EVIDENCE_DIR/lens-doc-1.html"`. Contains `Focus record`, `ACC. 1`, `Cited by`, and `Full record & body text`. Guangdong/Shenzhen rows cite id 1.
- **Proof.** HTML dumps plus optional screenshot of `/lens?q=人工智能` showing the teal `Policy Lens` bar.

## Gotchas

- Lens matches **titles only** (`title LIKE '%q%'`). A body-only mention will not appear. Do not prove Lens by searching body text.
- Results are cached in-process for one hour (`web/services/lens.py`). After reseeding, restart uvicorn (cleanup + launch) or the dossier can be stale.
- `?doc=` and `?q=` are exclusive in the handler: a numeric `doc` wins and `topic` is skipped.
- Suggestion chips are hard-coded in `pages.py` (`人工智能`, `算力`, `数据要素`, …). Fixture only guarantees hits for `人工智能` and `石油` (oil collection, not a default chip).
