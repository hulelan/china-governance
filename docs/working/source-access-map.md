# Source Access Map — what we CAN and CANNOT reach

**The authoritative, living record of source reachability.** Consolidates access
status that used to be scattered across `reconnect-sources.md`,
`new-source-candidates.md`, `china-vantage-options.md`, and CLAUDE.md's Open Questions.

- **Last verified:** 2026-09-03 (central + provincial fully; 368-unit city tier mapped,
  reachability sampled — full list in `source-map-cities.csv`).
- **Vantage:** the droplet's NYC datacenter IP (`104.236.88.45`, AS14061 DigitalOcean).
  Reachability is IP-specific — a residential-China proxy changes most "blocked" rows.

## Method (how to read / refresh this)

**HTTP status is worthless for CN-gov reachability — measure CONTENT BYTES and follow
redirects.** Repeatedly burned: a site returns `200` but a 160-byte redirect stub or a
~1 KB anti-bot shell. Classify each source by:

1. `curl -s -o /dev/null -w "%{http_code}"` on homepage **and** a policy section
   (`/zwgk/`) — with a browser UA, `--max-time 8`.
2. `curl -s <url> | wc -c` (and `curl -sL` to follow redirects): **<2 KB = stub/anti-bot,
   not real content**; tens–hundreds of KB = real.

Codes: `200/301/302`→check bytes · `000`→TCP blackhole (network geo-fence) ·
`403/406/412`→WAF geo-block · `521`→origin/anti-bot · section-`404`-but-home-`200`→
geo-fenced sections (NEA pattern).

**Refresh:** re-run the sweep — `scripts/rnd/discovery/reachability_sweep.sh <list>`
(list = `tier|name|url` lines) — then update the tables below with the date.

---

## Crawled this run (2026-09-04) — Tier B actioned ✅

Turned the reachable-new frontier into live crawlers: **37 sources configured, 34
yielding, +1,595 docs** (corpus 285,659 → 287,254), **+849 citations resolved**. All
`no-proxy`. Now in Tier A:
- **青海 Qinghai** (113), **新疆 Xinjiang** (49), **民委 NEAC** (16) — 2 new dialects
  (U `qhsys`, V `cmon`) added to `govcms.py`.
- **31 prefecture cities** (top: liuzhou 118, liaoyuan 114, shannan 96, linxia 74,
  suzhou_ah 67, changzhi 62, ganzhou 59, hanzhong 58 …).
- **3 zero-yield** (need a section-path/dialect fix, low priority): **zhoukou, quanzhou,
  jiyuan** — configured but their listing sections rendered no articles (JS or wrong path).
- Wired into the nightly (`--group city` + qinghai/neac/xinjiang in the govcms loop),
  so they stay synced. Full per-site table: `logs/citycrawl_*.log` on the droplet.

## Tier A — CRAWLED (we already ingest these) ✅

- **Central (~40 bodies):** State Council (`gov`), NPC, SPC, PBoC, MoT, MARA, MOJ,
  MOFCOM, NDRC, MFA, CNAO, MIIT, MEM, MOE, MCT, MWR, MEE, MOST, MOF, MVA + ~20 more
  agencies (chinatax, csrc, cac, samr, cnipa, nbs, sasac, pbc, nhsa, nrta, …). See the
  `sites` table (`admin_level='central'`) for the live list.
- **Provinces (14):** Beijing, Shanghai, Jiangsu, **Zhejiang\***, Guangdong,
  **Heilongjiang\***, Fujian, Liaoning, Ningxia, Shandong, Xizang, Hunan, Jilin, Chongqing.
  - **\* Zhejiang and Heilongjiang main portals are BLACKHOLED** from our IP — we must
    be reaching them via department subdomains. Confirm that path still works.
- **Cities (~20):** Guangzhou, Shenzhen + 13 GD cities, Suzhou, Wuhan, Hangzhou,
  Qingdao, Jinan, Shenyang (see city map below).

## Tier B — REACHABLE-NEW (crawlable now, NO proxy) → build a crawler 🎯

Content-verified real portals we do **not** yet crawl. Highest-value action items.

| Source | Domain | Evidence | Note |
|---|---|---|---|
| **青海 Qinghai** (province) | **http://**www.qinghai.gov.cn | 162 KB real (HTTPS is blackholed) | crawlable — /zwgk/xwdt/ sections; new dialect U |
| **新疆 Xinjiang** (province) | www.xinjiang.gov.cn | 108 KB real | crawlable — already configured (was mis-tagged residential) |
| **民委 NEAC** (central, ethnic affairs) | www.neac.gov.cn | 171 KB real | crawlable — /seac/xxgk/ sections; new dialect V |

> **Correction (2026-09-04):** 云南 Yunnan was a FALSE POSITIVE here — its homepage
> loads (146 KB) but **every `/zwgk/*` policy section returns a 403 WAF shell** from our
> IP. Moved to Tier C (proxy-gated). Lesson reinforced: verify the *policy sections*, not
> just the homepage.

## Tier C — PROXY-GATED (datacenter-IP blocked) → needs residential-CN proxy 🔒

Real sites, but our NYC IP is blocked (blackhole/WAF). See `china-vantage-options.md`
— one residential proxy unlocks this whole tier.

- **Central:** 住建部 MOHURD (blackhole), 民政部 MCA (blackhole), 自然资源部 MNR
  (blackhole), 卫健委 NHC (412), 公安部 MPS (521), 国家能源局 NEA (home 200 but sections 404).
- **Provinces:** 四川 Sichuan, 山西 Shanxi, 广西 Guangxi, 江西 Jiangxi, 河北 Hebei,
  海南 Hainan, 贵州 Guizhou, 陕西 Shaanxi (all blackhole); 河南 Henan, 安徽 Anhui,
  内蒙古 Inner Mongolia (403); 湖北 Hubei, 甘肃 Gansu (412);
  **云南 Yunnan (403 on all policy sections — homepage 200 is a false positive).**
- **GD cities:** 惠州 Huizhou, 阳江 Yangjiang (blackhole).

## Tier D — ANTI-BOT (needs a browser/cookie-solving fetch) 🤖

Reachable IP-wise but every page is a JS challenge, not content.

- **人社部 MOHRSS** — www.mohrss.gov.cn (988-byte anti-bot shell on 200).

## Tier E — SPA / SEARCH-DB-GATED (needs a bespoke crawler) 🧩

Docs exist but only behind a JS search API, not a browsable list.

- **福建 政策文件库** `/zck/` (WAS5 search) — the bulk of Fujian dept 规范性文件.
- **reconnectchina.org** itself — login-gated + robots-disallowed; **email them for API
  access** (they invite it). Do NOT scrape. See `reconnect-sources.md`.

## Tier F — DEAD / NO PUBLIC POLICY PORTAL ⛔

- **天津 Tianjin** — homepage redirect resolves to an empty response (not crawlable now).
- **国家安全部 MSS**, **中宣部/宣传部** — no standalone public policy portal.
- The highest-demand DELISTED documents (苏住建规, 深圳听证办法, 采购供应商信用, 广东控规条例)
  — withdrawn from origin sites; only via 北大法宝 / 国家法律法规数据库 / archive.org.

---

## City tier (368 units) — full list in `source-map-cities.csv`

Recovered in full from ReConnect's public JS bundle (taxonomy only, no doc scraping):
**335 prefecture cities + 4 municipalities + 29 special county-level units** (XPCC/兵团,
Hainan counties, Hubei 天门/仙桃/潜江/神农架, 河南济源, 香港/澳门).

- **Coverage: 23 HAVE / 345 NEW.** HAVE = 20 cities (14 GD via gkmlpt + Suzhou, Wuhan,
  Hangzhou, Qingdao, Jinan, Shenyang) + 3 municipalities (Beijing, Shanghai, Chongqing).
  **天津 Tianjin is the one NEW municipality** (but its portal is dead — Tier F above).
- **Sampled reachability (25 representative NEW cities from our NYC IP): ~28% crawlable
  / ~72% blocked** (7 reachable · 3 WAF · 15 blackhole). So of the 345 NEW cities,
  order-of-magnitude **~90 are directly crawlable** (no proxy), the rest are proxy-gated.
  This is the **long tail** — low citation-demand per city; pick targets by policy
  relevance, not en masse.
- **Domain caveat:** `candidate_domain` in the CSV is the `www.<pinyin>.gov.cn` heuristic
  and is WRONG for abbreviation-domain cities (石家庄=sjz, 西安=xa, 大连=dl, 南昌=nc,
  昆明=km, 贵阳=gy, 长春=cc, 宁波=nb, 兰州=lz, 东莞=dg, 厦门=xm, …). The 25 sampled rows
  carry VERIFIED domains; 51 autonomous-prefecture/county rows are flagged `(verify)`;
  343 rows are `untested`. Verify a city's real portal (byte-check) before crawling it.

---

## Bottom line

- **Actionable now (no proxy):** 3 provinces + 1 central body — **Qinghai, Yunnan,
  Xinjiang, NEAC** (Tier B).
- **The one lever for the rest:** a **residential-CN proxy** unlocks Tier C (~5 central
  ministries + ~13 provinces + the GD-city + most-city long tail) in a single move — far
  more than any per-site crawler. Tier D (MOHRSS) additionally needs an anti-bot fetch;
  Tier E needs bespoke search-API crawlers.
- **HTTP 200 ≠ reachable.** Always byte-check + follow redirects (this doc's method).
