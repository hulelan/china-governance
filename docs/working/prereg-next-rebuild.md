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
