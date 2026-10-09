# Pre-registration: what the next full rebuild must do

*Written 2026-10-08, BEFORE the rebuild, so the numbers cannot be chosen after the fact. The
droplet's in-flight nightly pulled at `f86a0cf`, so its Phase 2b runs the OLD resolver; every
prediction below applies to the first rebuild that runs at `bc2126a` or later. Registering this
after the rebuild would be worthless, which is the only reason it is a separate file.*

## Baseline, measured read-only on the live DB 2026-10-08 18:3x UTC

| quantity | value |
|---|---|
| `citations` total edges | 585,471 |
| resolved (`target_id NOT NULL`) | 310,136 |
| resolution | **52.97%** |
| `doc_inbound` rows (docs with inbound) | 41,179 |
| 城乡规划法 (`12685270`) edges / distinct citers | 2,201 / 1,950 |
| `diffusion_events` | 45,524 |
| `doc_identity.localized_of` set | 2,014 |
| `doc_identity.genre='implementing'` | 17,883 |
| unclassified documents | 15,512 (draining, 2 errors in 8,200) |

Note the baseline drift: the `localized_of` experiment ran from **2,075**, the live table holds
**2,014**. Predictions are therefore stated as **deltas**, not absolutes — an absolute target can
be met or missed by corpus growth alone, which is not what is being tested.

## Prediction 1 — the org-stub gate makes resolution FALL

`extract_citations.py` gained an org-stub containment gate (`org_only_exact=True`): a reference
that is only an organization's name must match exactly, not by containment. This **removes** wrong
edges, so:

- resolved edges **fall by ~4,570** (310,136 → ≈305,566), resolution **52.97% → ≈52.2%**;
- a **rise** falsifies it — the gate cannot create edges;
- a fall **beyond ~4,600** means something else moved too and must be found before the number is
  quoted anywhere.

This matters because every previous resolution change in this project was an increase, and a
decrease is the correct outcome of a precision fix. The temptation to read it as a regression is
exactly why it is written down first.

## Prediction 2 — the identity rebuild moves two fields and nothing else

`build_doc_identity.py --write --force` at the `KNOWN_LOCALITIES` seed (54 → 381 names,
`87eec6c`):

- `localized_of` **+1,336** (2,014 → ≈3,350), with **0 removed and 0 retargeted**;
- `genre='implementing'` **+1,336** by the same edges (17,883 → ≈19,219);
- the dominant beneficiary is the **`npc` 地方法规 tier, ~1,287 of the 1,336**;
- 无锡市 2 → ~73 while **苏州市 stays at ~83** — cities that already worked must not move;
- `diffusion_events` rebuilds **byte-identical** (measured on the experimental build);
- `validate_cascades.py` returns **15/15, line for line**.

Any tracker or cascade figure that moves contradicts this and needs an explanation before the
rebuild is accepted.

## Prediction 3 — the body ledger's first seed

`scripts/body_ledger.py --seed` (after `git pull`; no network, reads saved HTML):

- ~**8,369 rows capped**: `anti_bot_stub` 3,791 · `empty_extraction` 2,512 · `image_only` 1,745 ·
  `pdf_only` 321;
- ~**11,573 `html_missing`** left at `attempts=0` deliberately;
- `npc`'s 31,070 bodiless rows **excluded** (`SEED_SKIP_SITES`) — they are bodiless by design and
  would be 61% of the ledger.

Then, on the first nightly that runs with it: Beijing's body-fetch loop drops ~760 fetches/night.
**Expect the saving to appear as coverage before it appears as time** — Beijing is currently killed
at 2,840/6,821 items, so a freed budget first buys it the `gfxwj` section it has never reached. A
Phase 1 wall-clock that does *not* fall on night one is therefore consistent with the prediction,
and the thing to check instead is whether `beijing` reached a new section.

## Prediction 4 — the PBC backfill must RAISE resolution, and in a named place

`crawlers/pbc.py` now walks the easysite pager (`af874c7`, verified independently 2026-10-08:
section 3581332 → 22 pages, 144957 → 6, both confirmed from the live `tagname` attributes). The
next nightly git-pulls it and will store ~510 new documents in ~10 min, inside `run_crawler`'s cap.

- `pbc` goes **31 → ~541** documents, oldest **1993-01-14** (currently 2025-12).
- Each arrives with **title + 文号 + date**, which is exactly what `TitleMatcher` indexes, so the
  FOLLOWING citations rebuild should **raise** resolved edges. This is the opposite direction from
  Prediction 1, and the two land in different nightlies, so do not read them together.
- **The named place:** 《支付结算办法》(银发〔1997〕393号) and 《储蓄管理条例》implementing rules
  are confirmed present on page 6 (I read both bodies). The unresolved monetary head measured
  2026-10-08 is 人民币银行结算账户管理办法 **22 citers**, 非金融机构支付服务管理办法 **18**,
  商业银行服务价格管理办法 **14**, 金融租赁公司管理办法 **11**. If PBC's archive contains them,
  those specific `target_ref` groups should drop out of the unresolved list. **If resolution rises
  but none of those four resolve, the gain came from somewhere else and the demand list was wrong
  about what PBC publishes** — which is the more interesting outcome and must not be glossed.
- **~360 of the 541 are attachment-only** (body = the PDF's filename). They are now labelled
  `附件：…` with URLs in `attachments_json`, so expect `pbc` body coverage to look POOR
  (~181/541 with real inline text) and do not read that as a crawler regression. It is the honest
  number replacing a fake one — those 360 previously would have counted as "has a body".

## Prediction 6 — the instance-title denylist removes ~391 citers, in named places

`extract_citations.py` now drops titles that can never be a resolution target from **every** tier
(`drop_instance_titles=True`), not just from containment as the org gate does — because for these an
exact match is equally wrong. Measured before the change:

| denylisted shape | held titles | citers today |
|---|---|---|
| bare `政府工作报告` | 25 docs / 25 instrument_ids | **283** |
| `*决定书` | 152 | 107 (房屋征收补偿决定书 alone: 39 docs, 95) |
| `*告知书` | 40 | 1 |
| `*通知书` | 101 | 0 |

- resolved edges should **fall by roughly 391**, and `政府工作报告` + `房屋征收补偿决定书` should
  **disappear from `doc_inbound` entirely**;
- a **rise** falsifies it — the gate cannot create edges;
- a fall **far beyond ~400** means the endings caught an instrument, and the named test to look at
  is `test_real_instruments_are_kept` (国务院…的决定, …的通知, …的意见 must all survive; the `书` is
  load-bearing);
- `深圳市政府工作报告` and other jurisdiction-qualified titles must still resolve — only the **bare**
  generic form is denied.

This lands in the same rebuild as Prediction 1 (the org-stub gate, ~4,570 edges), so **the two
falls add**: expect resolution to drop by roughly 4,960 edges in total, not 4,570. Do not read
either number alone.

## Prediction 7 — the body-tail trim removes ~195 RESOLVED citation edges

Measured by `trim_body_tails.py --dry-run --no-reextract` on the live DB, 2026-10-09 (read-only).
The trim's headline justification is not tidiness: a 相关链接 / 上一篇 tail holds **other
documents' titles**, which the citation extractor reads as references. Quantified:

> Outbound citation edges whose reference text occurs **ONLY** inside the tail:
> **368 edges on 319 documents** — formal 5 resolved / 7 unresolved, llm 106 / 60,
> named 84 / 106.

- **~195 resolved edges should disappear** (5 + 106 + 84) at the citations rebuild **after** the
  trim is applied, plus ~173 unresolved refs leaving the queue.
- These are **spurious by construction** — the reference exists nowhere in the document's real
  text — so their removal is a precision gain, not a loss, and it is the third fall in a row.
- **A rise falsifies it.** Trimming cannot create references.

### Reading the three falls together

P1 (org-stub gate, ~4,570), P6 (instance-title denylist, ~391) and P7 (tail trim, ~195) are all
**precision fixes that remove edges**, and if the window in `write-window-plan.md` is used they land
in **one** rebuild:

| fix | resolved edges removed |
|---|---|
| P1 org-stub containment gate | ~4,570 |
| P6 instance-title denylist | ~391 |
| P7 body-tail trim | ~195 |
| **expected total** | **≈5,156** |

Against a 310,136 baseline that is resolution **52.97% → ≈52.1%**. **Every previous resolution
change in this project was an increase**, so the single most likely misreading of the next rebuild
is to see ~5,100 fewer resolved edges and call it a regression. It is three precision fixes landing
together. P4 (the PBC backfill, which should *raise* resolution) lands in the same window and
partially offsets them, so **the net number is not interpretable at all** — only the per-fix checks
below are.

## Prediction 5 — how much of the instrument-pooling gap is staleness

Measured on the live (stale) `doc_identity`, 2026-10-08, before the rebuild
(`docs/working/qa-resolver-deferred-patterns.md` §3). Families of identically-titled documents:

| | families | documents |
|---|---|---|
| pooled to one `instrument_id` | 3,423 | 9,052 |
| not pooled, copies span > 400 d (by design) | 8,123 | 24,019 |
| **not pooled, copies within 400 d (should have)** | **11,891** | **28,225** |
| …of those, containing a doc with NO identity row | 2,180 | — |

Worst cases have a span of **0 days**: 中共中央关于制定…第十五个五年规划的建议 (2 docs, 209 citers),
国务院关于印发全面推进依法行政实施纲要的通知 (2 docs, 198), 中办印发《通知》… (3 docs, 253).

- **If staleness:** the within-400d figure falls materially, driven by the 2,180 families that
  currently contain an identity-less document.
- **If a real pooling defect:** it stays near 11,891 / 28,225, and then it is worth real work —
  28,225 documents is 8% of the corpus, and `instrument_id` is what `citation_rank`, the diffusion
  anchors and the tracker's anchor-diversity columns all pool on.
- **Either way the >400d bucket should barely move**, since edition separation is intended.

Re-run exactly: the `fam` view in `docs/working/qa-resolver-deferred-patterns.md` §3.

## Open follow-up (logged, not done)

The **31 pre-existing `pbc` rows keep their node-id dates**. The 19-digit node id is the CMS
*creation* stamp and can precede publication (measured: `2026012314163359926` is listed as
2026-01-26, not 01-23), so a few of the 31 are off by days. The crawler skips by URL, so they will
not self-correct. `scripts/redate_from_html.py --site pbc` is the existing route (it maps
`site_key` → the crawler's own dater) once a `pbc` dater is registered in `SITE_DATERS`. Judged
below the bar for now: 31 documents, error of days, no analysis depends on it.

## How to check

```bash
# after the rebuild, on the droplet
sqlite3 "file:documents.db?mode=ro" "
  SELECT COUNT(*), SUM(target_id IS NOT NULL),
         ROUND(100.0*SUM(target_id IS NOT NULL)/COUNT(*),2) FROM citations;
  SELECT COUNT(*) FROM doc_identity WHERE localized_of IS NOT NULL AND localized_of!='';
  SELECT COUNT(*) FROM doc_identity WHERE genre='implementing';
  SELECT COUNT(*) FROM diffusion_events;"
python3 scripts/validate_cascades.py        # expect 15/15
python3 scripts/body_ledger.py --stats
```
