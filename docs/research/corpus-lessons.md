# What the replications teach us about the corpus: fixes and additions, prioritized

*Methods memo, 2026-10-06. The nine replications and the consistency review were as diagnostic
of the instrument as of China. This records what they exposed about the corpus, ranked by how
much each would raise the ceiling on the findings, with the study that surfaced it. Companion
to `findings-synthesis.md` (what we found) and `consistency-review.md` (where the findings
disagreed). Items are queued in `docs/working/backlog-2026-09.md`.*

---

## The short version

The corpus's **content** is strong and its **identity fields** are weak. Level, instrument,
genre, date, and issuer are each inferred or per-site rather than per-document, and every
analytic workaround this session (the anchor pooling, the implementing flag, the npc exclusion,
the hand-built genre subsets, the date-stamped site drops) was patching one of those five. Fixing
them is a smaller job than any single replication and would make the next nine cleaner.

---

## Part A. Fixes to the corpus

### A1. Level is per-site; documents are not (highest priority)
**Exposed by:** the diffusion atlas (819 "central" anchors were local 人大 regulations), the
citation-network study (~29k stale `citations.*_level` rows), the consistency review ("central"
means a different universe per memo).
**The flaw:** `sites.admin_level` stamps one level on every document a site hosts. The
national-laws site filed ~28,000 provincial and municipal regulations as central; department
and bureau sites blur provincial and municipal.
**Fix:** a per-document `admin_level` derived from publisher and 文号 (the issuer parser
already yields the lead issuer), kept alongside the site level. Drop or nightly-recompute the
citation level columns from it. Every level-share series in the memos becomes comparable.

### A2. No canonical instrument identity
**Exposed by:** every diffusion study (the anchor-identity gotcha: Xinhua 受权发布 vs gov.cn vs
ministry copies; 政府信息公开条例 on 18 sites in 20 copies), the resolver fixes (mirrors
competing for the same citations).
**The flaw:** authority, inbound citations, and cascades attach to a *copy*, and the
auto-matcher pools mirrors by normalized title as a workaround.
**Fix:** an `instrument_id` grouping all promulgations of one text (title-core plus 文号 plus
date window), with one canonical representative (promulgation genre, highest level). Attach
`citation_rank` and cascades to the instrument, not the copy.

### A3. Genre cannot separate an instrument from talk about an instrument
**Exposed by:** the fidelity study (an implementing-instrument subset had to be hand-built), the
mention-leakage finding (AI+ events 33 → 103, of which 75 were readouts), the citation-network
study (explainers as pool representatives).
**The flaw:** `algo_doc_type` has "other" as the largest central genre since 2020 (15k docs),
and news / readout / explainer / Q&A are not reliably distinguished from promulgations.
**Fix:** a genre classifier with promulgation, implementing instrument, explainer, readout, and
news as first-class values. The `source_implementing` flag then becomes a derived field, not a
patch. This one field would have prevented the mention leakage outright.

### A4. Dates fail three ways
**Exposed by:** a staged SQL pass that silently binned most rows into 1970 (`date_written` is
integer in some rows and text in others), the industrial-policy study (74 sites, 27,915 docs
with ≥70% of dates in 2026, i.e. crawl-stamped, dropped from the analysis), and the CAST crawl
(65 dates grabbed from signature lines until the `<meta PubDate>` fix).
**Fix:** normalize `date_written` to one type; prefer page metadata (`PubDate`, `og:*`) over
body scans in every crawler; flag crawl-stamped sites with a `date_quality` so trend studies
exclude them by default rather than by hand.

### A5. Issuer identity
**Exposed by:** the joint-issuance study (the naive proxy found 852 joint documents; the parser
found 13,004) and its 粤办 phantom-pair bug (a registry problem).
**Fix:** promote `doc_issuers` to the issuer field of record (it is nightly now) and maintain a
canonical agency registry with aliases, so coalition analysis and A1's per-document level share
one source of truth.

### A6. Resolution is honest now, and coverage-bound
**Exposed by:** the resolver fixes (27% of edges were proxy targets; after fixing, ~17.8k wrong
proxies are left unresolved and resolution sits near 50%), the August backfill (resolution %
flat despite +16k resolved, because new documents bring their own dangling references).
**Fix:** treat the unresolved references as the crawl queue they are
(`citation-crawl-queue.csv`). Ingesting cited-but-missing instruments is the only lever that
raises resolution; matching improvements are exhausted.

### A7. Body coverage in the department tier
**Exposed by:** both fidelity studies (pairs dropped for missing bodies; department tier at
60% vs 84% overall).
**Fix:** a targeted body backfill for department sites (the GD-dept container fix pattern).

---

## Part B. Additions the replications call for

### B1. A second deep province (the most important addition)
**Why:** the volume's most reframing results, province-before-city (68-76%), the province as
translation layer, cities copying the province in 92.8% of chains, rest on Guangdong, which
supplies 95% of the nested chains because it is the only province crawled to district depth.
Until Jiangsu, Zhejiang, or Sichuan is crawled to the same depth, these are Guangdong findings
presented as China findings. A crawl decision, not a method problem.

### B2. Hunt the bottom-up channel deliberately
**Why:** the through-line (center designates, localities echo, reverse flow nearly invisible)
is partly real and partly because published documents do not carry upward signals. Sources that
would partially see them: 人大 and 政协 proposals and 调研报告, government research-office
reports, and the center's acknowledgment of local models in the 典型经验 / 经验推广 / 示范 lexicon.
If generalization still looks absent with these in the corpus, the finding hardens; if not, we
have found the channel.

### B3. A successor-instrument detector
**Why:** our pilots-that-scale rate (0.4-1.2%) versus Wang & Yang's 53.9% is partly our
title-family detection missing rollouts. A detector for "same topic, same title core, 试点
dropped, later date, national issuer" would say whether the gap is real or measurement.

### B4. Join cheap external data where it unlocks a causal test
**Why:** provincial GDP from the statistical yearbooks is public and small. Joined to the
fixed-site panel it lets us run Wang & Yang's site-selection finding descriptively, the one part
of their causal core the corpus can approach.

### B5. Encode the validation as a nightly regression test
**Why:** the consistency review found build drift, and my own resolver fix introduced a
regression that only the review caught. The known cascades (boost GD 52d / JS 82d / BJ 116d;
城乡规划法 at ~2,141 citations; AI+ ~30 implementing events) should be asserted after every
nightly rebuild and fail loudly. One-off audit becomes structure.

### B6. Report raw inbound alongside `citation_rank`
**Why:** the 3x central weighting still shapes the top-30 (19/30 overlap with the raw corrected
ranking). Both should be visible wherever rank is used.

### B7. Use the tracker as an instrument
**Why:** the per-area weekly cascade series is a "policy tempo" measurement no paper has. A few
months of it is a dataset in its own right.

---

## Sequencing

A1 through A5 are one coordinated data-model pass (per-document level, instrument identity,
genre classifier, date audit, issuer registry) and should be done together, since the fields
depend on each other. B5 should land first because it protects everything else. B1 is the
crawl priority and depends on the Hong Kong vantage only if the chosen province is
datacenter-blocked (Jiangsu is not). B2 and B3 are new crawlers and a detector; B4 is a small
external join; B6 and B7 are reporting changes.
