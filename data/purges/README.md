# data/purges

`officials.json`: senior officials removed since the 18th Party Congress (November 2012),
per person at deputy-national rank (副国级) and above, a separate CMC-member tier, and
counts only for the ranks below. Memo: `docs/research/purges-deputy-national.md`.

## Rebuild and verify

    python3 scripts/rnd/purges/build_purges.py --ssh root@104.236.88.45          # verify + rewrite
    python3 scripts/rnd/purges/build_purges.py --ssh root@104.236.88.45 --check  # verify only
    python3 scripts/rnd/purges/build_purges.py --db documents.db                 # with a local DB
    python3 -m pytest tests/test_purges_verifier.py

The script re-reads every cited document (read-only) and requires each quote to be an
exact substring of its `title` or `body_text_cn`. It exits 1 and writes nothing if any
quote fails. Fields marked (derived) below are written by the script; do not hand-edit them.

`scripts/rnd/purges/tally_announcements.py` produces the one own-tally row in `ladder`.

## Schema

Top level: `meta`, `persons`, `cc_expulsions`, `ladder`, `institutional_changes`, `ties`,
`ties_meta`, `web_urls_to_ingest`, `summary` (derived).

### Evidence item (used everywhere)

| label | fields | counted as verified |
|---|---|---|
| `corpus` | `doc_id`, `quote`, optional `note`; (derived) `verified`, `where` (`title`/`body`), `site`, `url`, `doc_date`, `doc_title` | yes, when `verified` is true |
| `web, not in corpus` | `url`, `fetched` (true = page opened and the key sentence read; false = URL and wording from a search summary only), `note` | never |
| `not in corpus` | `note` (the fact is recalled from general knowledge) | never |
| `own tally` | `script`, `note` | n/a |
| `officials.db` | `note` (a row of the officials database; not quote-verified) | never |

### `meta`

`as_of`, `scope`, `rank_ladder` (rank, English gloss, definition: 正国级, 副国级, CMC member,
正部级, 副部级, 正厅级, 副厅级, 县处级, 乡科级), `removal_types` (a, b, c, d),
`evidence_labels`, `corpus_verified_rule`, `coverage_gaps`.

### `persons[]`

| field | meaning |
|---|---|
| `id`, `name_cn`, `name_en` | |
| `tier` | `正国级`, `副国级` or `CMC member`. A CMC member who was not a vice-chair is its own tier and is NOT counted as 副国级; one who was also a State Councilor is 副国级 through that post (`also_cmc_member: true`). |
| `rank_at_removal` | `rank`, `held` (in office / retired), `posts` |
| `highest_rank_held` | `rank`, `posts` |
| `rank_evidence[]` | evidence items for the rank |
| `removal_type` | `a` disciplinary or corruption case formally announced; `b` removed with no stated reason; `c` demotion; `d` foreign or Hong Kong media only |
| `flags[]`, `flag_note` | `removed_before_18th_congress`, `investigation_only_no_disposal_yet` |
| `status` | one line |
| `stated_grounds` | `zh` (official wording), `en`, `evidence[]` |
| `events[]` | `date` (YYYY-MM-DD, or YYYY-MM with `date_precision: "month"`), `action`, `detail_en`, optional `sentence`, `establishes_removal` (bool), `evidence[]` |
| `successions[]` | `post`, `successor`, `date`, `evidence[]` |
| `officials_db` | `present`, `cc_congresses`, `is_politburo`, `is_psc` |
| `corpus_verified` (derived) | true when at least one event with `establishes_removal` has verified corpus evidence |
| `events_with_corpus_evidence` (derived) | "n of m" |

`action` values: `investigation_announced`, `suspended`, `removed_from_post`, `demoted`,
`expelled`, `expulsion_confirmed_by_plenum`, `resignation_accepted`, `prosecution_reported`,
`indicted`, `sentenced`, `conviction_reported`, `died`, `named_in_party_resolution`,
`named_in_party_journal`, `named_in_party_media`, `named_by_ccdi_secretary`.

### `cc_expulsions[]`

One row per Central Committee plenum: `plenum`, `date`, `congress`, `expelled[]` (null when
the list was not retrieved), `other[]`, `evidence[]`; (derived, 20th CC only) `membership`
(name to `full` / `alternate` / `not found`) from name-list documents 900207119 and 900207120.

### `ladder[]`

`rank_span`, `measure`, `period`, `value`, `kind` (`official_aggregate` or `own_tally`),
`evidence[]`, optional `note`. An official aggregate and an own tally are never summed.
Official aggregates use different measures (case opened, publicly announced, disciplined)
and different rank spans (中管干部, 省部级及以上); each row states its own.

### `institutional_changes[]`

`date` (YYYY-MM), `system`, `change`, `evidence[]`. A hand-selected list of eight items,
used only for the timing table in `summary.timing`. Not a census of reorganisations.

### `ties[]`, `ties_meta`

`removed[]`, `named[]`, `tie_type`, `body`, `period`, `corpus_counts`, `evidence[]`.
A tie is a co-presence fact (same body at the same time, or the same official list),
not a relationship. `ties_meta` records how each named person was resolved, the three
unresolved names, and the officials.db caveat.

### `summary` (derived)

`headline` (total at 副国级+ since the congress, by removal type, corpus-verified count,
flagged pre-congress names, CMC tier), `cells` (tier x removal type, with names),
`cc_expulsions_by_plenum`, `cc_totals`, `timing` (24-month windows and base rate).
