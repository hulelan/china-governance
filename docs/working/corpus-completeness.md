# Corpus completeness — TODO (body text + missing citations)

Snapshot 2026-07-13, live droplet `documents.db` (192,687 docs). Two distinct
completeness problems: **(A)** docs we HOLD but have no full text, and **(B)** docs
we CITE but don't hold. Plus **(C)** a data-quality fix that improves both.

Regenerate the numbers with the SQL in `missing-cited-docs.md` (§Regenerate) and
the body-coverage query at the bottom of this file.

---

## A. Body-text backfill — docs we hold, no `body_text_cn`

**40,948 of 192,687 docs (21%) have no body.** But this is really two problems:

| | docs | note |
|---|---|---|
| **All docs** | 78.7% have body | headline number, misleading |
| **Excluding `npc`** | **92.8% have body** | the "real" coverage |
| `npc` alone | **29,204 / 29,208 → 0%** | metadata-only *by design* |

### A1. NPC full text — 29,204 laws, 0% body ⭐ THE "law" gap
The National Laws Database (`crawlers/npc.py`) was built metadata-only (title,
document_number, publisher — no body). This is the single biggest full-text
opportunity in the corpus and the "law" gap.
- **First step (verify feasibility):** confirm `npc.gov.cn` exposes each law's full
  text on a per-law page / API (some entries are scanned PDFs; some are HTML). Pull
  one law end-to-end before committing to 29k.
- **Then:** extend the npc crawler with a body-fetch pass (or a dedicated
  `--backfill-bodies` mode like gkmlpt has). ~29k fetches — stage it, it's large.
- **Decision:** is full statutory text in-scope for this project, or is the laws DB
  intentionally a metadata index? (If the latter, close this and note it as
  deliberate so the 78.7% number stops looking like a defect.)

### A2. Failed body fetches — the long tail (try FREE backfill first)
These are docs whose body fetch failed or was skipped — many may re-extract from
already-saved raw HTML at **zero cost** via `scripts/backfill_from_html.py`.
| site | no_body | have % | likely cause |
|---|---|---|---|
| `miit` | 2,754 | 32% | US→China timeouts on body fetch (see crawler docstring) |
| `suzhou` | 1,022 | 79% | partial backfill |
| `fgw` | 811 | 58% | partial backfill |
| `stic` | 674 | 72% | partial backfill |
| `mzj` | 366 | 92% | tail |
| `guancha` | 364 | 94% | homepage-only articles w/o full body |
| `swj`/`szpsq`/`jtys`/… | ~300 each | 88-90% | tail |
- **Action:** run `backfill_from_html.py --site <s> --dry-run` on the top few
  (miit, suzhou, fgw, stic) to see how many recover from saved HTML for free. Only
  what's left needs a re-crawl.

### A3. `ipc_court` — 285 docs, 0% body (real scraping job)
`ipc.court.gov.cn` renders bodies via **PDF.js / client-side JS** (static HTML is a
269-byte shell). NOT a UA fix. Needs the `/article/content/…` data endpoint or PDF
extraction. Do when the court corpus matters. (Also tracked in `todos.md` §4b.)

---

## B. Targeted crawl — docs we cite but don't hold

Dangling citations (target_id IS NULL): **56,021 formal (81%)**, **100,459 named
(60%)**, **6,568 llm (43%)**. The most-cited missing docs are the crawl priority —
the missing-cited list IS the ranked backlog. Highest-leverage first:

### B1. Single flagship docs (few fetches, huge citation payoff)
- ⭐ **粤港澳大湾区发展规划纲要** (Greater Bay Area Development Plan) — cited **313×**,
  a central flagship we don't have. One fetch.
- **国家中长期科学和技术发展规划纲要（2006-2020年）** — cited **98×**, central S&T plan.

### B2. State Council 国发 / 国办 cluster — best ROI
~1,563 distinct missing docs, **5,550 refs**. Small, high-value, findable on
gov.cn / the State Council document DB. Examples: `国发〔2004〕20号` (47×),
`国发〔2010〕33号` (45×), `国发〔2004〕10号` (43×).

### B3. Guangdong planning & land-management regs — the dominant thematic gap
These underpin the entire GD/Shenzhen municipal corpus (most-cited named titles):
- 广东省城乡规划条例 (957×) · 城市、镇控制性详细规划编制审批办法 (915×)
- 广东省控制性详细规划管理条例 (340×) · 建设用地容积率管理办法 (371×)
- 广东省征地补偿保护标准 (268×) · 广东省自然资源厅…控制性详细规划管理指导意见 (287×)
- Municipal: 惠州市加强建设项目征地拆迁管理规定 (513×), 中山市…城市总体规划 (146-224×)
- **Source:** most are on 广东省人民政府 / 广东省自然资源厅 / 中山市府 sites — a
  targeted GD-planning crawl would resolve thousands of edges at once.

---

## C. Data quality — normalize `target_ref` before ranking (do this FIRST)

The greedy `REF_PATTERN` folds lead-in words ("按照"/"根据") and issuer names into
the 文号, so **one doc fragments into 2-3 "missing" entries** and inflates counts:
```
127 × 按照苏州市住房和城乡建设局苏住建规〔2011〕4号
126 × 苏州市住房和城乡建设局苏住建规〔2011〕4号
      苏住建规〔2011〕4号            ← same doc, three rows
```
Same for `根据财库〔2022〕3号` vs `财库〔2022〕4号`.
- **Fix:** in `scripts/rnd/citations/extract_citations.py`, normalize `target_ref`
  to the bare 文号 (strip leading 按照/根据/依据; strip a prepended agency name;
  keep `<机关简称>〔YYYY〕N号`) before grouping/resolving.
- **Payoff:** collapses duplicate "missing" rows, raises the formal resolve rate
  (some of these fragments probably DO match a held doc once cleaned), and makes
  this whole wishlist rank honestly. Low effort, high signal. **Blocks accurate
  prioritization of B**, so do it before a big targeted crawl.

---

## Suggested order
1. **C** (ref normalization) — cheap, and it corrects the priorities for B.
2. **A2** (free `backfill_from_html` on miit/suzhou/fgw/stic) — recover body text
   at $0 before any re-crawl.
3. **B1** (grab the 2 flagship central docs — 大湾区纲要, S&T纲要) — trivial, high visibility.
4. **A1 decision** (is NPC full-text in scope?) — the big one; needs your call.
5. **B2/B3** (targeted State Council + GD-planning crawls) — larger, do after C.
6. **A3** (ipc_court JS/PDF) — when the court corpus matters.

## Regenerate (body coverage by site)
```sql
SELECT site_key, COUNT(*) total,
       SUM(body_text_cn IS NULL OR body_text_cn='') no_body,
       ROUND(100.0*SUM(body_text_cn IS NOT NULL AND body_text_cn!='')/COUNT(*),1) pct_have
FROM documents GROUP BY site_key HAVING no_body > 0 ORDER BY no_body DESC;
```
