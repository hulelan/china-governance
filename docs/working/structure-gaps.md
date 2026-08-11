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
