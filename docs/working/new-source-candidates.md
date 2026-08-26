# New Source Candidates — institutions we CITE but never crawled (2026-08-26)

Read-only analysis against the LIVE droplet DB. Goal (distinct from
`backfill-tail-scan.md`, which covered institutions we *already* crawl): find
**genuinely-NEW source institutions/domains** — ones with **no `sites` row and no
crawler** — that the corpus cites but doesn't hold. Recency lens: prioritised refs
cited by docs crawled **since 2026-07-01** (~100k recent docs). No code changed.

## Method
- Unresolved edges: `citations WHERE target_id IS NULL` (232,213 of 491,193).
- Recent frontier: joined those to `documents` with `crawl_timestamp >= 2026-07-01`,
  aggregated top 2,500 `target_ref` by demand, classified each to an institution
  by 文号 prefix + leading-name regex.
- Sized each NEW institution across the **whole** unresolved table (LIKE buckets).
- Filtered out institutions already in `sites` and national-law metadata stubs
  (npc `law-db`, already present by design).
- Bounded droplet reachability curls (browser UA) — **and checked the response body,
  not just the status code** (several "200"s are JS anti-bot challenge stubs).

## The reachability trap (important)
A `200` status is NOT proof of crawlability. `mohrss.gov.cn` returns HTTP 200 but a
**987-byte EdgeOne/Tencent anti-bot JS challenge** (`EO_Bot_Ssid` cookie computed in
JS) on every page including the homepage — a plain crawler gets the stub, never the
list. `nfra.gov.cn` returns 200 / 237 bytes (SPA shell). So the honest split is:
real-HTML-reachable vs status-200-but-gated vs datacenter-blocked (000/412/521).

## RANKED new-institution candidates (whole-corpus unresolved demand)

| # | Institution | Domain | Demand (refs) | Droplet | Effort class |
|---|---|---|--:|---|---|
| 1 | 人社部 MOHRSS | mohrss.gov.cn | **923** (600) | 200 **but JS anti-bot stub** | bespoke (solve EdgeOne cookie / browser vantage) |
| 2 | 卫健委 NHC | nhc.gov.cn | **870** (558) | 412 WAF | proxy-gated |
| 3 | 民政部 MCA | mca.gov.cn | 400 (289) | 000 blocked | proxy-gated |
| 4 | 人防办 (人民防空) | *(no central portal)* | 349 (116) | — | low tractability (scattered provincial 人防办) |
| 5 | 海关总署 GACC | customs.gov.cn | 323 (237) | 412 WAF | proxy-gated |
| 6 | 公安部 MPS | mps.gov.cn | 213 (106) | 521 | proxy-gated |
| 7 | 自然资源部 MNR | mnr.gov.cn | 184 (120) | 000 blocked | proxy-gated (known) |
| 8 | 住建部 MOHURD | mohurd.gov.cn | 141 (120) | 000 blocked | proxy-gated (known) |
| 9 | **国家能源局 NEA** | nea.gov.cn | **111** (90) | **200 real (108KB)** | **QUICK WIN — config already exists** |
| 10 | 金融监管总局 NFRA | nfra.gov.cn | 72+54 (98) | 200 / 237B SPA shell | bespoke (JSON/SPA) |
| 11 | 海事局 MSA | msa.gov.cn | 58 (17) | 200 real (69KB) | bespoke (Java `.jhtml` + `lawId` JSON law API) |

## QUICK WINS (reachable + standard CMS, addable now)

Honestly there is **only one clean quick win** among genuinely-new institutions —
the new-source frontier is overwhelmingly datacenter-blocked or JS-gated:

1. **国家能源局 NEA — `nea.gov.cn` — do this immediately.** The govcms config
   **already exists** (`crawlers/govcms.py:455`, site key `nea`, dialect D =
   `/YYYYMMDD/<hex>/c.html`) but has **0 docs in the DB** — it was never run/wired
   into the nightly pass. Reachable with real content (homepage 108KB; a sample
   article `…/20260805/…/c.html` returns 10,792 bytes of extractable body). Action
   is just `python3 -m crawlers.govcms --site nea` + add it to the central/daily
   run set. Zero new code. ~111 demand + all future energy-policy citations.

That's it for true quick wins. The next two reachable-new sites are **bespoke and
thin** — worth a config only if you want the coverage, not for citation ROI:

2. **海事局 MSA — `msa.gov.cn`** — real HTML but a Java CMS: law list is a
   JS/JSON endpoint (`/page/hsfg/detail.jhtml?lawId=…`), not a t-date list. Bespoke
   crawler, only ~58 demand. Low priority.
3. **金融监管总局 NFRA — `nfra.gov.cn`** — SPA (237-byte shell), needs the
   backing JSON API. ~126 demand (incl. legacy 银保监/CBIRC refs). Bespoke; a new
   central financial regulator, so may be worth it for *forward* coverage more than
   for the citation backfill.

## Top prize, but not a quick win
**MOHRSS 人社部 (923 demand)** is by far the largest genuinely-new institution, and
`mohrss.gov.cn` is not IP-blocked — but every page is an EdgeOne JS anti-bot
challenge, so a plain `fetch()` gets a 987-byte stub. Getting it needs either a
challenge-solving session (compute the `EO_Bot_Ssid` cookie) or a browser vantage.
High value if you invest the bespoke effort once; not addable today.

## Proxy-gated tier (real demand, needs a residential vantage)
`NHC (870) · MCA (400) · GACC (323) · MPS (213) · MNR (184) · MOHURD (141)` —
combined ≈ **2,131 demand** across six major central ministries, all
datacenter-IP-blocked (000/412/521) from the droplet's NYC IP. This is the same
wall `backfill-tail-scan.md` and CLAUDE.md's coverage audit hit. It is a single
infrastructure fix (residential fetch proxy), not eleven crawler tasks — and it
would unlock the bulk of the new-source frontier at once. MNR/MOHURD/NHC were
already known-blocked; MCA/GACC/MPS are newly identified here as blocked-and-cited.

## Honest bottom line
- **Do now:** run/wire **NEA** (config already written, reachable, 0 effort).
- **Worth a bespoke build:** **MOHRSS** (923, JS-challenge) is the only large
  reachable-DNS target; everything bigger is IP-blocked.
- **Infrastructure decision, not a crawl:** a residential proxy unlocks
  NHC+MCA+GACC+MPS+MNR+MOHURD (~2,131 demand) together — higher aggregate value
  than any single new crawler.
- **Thin tail — skip unless you want the coverage per se:** MSA (58), NFRA (72),
  人防办 (349 but no central site). The 税务总局 公告 series (~726 recent) and the
  huge `OTHER`/national-law buckets are **backfill of sites we already crawl** or
  by-design npc metadata stubs — out of scope for "new sources."
