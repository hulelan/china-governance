# Document detail

A document record shows issuer, date, instrument type, English/Chinese titles, optional summary, the Chinese body (`#doc-body`), catalog fields, and citation lists, with `ACC. {id}` in the header.

## Sub-features

- `doc-header` renders `Record · {publisher}` and `ACC. {id}`, 文号, titles.
- `doc-body` fills `#doc-body` when `body_text_cn` is present; otherwise a dashed empty state with the origin URL.
- `doc-cites` lists outbound citations with optional `a[href="/document/{resolved.id}"]`.
- `doc-cited-by` lists inbound citations.
- `doc-404` returns HTML `Not found` for an unknown id.

## How to get to it (user POV)

- From Search or Catalog, choose a title (`a[href="/document/{id}"]`).
- From Lens, choose `Full record & body text →` (`a[href="/document/{id}"]`).
- Open `/document/{id}` directly.

## Driving it with curl + Chrome

Preconditions:

- Doctor reports `DOCTOR_OK`.
- Fixture id 1 is the State Council AI+ opinions with body text; id 2 cites id 1 via `国发〔2025〕11号`.

- **Open record.** Run `curl -sS "$VERIFY_BASE_URL/document/1" -o "$VERIFY_EVIDENCE_DIR/document-1.html"`. Contains `ACC. 1`, `国发〔2025〕11号`, `id="doc-body"`, and `人工智能赋能千行百业`.
- **Inbound cites.** Same file contains `Cited by` and the Guangdong title (id 2).
- **Outbound from the child.** Run `curl -sS "$VERIFY_BASE_URL/document/2"`. Contains `国发〔2025〕11号` and a link `/document/1`.
- **Missing id.** Run `curl -sS -o /dev/null -w '%{http_code}' "$VERIFY_BASE_URL/document/999999"`. HTTP `404` and body `Not found`.
- **Proof.** HTML dump plus optional screenshot whose header shows `ACC. 1` and masthead `中国政策档案`.

## Gotchas

- `get_document` is `SELECT *`; extra columns must exist on the fixture or the template raises. The seeder includes `title_en`, `summary_en`, `algo_doc_type`, `citation_rank`, `ai_relevance`, `topics`.
- Inline cite marks (`.cite-mark`) only wrap refs that appear as substrings in `body_text_cn`. Fixture id 2’s body includes `国发〔2025〕11号`.
- Compare view `/compare/{id}` is a separate page (parsed vs raw HTML) and is not this feature.
- Do not use `/raw_html/` as proof of the document page; that mount only exists if a `raw_html/` directory is present and is disallowed in production `robots.txt`.
