# Sources catalog — what we don't fully have yet, and the plan

Snapshot 2026-07-15. Purpose: label every gap by HOW we close it, so work is a
matter of execution, not rediscovery. Built from three inputs: the site inventory
(`documents`/`sites`), the formal frontier (`cluster_frontier.py`), and the
policy-trace hunt (top missing named 《》 articles). Regenerate the numbers with
the queries at the bottom.

## Coverage-expansion program (toward full coverage of CN gov sites)

**Method that scales — gkmlpt batch discovery.** A huge share of Chinese gov sites
run the `公开目录平台` (gkmlpt) CMS that `crawlers/gkmlpt.py` already handles: each
is a free scraper (a `SITES` dict entry; SID + category tree auto-discover via
`discover_site()`). So "build a scraper" for these = probe a candidate domain, and
if `discover_site()` passes, add the entry. Batch-probe a list of a jurisdiction's
department/agency subdomains, add all that pass.

**Progress:**
- **GD provincial departments — 19 added (2026-07-15):** 自然资源厅/人社厅/住建厅 +
  教育厅/科技厅/工信厅/公安厅/民政厅/财政厅/生态环境厅/交通运输厅/农业农村厅/商务厅/
  文旅厅/卫健委/应急管理厅/林业局/医保局/发改委. (`gdnr`, `gdedu`, … in `SITES`.)
  Crawl queued via `coverage_round.sh`.
- Still TODO in GD ecosystem: 水利厅/市场监管局/司法厅/审计厅 (find correct domains);
  GD *municipal* departments; the broken/removed GD cities (Dongguan, Foshan, …).

**Roadmap for full coverage (by platform, highest-volume first):**
1. **GD ecosystem (gkmlpt)** — provincial depts (done), municipal depts, agencies.
   All bulk-discoverable. Nearly free.
2. **Other provinces' portals** — each is a DIFFERENT CMS (Shanghai = static year-
   archives; Jiangsu = jpaas jpage; Beijing/Chongqing/Zhejiang = their own). For each:
   probe the province portal + its departments, characterize the mechanism, build/
   adapt one crawler, then batch its departments the same way. Prioritize by frontier
   rank (Beijing 2,749, Suzhou/Jiangsu 3,962, Chongqing 2,928, …).

   **JIANGSU (investigated 2026-07-15):** provincial portal + departments ALL run the
   **jpaas `/art/` CMS** (财政厅/发改委/工信厅/交通厅 verified; NOT gkmlpt). Our
   `crawlers/jiangsu.py` handles the provincial portal via the jpage `dataproxy.jsp`
   API keyed by `columnid`+`unitid`+`webid` (hardcoded unitid=356383, webid=1 for
   www). To batch DEPARTMENTS: refactor jiangsu.py to a multi-site config. Discovery
   status: `webid` IS extractable from each dept homepage (财政厅=35, 发改委=3,
   工信厅=23), column ids are in `/col/colNNNN/` links, but **`unitid` is NOT on the
   homepage** — it's the missing piece (likely in the column-page JS or a config
   include; direct `/col/colN/index.html` fetch returned HTTPError, needs the right
   URL/referer). Also several dept domains 404'd (jsjs/jse/jss/zrzy) — find correct
   hosts. So Jiangsu depts are batchable but need: (a) solve unitid discovery, (b)
   identify each dept's policy-doc column id, (c) multi-site refactor of jiangsu.py.
   **The provincial 苏政发/苏政办发 cluster (bulk of the 苏 frontier) is already handled
   by the queued [BACKFILL]** (js → 991 docnums); dept regs (苏住建规) need this work.
   NOTE: gkmlpt's clean auto-discovery was a Guangdong luxury; jpaas needs per-site
   config extraction. Beijing next — characterize its CMS the same way before building.

   **BEIJING (probed 2026-07-15):** distinct CMS — NOT gkmlpt, NOT clearly jpaas.
   `www.beijing.gov.cn`/住建委/发改委 show no platform markers on the homepage;
   人社局 (`rsj.beijing.gov.cn`) uses `/col/col` (column-based, jpaas-family?). Needs
   its own characterization (probe the listing/pagination mechanism) + crawler.
   Provincial 京政发/京政办发 cluster already handled by queued [BACKFILL] (bj → 744).

   **META-CONCLUSION:** each province runs a DIFFERENT CMS, so "full coverage" past
   Guangdong is a per-province ENGINEERING program (characterize CMS → build/adapt
   one crawler → batch that province's departments), NOT free batching. Guangdong's
   gkmlpt was the one universal-auto-discovery ecosystem. GOOD NEWS: the provincial
   *core* of every top cluster (苏政发, 京政发, 沪府发) is resolved by the [BACKFILL]
   metadata fix on docs we ALREADY hold — so the expensive per-province crawler work
   is only needed for the DEPARTMENT long tail, which is lower-volume per ref.
3. **Central** — gov.cn library (`gov --library`) covers State Council + ministries;
   add dedicated crawlers only for bodies the library misses.
4. **[BLOCKED]** — huizhou/yangjiang/NPC need a China/residential vantage point.

Legend for the plan label on each source:
- **[BACKFILL]** — we already HOLD the docs; they just lack `document_number`.
  Fix = `scripts/rnd/backfill/backfill_docnums.py` (masthead 文号, jurisdiction-
  guarded). No crawling. MUST dry-run per site: only works if docs lead with their
  OWN 文号 (Shanghai/Jiangsu/gov yes; Zhongshan mostly no).
- **[LIBRARY]** — reachable via gov.cn's policy-document library
  (`gov --library --deep --categories gw|bm`). Central only.
- **[CRAWLER+]** — we have a crawler but it needs deepening or department subsites.
- **[BLOCKED]** — source is IP-gated from the droplet (datacenter/foreign IP).
  Needs a residential/China vantage point or a proxy.
- **[NEW]** — no crawler yet; a new source to build or investigate.

---

## A. [BACKFILL] Metadata gap — docs held, `document_number` empty

The biggest single lever. Many crawlers saved bodies without parsing the masthead
文号, so citations to these docs can't resolve even though we hold them. Extend
`SITE_PREFIX` with each site's jurisdiction stem, dry-run, then backfill + rebuild.

**Validated / done:**
- `sh` Shanghai (沪) — DONE: +3,295 → dangling 4,799→948.
- `gov` (国), `js` (苏), `bj` (京), `zhuhai` (珠), `mofcom` (商), `ndrc` (发改),
  `mof` (财), `zhongshan` (中府, low yield) — queued (all-site backfill after nightly).

**Candidates to add to SITE_PREFIX (high empty-docnum counts — dry-run each):**
| site | docs | w/ docnum | jurisdiction stem (guess) |
|---|---|---|---|
| `szdp` Shenzhen depts | 8,586 | 3 | 深 (per-dept varies) |
| `szlhq` Longhua | 6,280 | 104 | 深龙华/深华 |
| `mzj` | 4,847 | 225 | (identify dept) |
| `miit` | 4,057 | 159 | 工信部 |
| `szlg` Longgang | 3,893 | 182 | 深龙岗/深龙 |
| `heyuan` | 3,777 | 181 | 河/河府 |
| `hrss` | 3,106 | 211 | 人社 |
| `swj` `jtys` `zjj` `stic` `yjgl` `szeb` `fgw` `wjw` | ~2–3k each | ~2–5% | per-dept |
| `samr` | 2,689 | 636 | 国市监 |
| `cac` | 2,259 | 77 | 网信 |
| `gz` Guangzhou | 3,656 | 2,049 | 穗 |
- **CAVEAT:** GD municipal/district docs often DON'T lead with their own 文号
  (Zhongshan yielded only 74/3,416). Dry-run first; low yield = these stay a real
  gap (their 文号 sits elsewhere in the doc, or not at all).
- **NOT backfillable:** media (`guancha`/`xinhua`/`ifeng`/`people`/`stdaily`) have
  0 docnum by nature — news articles, not 文号 docs. They're citation SOURCES, not
  targets. Leave empty. `npc` (29k laws) is metadata-only (names, not 文号).

## B. [LIBRARY] Central — reachable via gov.cn policy-document library

From the article hunt, these top missing articles are central and in the library:
- 城市、镇控制性详细规划编制审批办法 (×915), 建设用地容积率管理办法 (×371) — **住建部 (MOHURD)**
- 公务员录用体检通用标准 (×133), 事业单位公开招聘违纪违规… (×123) — **人社部**
- 律师事务所年度检查考核办法 (×97) — **司法部**
- 粤港澳大湾区发展规划纲要 (×318), 健康中国2030 (×115),
  国家中长期科技发展规划纲要 (×105), 法治政府建设实施纲要 (×81) — **State Council / 中办国办**
- COVID directives (新冠…防控方案第九版 ×174, 优化防控措施 ×213) — **国务院联防联控/卫健委**
- **Plan:** `gov --library --deep --categories bm` (ministries) + `gw` (State Council).
  Already built; the nightly + backfill rounds keep chipping these. The flagship
  中办国办 plans may need a targeted fetch (co-issued docs surface irregularly).

## C. [CRAWLER+] Existing crawler, needs department subsites / deepening

The article hunt's dominant cluster is **Guangdong provincial DEPARTMENT regs** we
don't reach — we crawl the GD main portal (`gd`), not each 厅/局 subsite.

**HOW TO CRAWL — SOLVED (2026-07-15): the GD dept subsites run on `gkmlpt`.**
Verified: `nr.gd.gov.cn` (SID=153, 27 cats), `hrss.gd.gov.cn` (SID=186),
`zfcxjst.gd.gov.cn` (SID=233, 13 cats) all serve `/gkmlpt/index` and pass
`crawlers.gkmlpt.discover_site()` — the SID + category tree auto-discover, so this
is our EXISTING crawler, no new code. **Added to `SITES`** as `gdnr` / `gdhrss` /
`gdzjst` (distinct keys — existing `hrss` is Shenzhen's `hrss.sz.gov.cn`, a
different body). All reachable from the droplet. Run: `python3 -m crawlers.gkmlpt
--site gdnr` (etc.), then citations rebuild. → resolves the 自然资源厅 (×287),
人社厅 (×244/×81) clusters.
- `司法厅` (`sft.gd.gov.cn`) returned HTTPError on the bare host — probe the right
  path / try `www.` before adding `gdsft`.
- **深圳市 dept docs** (深圳市科技计划项目管理办法 ×246, 深圳市财政局… ×166,
  深圳市城市规划标准与准则 ×88): Shenzhen depts are ALREADY gkmlpt sites we crawl
  (`szdp`, `stic`, …). These specific gaps are likely **[BACKFILL]** (metadata) or a
  missing sub-dept — check after the docnum backfill lands before adding crawlers.

**Provincial REGULATIONS (条例) — different source.** 广东省城乡规划条例 (×975),
广东省控制性详细规划管理条例 (×340) are 省人大 acts, NOT 厅 docs — issued by the
Provincial People's Congress. Candidate sources (both reachable): `rd.gd.cn`
(GD 人大) and the GD 规章库 under `gd.gov.cn/gkmlpt`. TODO: locate 广东省城乡规划条例
on one of them and confirm the listing mechanism (likely gkmlpt or a static
regulations index). This single 条例 is the #1 missing article — worth a targeted fetch.

## D. [BLOCKED] IP-gated from the droplet

- `huizhou` 惠州 — article 惠州市加强建设项目征地拆迁管理规定 (×513) + others.
  Datacenter-IP blocked (KNOWN, CLAUDE.md Open Questions). We hold 3,826 huizhou
  docs (from earlier residential crawls) but can't refresh from the droplet.
- `yangjiang` 阳江 — article 阳江市…征地青苗补偿规定 (×79). Same block. Hold 2,355.
- `npc` full statutory text — China-IP gated (only metadata worldwide). Articles
  中华人民共和国治安管理处罚条例 (×80), 粮食流通管理条例 (×78) are NPC admin regs.
- **Plan:** residential-IP / China VPS / proxy, or accept the gap. Decision pending
  (same as the NPC full-text decision). Note: many blocked-city regs are ALSO
  republished on gd.gov.cn / gov.cn — may be reachable there without the proxy.

## E. [NEW] / unknown — investigate

- Any dept subsite from §C once probed becomes a concrete [CRAWLER+] or [NEW].
- Sources the frontier's `--unreachable` families point to that aren't yet mapped
  (run `cluster_frontier.py --unreachable`).

---

## Priority order
1. **[BACKFILL] the high-yield sites** (gov/js/bj done-or-queued; then dry-run
   miit/samr/gz/szdp and add those that lead with 文号). Cheapest, biggest.
2. **[LIBRARY] targeted central fetches** for the flagship plans (大湾区纲要, etc.).
3. **[CRAWLER+] GD provincial department subsites** (自然资源厅 first — resolves the
   ×975/×340/×287 planning cluster). The main NEW crawling investment.
4. **[BLOCKED] decision** on huizhou/yangjiang/NPC (proxy vs accept vs republisher).

## Regenerate
```sql
-- site inventory + docnum coverage
SELECT d.site_key, s.admin_level, COUNT(*) docs,
       SUM(d.document_number!='') w_docnum
FROM documents d LEFT JOIN sites s ON s.site_key=d.site_key
GROUP BY d.site_key ORDER BY docs DESC;

-- top missing articles (named 《》)
SELECT COUNT(*) c, target_ref FROM citations
WHERE target_id IS NULL AND citation_type='named'
  AND LENGTH(target_ref) BETWEEN 8 AND 44
GROUP BY target_ref ORDER BY c DESC LIMIT 50;
```
