# QA: repairing the cross-site id-collision corruption

**Date:** 2026-10-07 · **Status:** script + tests ready, NOT yet applied (the
nightly held `/tmp/china-governance-daily-sync.lock.d` throughout this work).

Follow-up to `qa-gkmlpt-sync-diff.md` (commit `5d872b2`), which closed the hole:
`store_gkmlpt_document` and `base.store_document` upserted
`ON CONFLICT(id) DO UPDATE SET body_text_cn=..., raw_html_path=...` without
checking `site_key`, so one site's crawl overwrote another site's body. This
memo is about the damage already in the corpus.

Deliverables: `scripts/repair_site_collisions.py`,
`tests/test_repair_site_collisions.py` (18 cases).

## 1. The footprint predicate, and why it is trustworthy

```sql
raw_html_path != '' AND instr(raw_html_path, '/' || site_key || '/') = 0
```

**261 rows.** The predicate is sound because `save_raw_html`
(`crawlers/base.py:521`) is unconditionally `raw_html/<site_key>/<id>.html` for
*every* crawler — there is no legitimate cross-directory case. Verified against
the live corpus: every site has own-dir ≫ other-dir, with exactly one
instructive exception — `npc` is 0 own-dir / 81 other-dir, because
`crawlers/npc.py:272` writes `"raw_html_path": ""` and 30,989 of its 31,070 rows
have both body and path empty. So all 81 `npc` rows holding a path are foreign.

**The predicate is on `raw_html_path`, never on `url`** — which is what keeps it
clean. `ifeng` (tech./www.), `sz_invest` (fgw./www.sz.gov.cn), `mof`, `mofcom`
(fms./www.) and `stic` legitimately span hosts, and gkmlpt list items
legitimately carry outbound `url`s to gov.cn / mp.weixin.qq.com / Xinhua. None
of those are URL facts the predicate can see. `tests/test_repair_site_collisions.py`
asserts this directly (`test_predicate_ignores_legitimately_cross_host_rows`,
`test_url_is_irrelevant_to_the_predicate`).

## 2. 21 of the 261 are NOT corrupt — the url-identity exception

`crawlers/gov.py:150` (and `:428`) resolves a document id by URL before
assigning a new one:

```python
existing = conn.execute(
    "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''", (url,)
).fetchone()
if existing and existing[1]:
    continue                      # already have body — skip
doc_id = existing[0] if existing else next_id(conn)
```

So when a Shenzhen district row is a *pointer* at a `www.gov.cn` article, the
`gov` crawler **adopts that row's id** and writes the correct text for that URL
under `raw_html/gov/<id>.html`. The path mismatch is real; the body is not
corrupt. Confirmed by content — body matches title in all 21:

| id | site | ←dir | title | body opens |
|---|---|---|---|---|
| 7846793 | szpsq | gov | 国务院办公厅关于印发2020年政务公开工作要点的通知 | 国务院办公厅关于印发 2020年政务公开工作要点的通知 国办发〔2020〕17号 |
| 10543556 | szft | gov | 国务院办公厅关于印发全国一体化政务大数据体系建设指南的通知 | 国务院办公厅关于印发 全国一体化政务大数据体系建设指南的通知 |
| 12697867 | yunfu | gov | 中华人民共和国药品管理法实施条例 | 中华人民共和国国务院令 第828号 |

Distribution: `szpsq` 9, `szft` 5, `szns` 2, `yunfu` 2, `mofcom` 1, `szdp` 1,
`szlhq` 1. **Clearing these would destroy correct content**, so the script keeps
them and only records the decision.

The discriminator is *directional*: `foreign_dir` must be the real owner of the
row's `url` host (`HOST_OWNER = {"www.gov.cn": "gov"}`). The reverse case — a row
**owned by `gov`** whose path points into a gkmlpt dir — is a true clobber,
because a Shenzhen bureau does not own gov.cn URLs. All 13 are unambiguous:

```
12650953 gov<-szeb   T=中共中央 国务院印发《关于实施自由贸易试验区提升战略的意见》
                     B=为提升我市普通高中综合素质评价信息管理平台应用推广服务质量，现公开招标…
12651754 gov<-ga     T=国务院办公厅关于同意建立国务院推进贸易高质量发展部际联席会议制度的函
                     B=2025年，在市委、市政府和上级公安机关领导下，全市公安机关坚持…
```

## 3. Per-site repair table

**240 true clobbers / 21 keeps.** Repair is always **clear**, never "write a
guessed body" — the foreign body and path are deleted and `title`, `url`,
`date_published`, `document_number` and everything else are left alone (the
upsert only ever touched body / path / crawl_timestamp). Clearing is also what
brings the body *back*: crawlers gate on an empty body (`gov.py`
`if existing and existing[1]: continue`) and `gkmlpt.backfill_bodies` selects
`WHERE body_text_cn = ''`, so a cleared row is re-fetched by its own owner.

Reachability was probed from **the droplet** (its NYC IP is the operative
vantage), 37 requests at 1 req/s, byte-checked, following redirects: **27 of 37
owner URLs returned a real page** (9.5KB–237KB; no 200-byte redirect stubs).

| site | n | repair action | evidence |
|---|---|---|---|
| `npc` | 81 | **clear** (no refetch) | metadata-only BY DESIGN: `crawlers/npc.py:269` `"body_text_cn": ""  # Body requires Chinese IP access`; 30,989/31,070 rows natively have empty body+path. Empty *is* its correct state. |
| `ndrc` | 19 | **recrawl** `python3 -m crawlers.ndrc` | probe `www.ndrc.gov.cn` 200, 27,154 B |
| `zhongshan` | 17 | **recrawl** `gkmlpt --backfill-bodies --site zhongshan` | probe `www.zs.gov.cn` 200, 129,133 B; all 17 urls contain `gkmlpt` |
| `gov` | 13 | **recrawl** `python3 -m crawlers.gov` | probe `www.gov.cn` 200, 28,682 B |
| `most` | 12 | **recrawl** `python3 -m crawlers.most` | probe 200, 26,504 B |
| `sh` | 12 | **recrawl** `python3 -m crawlers.shanghai` | probe 200, 13,826 B |
| `bj` | 8 | **recrawl** `python3 -m crawlers.beijing` | probe 200, 27,167 B |
| `xinhua` | 8 | **recrawl** `python3 -m crawlers.xinhua` | probe `www.news.cn` 200, 22,872 B |
| `cq` | 7 | **clear and flag** | probe `www.cq.gov.cn` **timed out (45 s)** from NYC — the datacenter-IP blackhole pattern. But `daily_sync.sh:230` still runs `chongqing` weekly and the Aug-2026 backfill recovered 584 rows, so this is flagged, not declared dead. |
| `miit` | 7 | **recrawl** `python3 -m crawlers.miit` | probe 200, 9,552 B |
| `suzhou` | 6 | **recrawl** `python3 -m crawlers.suzhou` | probe 200, 51,985 B |
| `heyuan` | 5 | 2 **recrawl** (`gkmlpt --backfill-bodies --site heyuan`) + 3 **clear, stays empty** | 3 urls are `www.gov.cn` list-item stubs; `backfill_bodies` deliberately skips non-gkmlpt urls, so empty is their native state |
| `mofcom` | 5 | 4 **recrawl** `python3 -m crawlers.mofcom` + 1 **keep** | probe 200, 40,438 B |
| `szft` | 5 | **keep** | url-identity (§2) |
| `jsrd` | 4 | **recrawl** `govcms --site jsrd` (江苏省人大, `crawlers/govcms.py:126`) | probe `www.jsrd.gov.cn` 200, 29,111 B |
| `sz_invest` | 4 | **recrawl** `python3 -m crawlers.sz_invest` | curl failed with `OpenSSL error:0A000132 bad ecpoint` — a **TLS-handshake artifact of curl, not a block**; `fgw.sz.gov.cn` is crawled nightly |
| `cac` | 3 | **recrawl** `python3 -m crawlers.cac` | probe 200, 13,418 B |
| `wuhan` | 3 | **recrawl** `python3 -m crawlers.wuhan` | probe 200, 133,721 B |
| `zj` | 3 | **clear and flag — unreachable** | `daily_sync.sh:272` "Skipping zhejiang (weekly probe … blocked from NYC)", 0 new rows in 11 nights; probe `kjt.zj.gov.cn` failed |
| `hlj` | 2 | **recrawl** (heilongjiang) | probe 200, 21,589 B |
| `ipc_court` | 2 | **recrawl** `python3 -m crawlers.ipc_court` | probe 200, 31,657 B |
| `mee` | 2 | **recrawl** `python3 -m crawlers.mee` | probe 200, 62,729 B |
| `szns`, `yunfu`, `szdp`, `szlhq` | 2+2+1+1 | **keep** | url-identity (§2) |
| `swj`, `ga`, `hrss`, `jtys`, `mzj`, `sf`, `szlh` | 2+1+1+1+1+1+1 | **recrawl** `gkmlpt --backfill-bodies --site <k>` | all in `gkmlpt.SITES`, none in `KNOWN_BROKEN`; curl's `bad ecpoint` is the same TLS artifact as `sz_invest` (sibling hosts `audit.`/`stic.sz.gov.cn` probed 200) |
| `audit`, `gz`, `shanwei`, `stic` | 1 each | **recrawl** `gkmlpt --backfill-bodies --site <k>` | probes 200 (34,738 / 36,261 / 28,813 / 236,953 B) |
| `guancha`, `ifeng`, `nda`, `samr` | 1 each | **recrawl** `python3 -m crawlers.<k>` | probes 200 (65,676 / 57,897 / 13,948 / 57,109 B) |
| `nanjing`, `njd_qinhuai` | 1+1 | **recrawl** `govcms --site nanjing` / `--site njd_qinhuai` (both live in `crawlers/govcms.py`, not their own modules) | probes 200 (34,472 / 62,926 B) |

Totals: `clear_owner_recrawl` 125 · `clear_by_design` 81 (npc) ·
`clear_gkmlpt_backfill` 31 · `keep_url_identity` 21 · `clear_link_stub` 3.

## 4. How big is the real corruption? ~250 rows

261 was described as a lower bound, and it is — but it is **also** an over-count
(21 url-identity false positives). Both corrections were measured.

**Signal 1** (path mismatch): 261 matched → **240 true clobbers**.

**Signal 2** (independent): `document_changes` rows claiming `change_type =
'added'` whose `site_key` disagrees with the document's actual owner — the
"claimed a document it never added" signature from `qa-gkmlpt-sync-diff.md` §4.

```sql
SELECT COUNT(DISTINCT dc.document_id)
  FROM document_changes dc JOIN documents d ON d.id = dc.document_id
 WHERE dc.change_type = 'added' AND dc.site_key != d.site_key;
```

**230 distinct documents** (15,127 change rows), of which **217 are already in
the 261**. The 13 outside split as:

* **8 currently body-corrupt with an empty `raw_html_path`** — exactly the blind
  spot: the overwriting crawler saved no HTML, so signal 1 cannot see them
  (`gd` ×3, `huizhou` ×2, `sf` ×2, `szpsq` ×1; e.g. `4436455` 广东省…人工智能赋能
  千行百业若干措施 with a 208-char body).
* **5 already healed** (`gov`, `mee`, `ndrc` ×3) — own path, full-length body
  matching the title; a later owner re-crawl refilled them.

**Bounding the blind cell.** Signal 2 is narrow: `document_changes` is written
almost only by the ~8 gkmlpt sites that call `_record_change` (`zjj` 24,724,
`sz` 10,547, `stic` 8,481, `jiangmen`, `huizhou`, `gd`, `gz`, `zhuhai`, + tiny
tails), so it only sees clobbers whose *overwriting* crawler is one of those.
207 of the 261 (79%) had such a clobberer. Signal 2 found 8 path-less victims
inside that 79% window; scaling, ≈ 8 / 0.79 ≈ **10 path-less victims** corpus-wide.

> **Estimate: ≈ 250 rows were corrupted and are still corrupt** — 240 provable
> by path mismatch + ≈ 10 invisible to it (no clobberer path), plus ≈ 5 that were
> corrupted and have since self-healed.

A naive Lincoln–Petersen on the overlap gives 261 × 230 / 217 ≈ **277**, but
that inflates: it counts the 21 url-identity rows and the 5 healed rows as
corruption, and the two signals are not independent (both are driven by the same
gkmlpt-dominated mechanism). 250 is the defensible figure; 277 is the ceiling.

**Blast radius** (unchanged, re-measured read-only): max `citation_rank` among
victims **63.5**, and **0** rows above 100 — no top-ranked instrument is
affected. **464** `citations` edges have a victim as `source_id` (extracted from
the wrong document's text) and 105 as `target_id`. **19** victims are
`diffusion_events.anchor_id` (`gov` 4, `ndrc` 2, `mee` 1 — the rest are
non-document rows) and **25** are `source_id`. *(Note: 19 anchors, not 7 — the
query is `anchor_id IN (victims)` against the live table.)*

## 5. Re-derivation after the repair — order matters

Clearing bodies invalidates everything downstream of body text. Run in exactly
this order (it is the nightly's own Phase 2b → 2c → 2d order, so **letting one
full `daily_sync.sh` run is the supported path**; the explicit sequence is for
doing it immediately):

```bash
# 0. the repair itself (after the nightly lock clears)
python3 scripts/repair_site_collisions.py --dry-run     # read-only, confirm the plan
python3 scripts/repair_site_collisions.py --apply

# 1. refill the bodies that CAN come back (optional but do it before re-deriving,
#    so the derived layers are built from refilled text, not from holes)
python3 -m crawlers.gkmlpt --backfill-bodies            # the 31 gkmlpt rows
python3 -m crawlers.ndrc ; python3 -m crawlers.gov ; python3 -m crawlers.most
python3 -m crawlers.shanghai ; python3 -m crawlers.beijing ; python3 -m crawlers.miit
# …and the rest of the per-site commands in §3

# 2. citations FIRST — the 464 bad edges only disappear here
python3 scripts/rnd/citations/extract_citations.py      # ~5-6 min
# 3. then scores (citation_rank/algo_doc_type/ai_relevance read citations + bodies)
python3 scripts/compute_scores.py
python3 scripts/compute_topics.py
# 4. issuers, then identity (reads issuers + algo_doc_type, so it runs last in 2b)
python3 scripts/rnd/classification/issuer_parser.py
python3 scripts/build_doc_identity.py --force
python3 scripts/build_instrument_succession.py
# 5. stats + the tracker layer (diffusion reads doc_identity + citations)
python3 scripts/build_site_stats.py                     # also rebuilds doc_inbound, corpus_stats
python3 scripts/rnd/analysis/build_diffusion_events.py --write
python3 scripts/build_tracker_rollup.py
# 6. validate, then publish
python3 scripts/validate_cascades.py
systemctl restart chinagovernance                       # clears the 1h per-worker cache
```

Search indexes:

* `doc_search` (trigram) is **trigger-maintained**, so it self-corrects on the
  `UPDATE` — nothing to do.
* `doc_search_seg` (BM25) is **incremental by rowid and skips already-indexed
  ids** (`build_search_index_seg.py:111`), and it is a contentless FTS5 table so
  a row cannot be deleted without the original segmented text. **The 240 cleared
  docs therefore keep stale tokens from the foreign body** until a one-time
  `python3 scripts/build_search_index_seg.py --rebuild` (~1 h). Bounded impact
  (240 docs may surface for foreign terms); schedule it, don't block on it.

## 6. What the script does and does not do

* `--dry-run` opens the DB read-only (`?mode=ro`), prints the plan + a 20-row
  sample, writes nothing — safe during the nightly.
* `--apply` refuses to run while `/tmp/china-governance-daily-sync.lock.d`
  exists, unless `--force`.
* Batched commits (200) + PASSIVE checkpoint every 5 batches + a final
  `wal_checkpoint(TRUNCATE)`. An `UPDATE` touching `body_text_cn` rewrites the
  row's overflow pages, so 261 of them in one transaction is the
  `compute_scores.py` mistake (a multi-GB WAL the app's reader pins).
* Idempotent: clearing sets `raw_html_path = ''`, so the predicate stops
  selecting the row; the 21 keeps stay selected and upsert their audit row.
* Every decision is recorded in
  `collision_repairs(doc_id, old_site_dir, action, when_utc, site_key,
  old_body_len, old_path, note)`.
* Files under `raw_html/` are **not** touched — the saved HTML belongs to the
  crawler that wrote it, and for the url-identity rows it is the right document.

## 7. Not done here

* **The stale `"added"` rows in `document_changes`** (15,127 rows / 230 docs
  claiming adds that never happened) are left in place. They are now a useful
  forensic record; pruning them would delete signal 2.
* **The 8 path-less victims** found only by signal 2 are *not* repaired — the
  predicate cannot identify them individually with confidence, and `document_changes`
  cross-site "added" rows have false positives (the 5 healed ones). A targeted
  follow-up could clear the subset whose body is short AND whose title/body
  jurisdictions disagree.
* `doc_search_seg --rebuild` (§5).
