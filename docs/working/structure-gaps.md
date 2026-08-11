# Structure-chart coverage gaps — prioritized (2026-08-11)

Cross-referenced `data/structure.yaml` (the /structure org chart) against actual
crawler coverage (`crawlers/*.py`, `govcms.py` + `gkmlpt.py` SITES dicts) and the
`coverage-tracker.md` status notes. Full machine-readable list: `structure-gaps.csv`.

**Chart accounting:** 16 of the chart's nodes are rendered *uncrawled* (no `site_key`):
6 party organs (context-only), 2 tier roots (NPC, SPC — their children are crawled),
and **8 mirrored central ministries** (MPS, MOJ, MCA, MOHRSS, MOHURD, MEM, NHC, CNAO).
The bigger opportunity is **bodies missing from the chart entirely** — especially the
AI/data/S&T research + standards + industrial-economic tier, which is where this
project's value concentrates. Those dominate the top of the list below.

Legend: 🖥️ = needs a residential/browser fetch (datacenter-IP-blocked or SPA); the
droplet crawler alone won't reach it.

## Central — AI / data / S&T / industrial (highest value)

1. **CAICT 中国信息通信研究院** — MIIT's flagship think tank; the authoritative AI /
   data-element / computing-power / 6G white papers already cited across the corpus.
   `caict.ac.cn`, list at `/kxyj/qwfb/`. Single highest-value source missing.
2. **Jiqizhixin 机器之心** — leading China AI/ML media, peer of the already-crawled
   量子位 (qbitai). `jiqizhixin.com` — check for a wp-json/REST API → low-friction,
   high AI density.
3. **NFRA 国家金融监督管理总局** — 2023 ministerial-rank financial regulator (fintech,
   AI-in-finance, bank data/algorithm rules). `nfra.gov.cn`. 🖥️ SPA (215B shell).
4. **SASAC 国资委** — supervises central SOEs incl. the chip/telecom/AI/energy giants.
   Core industrial-economic body absent. `sasac.gov.cn`, 政策发布
   `/n2588035/n2588320/n2588335/index.html` (main site static; policy DB may be SPA).
5. **TC260 全国网络安全标准化技术委员会** — issues the *operative* AI-security/ethics
   standards (生成式AI安全基本要求 GB/T45654, 实践指南 series) — the technical backbone of
   China's AI governance. `tc260.org.cn`.
6. **BAAI 北京智源人工智能研究院** — top national AI research institute (Wu Dao, 智源大会).
   `baai.ac.cn`.
7. **Shanghai AI Lab 上海人工智能实验室** — leading state AI lab (InternLM, AI-safety,
   AI4Science). `shlab.org.cn/research`.
8. **NSFC 国家自然科学基金委** — primary basic-research funder; grant guides steer where
   AI/chip/quantum money flows. `nsfc.gov.cn`, static `/p1/3381/2824/` — looks crawlable.

## Central — economic / regulatory (second tier)

9. **GAC 海关总署** — customs regs = semiconductor/dual-use export controls & trade data
   (joint 两用物项 catalogs with MOFCOM). `customs.gov.cn/customs/302249/`.
10. **DRC 国务院发展研究中心** — the State Council's own top economic think tank; reports
    feed macro/industrial policy. `drc.gov.cn/drcreport.htm`.
11. **CAS 中国科学院** — apex national research system (AI/chip/quantum institutes).
    `cas.cn` (scope to HQ 通知/政策; institutes sprawl across subdomains).
12. **NMPA 药监局** — approves AI-enabled medical devices. `nmpa.gov.cn`. 🖥️ recheck CMS.
13. **MOHRSS 人社部** *(on chart, uncrawled)* — labor/AI-and-jobs, AI-engineer title
    schemes. Found a static-looking `xxgk2020/.../gfxwj/index_41.html` — **recheck**;
    coverage §9 flagged it SPA, but that index may be paginated-static. 🖥️ maybe.

## Provincial / city — major AI/tech regions blocked

14. **Anhui 安徽 / Hefei 合肥** — quantum + AI + big-science hub (科学岛, 讯飞). 🖥️
    datacenter anti-bot (403). Also **Sichuan/Chengdu** (chip packaging, hard-blocked)
    and **Shaanxi/Xi'an** (semiconductor cluster, hard-blocked) — all need a
    residential vantage per coverage §5/§11/§13.
15. **Tianjin 天津** — direct-controlled municipality (province-rank). 🖥️ reachable but
    Hanweb datacall client-rendered lists (browser network inspection needed, §12).

## Notes on the rest

- Remaining chart-uncrawled central ministries (**MPS, MOJ, MOHURD, MEM, MCA, CNAO**)
  are lower AI/tech density → priority 3. MOJ is the most interesting (drafts
  administrative regulations incl. data/tech rules).
- Party commissions on the chart (**Central Financial / S&T / Reform / Cyberspace
  Commissions**) are context-only: they have no dedicated doc-publishing sites and
  work through already-crawled bodies (Cyberspace Commission = CAC; S&T Commission's
  office = MOST). No crawl target.
- Additional low-friction media if the AI-media tier is expanded: **Leiphone 雷峰网**,
  **Huxiu 虎嗅** (coverage §10 flagged these), **Qiushi 求是网** (party-line signal).

## Verified reachability (2026-08-11 — droplet curl + residential Chrome + Google)

Candidate URLs were tested by fetching from the droplet (browser UA, gunzip) and,
for droplet-blocked ones, from a residential browser. Two of the subagent's guessed
paths were wrong and corrected via Google.

**✅ Droplet-crawlable NOW (config-only wins — build these first):**
- **TC260** `tc260.org.cn` — 200, 52 links. AI-security/ethics standards.
- **SASAC** `sasac.gov.cn/n2588035/n2588320/n2588335/index.html` — 200, 81 links.
- **Shanghai AI Lab** `shlab.org.cn/research` — 200, 94 links.
- **NSFC** — article pages (`nsfc.gov.cn/p1/3381/2824/NNNNN.html`, `/p1/2871/2874/2882/…`)
  fetch fine (200, real body). The bare directory 403s, so the crawler must harvest
  article links from a list page, not the dir index. Section = 政策法规 / 通知公告.
- **DRC** `drc.gov.cn/drcreport.htm` — 200 (modest; find the report-list page).

**🖥️ Datacenter-IP-blocked (need a residential vantage — same tier as the blocked
provinces; only a residential proxy or local-crawl-and-merge reaches them):**
- **CAICT 信通院** — the droplet 404s even the correct Google-found whitepaper URLs
  (`/kxyj/qwfb/bps/index_14.htm`, `/kxyj/qwfb/ztbg/`), i.e. IP-fenced. THE single
  highest-value miss — reinforces the case for a residential fetch vantage.
- **GAC 海关总署** `customs.gov.cn/customs/302249/` — 412 (WAF precondition block).

**⚙️ SPA / JS-app (reachable, but content is client-rendered — need browser
network-inspection to find the data API, like qbitai/haidian):**
- **Jiqizhixin 机器之心** — React/Apollo **GraphQL** (NOT WordPress; the wp-json guess
  was wrong). Articles at `/articles/YYYY-MM-DD-N`. Find the GraphQL endpoint.
- **BAAI 智源** `baai.ac.cn` — 1.5KB shell.
- **NFRA 金融监管总局** `nfra.gov.cn` — 237B shell.

**Bottom line:** 5 config-only crawlable now (TC260, SASAC, Shanghai AI Lab, NSFC, DRC);
2 blocked → residential tier (CAICT, GAC); 3 SPA → browser-API tier (Jiqizhixin, BAAI, NFRA).

## Crawler build round 1 (2026-08-11) — 5-agent fleet + central integration

A fleet of investigation subagents went through the central-body gaps; each detected
the URL dialect from the droplet vantage. Verdicts + what got built:

**✅ BUILT (config-only, added to `crawlers/govcms.py` + crawled):**
| Body | site_key | dialect | docs | notes |
|---|---|---|---|---|
| 国资委 SASAC | `sasac` | K ccontent (new) | 33 | /nN/…/c<id>/content.html |
| 网安标委 TC260 | `tc260` | L portal (new) | 17 | /portal/article/<cat>/<id>; dates via body fallback |
| 中科院 CAS | `cas` | A t-date .shtml | 74 | HQ notices/policy |
| 审计署 CNAO | `cnao` | K ccontent | 69 | 中华人民共和国审计法 etc., 1.5k-char bodies |
| 自然科学基金委 NSFC | `nsfc` | M nsfc (new) | 63 | /p1/<col>/<numid>.html; 7.7k-char bodies |
| 应急管理部 MEM | `mem` | A t-date .shtml | 2 | fg/ sparse (external law links filtered); TODO 规范性文件 sub-sections |
| 司法部 MOJ | `moj` | A t-date | 20 | unblocked by the base.py cookie-jar fix; 集成电路布图设计保护条例 etc. |

**Session total: 278 docs across 7 new central bodies (SASAC 33, TC260 17, CAS 74,
CNAO 69, NSFC 63, MEM 2, MOJ 20). All 7 wired into `daily_sync.sh` for nightly refresh;
citation_rank + scores reconcile on tonight's run.**

Framework improvements this round: new dialects K/L/M; `_PUB_DATE` (pull publish date
from the article body when the list row has none); same-host + no-`/../` quality filter
(drops cross-site nav links like SASAC→gov.cn and CAS protocol-relative `../..` 400s).

**✅ DONE — base.py cookie-jar fix (unblocked MOJ + the openresty/CT6T class):**
- `base.fetch()` now uses a per-call `HTTPCookieProcessor`, so a WAF that sets a cookie
  on a 302→self and requires it replayed on the redirect works instead of looping.
  MOJ 司法部 (`moj`) went from blocked → 20 docs. Empty jar for cookieless sites = no
  regression (verified: CNAO unchanged). Future openresty/CT6T gov sites now crawlable.

**🖥️ BLOCKED — JS anti-bot WAF or IP-fence (need a headless-browser or residential vantage):**
- MPS 公安部 (Jiasule `__jsl_clearance` JS) · MCA 民政部 (DNS SERVFAIL from droplet) ·
  NHC 卫健委 (412 JS-cookie WAF) · MOHRSS 人社部 (Tencent EdgeOne JS cookie) ·
  MOHURD 住建部 (intermittent WAF + JS-rendered list) · NMPA 药监局 (Aliyun `$_ts` JS WAF) ·
  GAC 海关总署 (policy-section 412 WAF; homepage IS reachable) ·
  CAICT 信通院 (every path 404-fenced — highest value, most completely blocked) ·
  Jiqizhixin 机器之心 (200 but serves a data-service interstitial to datacenter IPs).

**⚙️ API-crawlable NOW (bespoke, no residential needed):**
- **Huxiu 虎嗅** — JSON API `api-web-article.huxiu.com/web/channel/articleList` for
  discovery → SSR `/article/{aid}.html` for bodies. Build a small dedicated crawler.

**❌ SPA (out of scope for govcms's URL-pattern dialects):**
- DRC 国务院发展研究中心 (easyui AJAX datagrid, no server-rendered list).

**Accounting:** of the ~16 central bodies investigated → 6 built config-only, 1 pending a
base.py cookie fix, 1 API-crawlable (Huxiu), 1 SPA (DRC), 9 blocked (residential/JS-WAF).
The blocked cluster shares the same root cause as the blocked provinces: datacenter-IP
WAFs. A residential fetch vantage (proxy or local-crawl-and-merge) is the common unlock.

## Crawler build round 2 (2026-08-11) — central bureaus, 11 built / 625 docs

Same 5-agent fleet pattern, targeting the directly-subordinate central bureaus.

**✅ BUILT (config-only, in govcms + crawled + wired into daily_sync):**
| Body | site_key | dialect | docs | body% |
|---|---|---|--:|--:|
| 最高人民法院 SPC | `spc` | N spc *(new)* | 114 | 48 (hearing notices thin) |
| 求是网 Qiushi | `qstheory` | D hex | 130 | 82 |
| 中国民用航空局 CAAC | `caac` | A t-date | 112 | 100 |
| 中医药局 NATCM | `natcm` | O datepath *(new)* | 75 | 96 |
| 粮储局 NFSRA | `nfsra` | C content | 50 | 2 · body TODO |
| 中国气象局 CMA | `cma` | A t-date | 46 | 100 |
| 文物局 NCHA | `ncha` | B /art/ | 26 | 92 |
| 外汇局 SAFE | `safe` | P safe *(new)* | 20 | 5 · body TODO |
| 移民局 NIA | `nia` | K ccontent | 20 | 75 |
| 林草局 SFA | `sfa` | Q ymd8 *(new)* | 20 | — |
| 邮政局 SPB | `spb` | I hexmon | 12 | 25 |

New dialects N (spc /fabu/xiangqing), O (datepath /YYYY-MM-DD/id), P (safe /YYYY/MMDD/id),
Q (ymd8 /YYYYMMDD/id). **Body-extraction TODO for SAFE + NFSRA** — links/titles/dates
crawl fine but their article-body container isn't in `_BODY_CONTAINERS` yet (near-empty
bodies); backfillable once the container is added.

**⚙️ crawlable-but-DEFERRED:** CCGP 政府采购网 (dialect A, but high-volume low-value tender
notices — accounted, not crawled to avoid flooding the corpus).

**🖥️ blocked (residential/JS-WAF):** NRA 铁路局 (IPv6 CDN misroutes datacenter IP) ·
STMA 烟草局 (WAF blackholes datacenter IP; site is dialect L, residential would work) ·
NDCPA 疾控局 (jQuery JSON-rendered list = SPA).

## Master ledger

`docs/working/coverage-ledger.csv` (built by `scripts/rnd/discovery/build_coverage_ledger.py`)
is the canonical account: **297 institutions — 279 held, 18 not-held (11 blocked, 5 SPA,
1 API-ready = Huxiu)**. Regenerated from the live DB each round; the not-held list +
limitations are maintained in the builder. This is the "account for everything" artifact
for the full-coverage campaign.

## Crawler build round 3 (2026-08-11) — long-tail central + the provincial-wall proof

**✅ BUILT (config-only):** SASTIND 国防科工局 (K, 8) · CNSA 航天局 (K, 4) · SAAC 档案局
(I, 93). Wired into daily_sync.

**SPA / blocked (accounted):** SAC 标准委 (JS-SPA list+body) · GJXFJ 信访局 (wPaginate.js
SPA) · CCPS 中央党校 (Tencent WAF 403).

**Provincial-portal accounting sweep — 9 provinces, ALL blocked (the decisive finding):**
Henan (Wangsu CDN WAF 403) · Anhui (WZWS WAF `reason:GeoBL`, Hefei hub) · Hebei/Shanxi/
Jiangxi/Guangxi (network blackhole, SYN dropped) · Shaanxi/Guizhou (IPv6-only, no IPv4
route) · Yunnan (list metadata reachable via dialect A, but article bodies WAF-403).
**0/9 crawlable from the droplet** — hard confirmation that the provincial/city tier is
uniformly datacenter-IP-walled.

## Strategic inflection (after 3 rounds, ~21 central crawlers, ~1,000 docs)

The campaign has hit its natural shape. Two frontiers remain, and they need different things:
1. **The config-only central frontier is largely picked.** Most remaining central bodies
   are either held, SPA, or WAF-blocked. Diminishing returns on more central fleets.
2. **The mass of what's left — every uncrawled province + most major cities — is behind
   the datacenter-IP wall** (proven 9/9 this round). This is NOT solvable from the NYC
   droplet by any crawler cleverness; it needs a **residential/CN fetch vantage** (proxy
   or local-crawl-and-merge). This is the single highest-leverage unlock and a resource
   decision for the owner.
3. **Autonomous frontier that remains:** bespoke **API crawlers** for the SPA tier that
   expose JSON (Huxiu confirmed; likely CDC/GJXFJ/SAC/机器之心), plus the SAFE+NFSRA
   body-container fix. Lower throughput (per-site engineering) but doable without a
   residential vantage.
