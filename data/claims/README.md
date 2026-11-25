# data/claims

A place for CLAIMS extracted from the overseas claims-only sources (finmedia tier 7,
`crawlers/claims_outlets.py`: RFA, VOA, BBC, DW, 看中国, 大纪元, 新唐人, 联合早报,
端传媒), and from any other stored document whose content is an outlet's assertion
rather than an official act. **No extraction has been done yet**; this file fixes the
shape so that hand- and model-extracted claims land in one comparable format.

## Why claims are kept separate

These outlets report elite politics (investigations, detentions, patron/protégé ties,
"who is next") often ahead of, or instead of, any announcement. Their reliability is
uneven and differs by outlet. A claim is therefore always **attributed to the outlet
that made it** ("大纪元 reported that ..."), never stated as fact, never counted as an
announcement, and never joined to a government-document count. The corpus enforces the
separation structurally: `sites.admin_level='foreign_media'`, ontology leaf
`media_foreign_claims` (`claims_only: true`, `web.services.ontology.claims_only_sites()`),
`relation` tag `claims=outlet_attributed`, and no discourse speaker type
(`tests/test_claims_sources.py`).

## Files

One JSON file per extraction batch: `data/claims/<batch>.json` = `{"meta": {...},
"claims": [...]}`. `meta` holds `batch`, `created`, `extracted_by`, `scope` (the query or
document set the batch covers) and `notes`.

## Claim record

| field | type | required | meaning |
|---|---|---|---|
| `claim_id` | string | yes | stable id, `<batch>-<n>` |
| `outlet` | string | yes | `site_key` of the publishing outlet (`epochtimes`, `rfa`, ...) |
| `doc_id` | int | yes | `documents.id` of the stored article the claim is read from |
| `url` | string | yes | the article URL as stored |
| `doc_date` | `YYYY-MM-DD` | yes | the article's `date_published` |
| `claim_date` | `YYYY-MM-DD` or `YYYY-MM` or null | no | when the claimed event happened, if the article says |
| `speaker` | string | yes | who asserts it inside the article: `outlet` (the outlet's own voice), or the named person / description (`知情人士`, `消息人士`, `北京学者`, `前官员 X`) |
| `attribution_chain` | list of strings | yes | outlet first, then each relay, e.g. `["看中国", "海外推特账号 X", "知情人士"]`; `["新唐人"]` when the outlet speaks for itself |
| `sourcing` | enum | yes | `named` (a named, identifiable source), `anonymous` (unnamed insiders), `official_relay` (restating an official announcement, e.g. a CCDI notice), `other_outlet` (citing another outlet), `analysis` (the outlet's or a commentator's inference) |
| `claim_type` | enum | yes | see below |
| `persons` | list of objects | yes | every person the claim is about: `{"name_cn": "...", "role": "subject" / "patron" / "protege" / "associate" / "accuser", "post_at_claim": "..."}` |
| `claim_zh` | string | yes | **verbatim** quote carrying the claim; MUST be an exact substring of the stored `title` or `body_text_cn` of `doc_id` (verified the way `scripts/rnd/purges/build_purges.py` verifies its quotes) |
| `claim_en` | string | no | a translation of `claim_zh`, labelled as such; never a paraphrase that adds content |
| `hedge` | enum | yes | how the article itself qualifies it: `asserted`, `reported` (据报 / 传), `rumored` (传闻 / 网传 / 疑), `speculative` (或 / 可能 / 恐) |
| `corroboration` | object | no | filled later, never at extraction: `{"status": "unchecked" / "confirmed" / "contradicted" / "unresolved", "official_doc_id": int or null, "official_date": "YYYY-MM-DD" or null, "other_outlets": [site_key, ...], "note": "..."}`. `confirmed` requires an official corpus document (a CCDI / 新华社 announcement); another overseas outlet repeating it is `other_outlets`, not confirmation |
| `lead_days` | int or null | no | derived: `official_date - doc_date` when confirmed (positive = the outlet was first) |
| `confidence` | enum | yes | the EXTRACTOR's confidence that the record reads the article correctly (`high` / `medium` / `low`), not confidence in the claim |
| `extracted_by` | string | yes | `hand:<initials>` or `model:<model id>@<prompt version>` |
| `extracted_at` | `YYYY-MM-DD` | yes | |
| `note` | string | no | |

### `claim_type`

| value | meaning |
|---|---|
| `investigated` | the person is (or is about to be) under 审查调查 / 留置 / 立案 |
| `detained` | the person is detained, missing, or under control (失联, 被带走, 控制) |
| `removed` | removed, demoted, retired early, or posts stripped, with no announcement |
| `next_to_fall` | the person is predicted to fall, or is "in trouble" (有大麻烦, 前景堪忧) |
| `patron_protege` | an asserted patron, protégé, secretary, or clique (系, 帮) tie |
| `factional` | a factional struggle, power contest or coalition claim not reducible to one tie |
| `appointment` | an asserted or forecast appointment or promotion |
| `health` | the health, death or incapacity of a leader |
| `policy_internal` | an internal decision, meeting or document claimed but not published |
| `military` | PLA / CMC personnel or command claims (a subtype kept separate because the 2023- purges are its own series) |
| `other` | anything else; say what in `note` |

## Rules

- **Store, do not adjudicate.** An extraction records what the outlet says. Whether it was
  true goes in `corroboration`, filled by a separate pass against official documents.
- **One claim per record.** An article saying X is investigated AND is Y's protégé is two
  records sharing `doc_id`.
- **Quotes are verbatim.** `claim_zh` is copied from the stored text, never translated back,
  normalised, or stitched from two passages. A claim with no quotable sentence is not recorded.
- **Count claims by outlet, not in aggregate.** The outlets differ; a pooled "share of claims
  later confirmed" mixes a public broadcaster with movement-affiliated outlets and means little.
