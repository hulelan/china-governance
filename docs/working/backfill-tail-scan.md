# Backfill Tail Scan (investigation-only, 2026-08-24)

Read-only analysis of `docs/working/citation-crawl-queue.csv` (23,776 ranked
missing-doc refs) against the LIVE droplet DB. Goal: where does remaining
backfill value live, and where has it run out. **No code changed.**

## Method
- Aggregated queue demand by `inferred_institution`, excluding already-handled
  (Beijing, Jiangsu, MOF, Chongqing, Shanghai, Shenzhen, Guangdong, Zhongshan,
  Guangzhou, Fujian).
- **Reality-checked** "absent" vs "present-but-unresolved" by exporting all
  278,716 corpus titles + 68,582 non-empty `document_number`s and normalizing
  both sides (fold `《》〔〕`/brackets/dashes/whitespace, strip `中华人民共和国`,
  fold zero-padding on 文号). Then spot-probed ~20 top refs with `title LIKE`.
- Bounded reachability curls from the droplet.

## Headline findings
- The `coverage_status` field is NOISY and directional only. `have`≠present:
  a `have` ref means "we crawl that institution," not that the cited doc is in
  the corpus. Confirmed by probing — most `have` top refs are genuinely absent.
- **75.3% of documents have an EMPTY `document_number`.** So number-form (文号)
  citations structurally cannot resolve against most target docs even when the
  doc IS in the corpus. This is the single biggest hidden lever (below).
- After removing handled + datacenter-blocked + resolver near-misses, the
  reachable/we-crawl-it tail is a **long thin tail of OLD (2005–2015) docs**,
  each cited a handful of times — low yield per crawl-hour.

## Reachability probes (droplet, browser UA)
| Target | HTTP | Verdict |
|---|---|---|
| mnr.gov.cn (自然资源部) | 000 | BLOCKED (datacenter IP) |
| mohurd.gov.cn (住建部) | 000 | BLOCKED |
| nhc.gov.cn (卫健委) | 412 | WAF-blocked |
| mohrss.gov.cn (人社部) | **200** | REACHABLE — queue's "blocked" label is WRONG |
| shandong.gov.cn | 200 | homepage OK (policy sections typically WAF) |
| hlj.gov.cn | 502 | blocked/erroring (already 2,277 docs in corpus) |
| nx.gov.cn (宁夏) | 301 | reachable-ish, thin corpus |
| 12371.cn (共产党员网) | **200** | REACHABLE — we already have the `dangyuan` crawler |

## RANKED shortlist — worth backfilling (reachable + we crawl + real headroom)

> The cheapest, highest-value item is not a crawl at all — see Lever (a) first.

1. **Guangdong cities — Zhuhai / Jiangmen / Jieyang / Shanwei / Shaoguan**
   — combined genuinely-absent demand ≈ **2,284** (Zhuhai 939, Jiangmen 514,
   Jieyang 481, Shanwei 180, Shaoguan 170). Crawler: `gkmlpt` (all live, NOT in
   KNOWN_BROKEN; Shantou IS broken — skip). Reachable. **Mechanism: scattered
   sub-section / delisted, NOT a pagination cap** — corpus already spans
   2001–2026 for each, so a deeper re-sync recovers only scattered docs.
   Verdict: **MEDIUM** — a targeted `--sync` is cheap but per-doc yield is low.

2. **State Council + State Council General Office (国务院/国办)** — absent ≈
   **2,210** (SC 1,315 + SCGO 895). Crawler: `gov`. Reachable. Mechanism:
   **uncrawled historical 国发/国办发 archive** (missing docs are 2002–2010
   国发〔YYYY〕N号). Verdict: **MEDIUM** *iff* a 国发 archive section can be added
   cheaply; otherwise it's a long thin tail.

3. **Central Party docs via 12371 (中共中央/中办)** — demand **2,708** (474 refs),
   never crawled as a class. Crawler + site already exist (`dangyuan`/12371.cn,
   reachable). Verdict: **MEDIUM** — worth a targeted probe; this is the party
   lever's tractable slice.

4. **Central ministry old-doc tails — Tax / NDRC / MOE / MOFCOM / MIIT / MOST /
   PBC / MEE / MOT** — each 178–1,450 absent (Tax 1,450, NDRC 1,162, MOE 539,
   MOFCOM 457, MIIT 293, MOST 275, NHSA 264, PBC 207, MEE 185, MOT 178). All
   reachable, all already crawled. Mechanism: long thin tail of OLD docs in
   archive sections the crawler doesn't reach. Verdict: **LOW / diminishing** —
   do opportunistically, not as a campaign.

## NOT worth it (blocked, delisted, or by-design metadata)
- **MNR 自然资源部 (463), MOHURD 住建部 (430), NHC 卫健委 (327)** — datacenter-IP
  BLOCKED from the droplet (000/412). ~1,220 demand stranded; needs a
  residential fetch vantage, not a crawl change.
- **Province portals — Shandong (431), Heilongjiang (402), Ningxia/Xizang/Hunan
  (thin)** — policy sections WAF/datacenter-block from NYC (HLJ 502; Shandong
  homepage 200 but deep sections block). Low reachable yield.
- **npc / national laws (1,927, `law-db`)** — famous laws (道路交通安全法 etc.)
  already present as **metadata-only stubs by design**; this is a body-backfill
  question, not a crawl gap.
- **`unknown` institution bucket (30,305 demand, 7,975 refs)** — a scattered tail
  of GB national standards, COVID-era temporary notices, cross-agency circulars,
  MOJ 律师 rules, etc. No single tractable target; largely unattributable.
- **Already handled** + **Huizhou (1,339)/Yangjiang (257)** (datacenter-blocked).
- **MOHRSS 人社部 (398)** — REACHABLE but no crawler exists; a *new* small
  crawler for ~400 demand. Borderline; note but don't prioritize.

## The two non-crawl levers (quantified)

**(a) Resolver near-misses — BEST cheap lever.** Docs already in the corpus that
fail to resolve only on punctuation / zero-padding / empty `document_number`:
- Measured floor (exact normalized match): **733 refs / 2,576 demand** present
  but unresolved. With substring title matching it rises to **~1,040 refs /
  ~3,800 demand**.
- Concrete proof: ref `财库〔2022〕4号` (demand 130) IS in the corpus as
  `财库〔2022〕004号` (gov + mof) — a pure **zero-padding** miss. `财库〔2022〕3号`
  (66) same. The current resolver folds brackets but NOT zero-padding.
- Because **75% of docs have empty `document_number`**, the true near-miss
  universe is larger still — realistic **~4,000–6,000 demand** recoverable by
  (i) zero-pad folding on 文号, (ii) number→title matching, (iii) fuller title
  punctuation normalization. **No crawling required.** Highest ROI.

**(b) 中共X委 Party-committee family — cited but never crawled as a class.**
- Total **931 refs / 4,319 demand**. Breakdown:
  - 中共中央 / 中办 (中发/中办发): **2,708** (474 refs) — tractable via existing
    `dangyuan`/12371 crawler (reachable). → see shortlist #3.
  - 市委 (municipal party committees): **719**
  - 中共广东省委: **625**
  - other 省委/党委: **267**
- The provincial/municipal party committees (~1,600 demand) have no crawler and
  are scattered across many issuers — low yield, would need bespoke targets.

## Bottom line
Real remaining value, in order: **(1) fix the resolver (zero-pad + number→title +
punctuation) — ~4–6k demand, zero crawl;** (2) probe 12371 for central Party
docs (~2.7k); (3) a targeted gkmlpt re-sync of Zhuhai/Jiangmen/Jieyang/Shanwei/
Shaoguan (~2.3k, scattered); (4) a State Council 国发 archive section if cheap.
Everything else (blocked ministries, province portals, npc metadata, the unknown
bucket, remaining central old-doc tails) is either datacenter-blocked, by-design,
or a thin tail — not worth a crawl campaign.
