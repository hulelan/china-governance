# ReConnect China — source registry vs. our coverage

**Extracted 2026-09-02.** Read-only reconnaissance of reconnectchina.org (the
EU-funded University of Vienna database, ~6.68M machine-translated Chinese
official documents). Goal: enumerate the **sources** (issuer institutions +
region taxonomy) it draws from, and flag which ones we do *not* yet crawl.

We took only the source *enumeration*, not document contents. Method: one page
load of the public SPA + reading its already-loaded client JS bundle
(`/assets/search-CdkYhrVp.js`), where the entire facet taxonomy is hard-coded.

---

## How ReConnect exposes data (can we pull programmatically?)

- **It is a React-Router SPA** served from `reconnectchina.org` (canonical host
  `reconnectchina.univie.ac.at` 301-redirects to it). Routes: `home`, `search`,
  `account`, `content-page`, `health`.
- **There IS a JSON API, but it is gated.** The document search calls
  `POST /fetch/search/more/` (found verbatim in the bundle). `robots.txt`
  disallows `/fetch/search/`, `/fetch/recent/`, `/recent/`, `/search/` and asks
  scrapers to **request API access by email** instead ("faster, more reliable").
  `GET /fetch/search/` with no params returns **404** (endpoint exists, needs a
  POST body).
- **The full document search requires a (free) login account** — the `/search`
  page shows "Account needed for text search." So the corpus itself is *not*
  openly pullable; programmatic access = email them for an API key. We did **not**
  register an account.
- **The facet taxonomy, by contrast, is fully public** — it is compiled into the
  JS bundle as plain arrays, which is how everything below was recovered. No
  scraping of documents was involved.
- ReConnect does **not** expose the official government source URL per issuer in
  the frontend facets — only the Chinese institution/region name. (Individual
  documents carry a source link, but that is behind the login-gated search, which
  we did not touch.) Official URLs in the tables below are therefore **inferred
  from our own knowledge of the .gov.cn portals**, not taken from ReConnect.

---

## Taxonomy (verbatim from the bundle)

### 29 policy topic categories (English button labels, verbatim)

`Agriculture, Awards, Commerce, Credit, Culture, Diplomacy, Education,
Emergency, Energy, Environment, Finance, Government, Health, Housing,
Infrastructure, Legal, Military, Party, Personnel, Safety, Security, Sports,
Tech, Tourism, Trade, Transport, Veterans, Weather, Welfare`

(The bundle's internal default-selected set `K2` omits `GOVERNMENT` and `LEGAL`,
so 27 are pre-checked; the UI offers all 29.)

### 5 document/item types (`Vn`)

`law/decree, regulation, notice/announcement, opinion/plan, news/report`

### Region taxonomy — 3 location tiers (`locationTypes = ["centre","provinces","cities"]`)

ReConnect models an issuer as **one administrative unit at one of three tiers**:

- **centre** → 30 named central bodies (the `k3` array — full list + mapping below).
- **provinces** → 31 provincial-level units (`w3`): the 31 mainland province-level
  divisions (excludes Hong Kong / Macau / Taiwan, which appear only in the city tier).
- **cities** → ~335 prefecture-level cities (`b3`) **+** 4 direct-controlled
  municipalities (`Bn`: 上海市, 北京市, 天津市, 重庆市) **+** 29 province-directly-
  administered county-level & special units (`F3`: the Xinjiang XPCC cities
  石河子/阿拉尔/图木舒克/五家渠/北屯/铁门关/双河/可克达拉/昆玉/胡杨河/白杨,
  Hainan counties, Hubei 天门/仙桃/潜江/神农架, 河南济源, plus 香港特别行政区 /
  澳门特别行政区).

**Key structural finding:** ReConnect's issuer granularity is **coarse** — a
province-level doc is attributed to the *province*, a city doc to the *city*.
There is **no per-department facet** (no "广东省工信厅" as a separate issuer). Our
corpus is the opposite: narrower in region breadth but **deeper**, crawling
individual provincial/municipal *departments*. So the gap below is one of
*breadth* (more regions), not depth.

---

## Cross-reference against our `sites` table

### Tier 1 — the 30 CENTRE issuers (`k3`)  →  20 HAVE / 10 NEW

| # | CN name | EN | Our site | Status |
|---|---------|----|----------|--------|
| 1 | 中华人民共和国中央人民政府 | State Council / central gov portal | `gov` | HAVE |
| 2 | 全国人民代表大会 | NPC | `npc` (laws DB) | HAVE (approx) |
| 3 | 最高人民法院 | Supreme People's Court | `spc` | HAVE |
| 4 | 中国人民银行 | PBoC | `pbc` | HAVE |
| 5 | 交通运输部 | Ministry of Transport | `mot` | HAVE |
| 6 | 人力资源和社会保障部 | MOHRSS | — | **NEW** |
| 7 | 住房和城乡建设部 | MOHURD | — | **NEW** |
| 8 | 公安部 | Ministry of Public Security | — | **NEW** |
| 9 | 农业农村部 | MARA | `mara` | HAVE |
| 10 | 司法部 | Ministry of Justice | `moj` | HAVE |
| 11 | 商务部 | MOFCOM | `mofcom` | HAVE |
| 12 | 国家卫生健康委员会 | National Health Commission | — | **NEW** |
| 13 | 国家发展和改革委员会 | NDRC | `ndrc` | HAVE |
| 14 | 国家安全部 | Ministry of State Security | — | **NEW** (no public policy portal) |
| 15 | 国家民族事务委员会 | State Ethnic Affairs Commission | — | **NEW** |
| 16 | 国防部 | Ministry of National Defense | — | **NEW** |
| 17 | 外交部 | MFA | `mfa` | HAVE |
| 18 | 审计署 | National Audit Office | `cnao` | HAVE |
| 19 | 宣传部 | CPC Publicity (Propaganda) Dept | — | **NEW** (no standalone portal) |
| 20 | 工业和信息化部 | MIIT | `miit` | HAVE |
| 21 | 应急管理部 | MEM | `mem` | HAVE |
| 22 | 教育部 | MOE | `moe` | HAVE |
| 23 | 文化和旅游部 | MCT | `mct` | HAVE |
| 24 | 民政部 | Ministry of Civil Affairs | — | **NEW** |
| 25 | 水利部 | MWR | `mwr` | HAVE |
| 26 | 生态环境部 | MEE | `mee` | HAVE |
| 27 | 科学技术部 | MOST | `most` | HAVE |
| 28 | 自然资源部 | Ministry of Natural Resources | — | **NEW** |
| 29 | 财政部 | MOF | `mof` | HAVE |
| 30 | 退役军人事务部 | Ministry of Veterans Affairs | `mva` | HAVE |

**Note:** ReConnect's centre facet is only these 30 core bodies. **We already
crawl ~50 central sites**, including many agencies ReConnect does *not* separately
enumerate (CAC, SAMR, NDA, CNIPA, NEA, NBS, SAFE, SASAC, CSRC, NATCM, NHSA,
chinatax, CMA, CNSA, CAAC, NIA, SFA, SAAC, NCHA, TC260, SPP, CPPCC, chinapeace,
CAS, NSFC, SASTIND, SPB, NRTA). So at the centre our coverage is *broader by
agency*; the only real gaps are the 10 big line ministries below.

#### The 10 NEW central ministries (inferred official portals)

| CN | EN | Inferred portal |
|----|----|-----------------|
| 公安部 | Ministry of Public Security | https://www.mps.gov.cn |
| 住房和城乡建设部 | MOHURD (housing/construction) | https://www.mohurd.gov.cn |
| 人力资源和社会保障部 | MOHRSS (HR & social security) | http://www.mohrss.gov.cn |
| 国家卫生健康委员会 | National Health Commission | http://www.nhc.gov.cn |
| 民政部 | Ministry of Civil Affairs | https://www.mca.gov.cn |
| 自然资源部 | Ministry of Natural Resources | https://www.mnr.gov.cn |
| 国家民族事务委员会 | State Ethnic Affairs Commission | https://www.neac.gov.cn |
| 国防部 | Ministry of National Defense | http://www.mod.gov.cn |
| 宣传部 | CPC Publicity Dept | (no standalone .gov portal; via 12371 / 中国文明网) |
| 国家安全部 | Ministry of State Security | (no public policy portal) |

The first 6 are high-value, high-volume policy issuers worth crawling.

### Tier 2 — the 31 PROVINCES (`w3`)  →  14 HAVE / 17 NEW

Full `w3` list: 上海, 云南, 内蒙古, 北京, 四川, 吉林, 天津, 宁夏, 安徽, 山东,
江西, 山西, 广东, 广西, 新疆, 江苏, 福建, 河北, 河南, 浙江, 海南, 湖北, 湖南,
甘肃, 西藏, 贵州, 辽宁, 重庆, 陕西, 青海, 黑龙江.

**HAVE (14):** 北京, 上海, 江苏, 浙江, 广东, 黑龙江, 福建, 辽宁, 宁夏, 山东,
西藏, 湖南, 吉林, 重庆 (province portals + departments).

**NEW (17), with inferred portals:**

| CN | EN | Inferred portal |
|----|----|-----------------|
| 四川省 | Sichuan | https://www.sc.gov.cn |
| 河南省 | Henan | https://www.henan.gov.cn |
| 河北省 | Hebei | http://www.hebei.gov.cn |
| 湖北省 | Hubei (we have Wuhan city only) | https://www.hubei.gov.cn |
| 安徽省 | Anhui | https://www.ah.gov.cn |
| 云南省 | Yunnan | http://www.yn.gov.cn |
| 广西壮族自治区 | Guangxi | http://www.gxzf.gov.cn |
| 新疆维吾尔自治区 | Xinjiang | http://www.xinjiang.gov.cn |
| 陕西省 | Shaanxi | http://www.shaanxi.gov.cn |
| 山西省 | Shanxi | http://www.shanxi.gov.cn |
| 江西省 | Jiangxi | http://www.jiangxi.gov.cn |
| 贵州省 | Guizhou | https://www.guizhou.gov.cn |
| 甘肃省 | Gansu | https://www.gansu.gov.cn |
| 海南省 | Hainan | https://www.hainan.gov.cn |
| 青海省 | Qinghai | http://www.qinghai.gov.cn |
| 天津市 | Tianjin (municipality) | http://www.tj.gov.cn |
| 内蒙古自治区 | Inner Mongolia | https://www.nmg.gov.cn |

### Tier 3 — the ~335 CITIES (`b3` + `Bn` + `F3`)  →  ~20 HAVE / ~348 NEW

ReConnect covers **every** prefecture-level city nationally. We cover ~20:
Guangzhou, Shenzhen + 13 other Guangdong cities (Huizhou, Yangjiang, Shantou,
Shanwei, Shaoguan, Jiangmen, Jieyang, Heyuan, Yunfu, Zhaoqing, Zhongshan,
Zhuhai), Suzhou, Wuhan, Hangzhou, Qingdao, Jinan, Shenyang. The remaining
~315 prefecture cities (plus the 29 special county-level units) are all NEW.
This is the single largest breadth gap, but the lowest priority per-unit — it is
long-tail municipal coverage; pick targets by policy relevance, not en masse.
The full 335-city list is recoverable from the same bundle array `b3` if needed.

---

## Coverage-gap summary (ranked)

| Gap | Count NEW | Priority |
|-----|-----------|----------|
| Central line ministries | 10 (6 crawlable) | **HIGH** — national policy issuers |
| Provinces | 17 | **MEDIUM** — big provinces (Sichuan/Henan/Hebei/Hubei/Anhui) first |
| Prefecture cities | ~348 | LOW — long tail, pick by relevance |

### Top ~15 NEW sources (highest-value coverage gaps)

1. 公安部 Ministry of Public Security — https://www.mps.gov.cn
2. 住房和城乡建设部 MOHURD — https://www.mohurd.gov.cn
3. 人力资源和社会保障部 MOHRSS — http://www.mohrss.gov.cn
4. 国家卫生健康委员会 National Health Commission — http://www.nhc.gov.cn
5. 民政部 Ministry of Civil Affairs — https://www.mca.gov.cn
6. 自然资源部 Ministry of Natural Resources — https://www.mnr.gov.cn
7. 四川省 Sichuan (province) — https://www.sc.gov.cn
8. 河南省 Henan (province) — https://www.henan.gov.cn
9. 河北省 Hebei (province) — http://www.hebei.gov.cn
10. 湖北省 Hubei (province) — https://www.hubei.gov.cn
11. 安徽省 Anhui (province) — https://www.ah.gov.cn
12. 云南省 Yunnan (province) — http://www.yn.gov.cn
13. 广西壮族自治区 Guangxi — http://www.gxzf.gov.cn
14. 新疆维吾尔自治区 Xinjiang — http://www.xinjiang.gov.cn
15. 天津市 Tianjin (municipality) — http://www.tj.gov.cn

**Caveat:** the `.gov.cn` URLs are the well-known official portals from our own
knowledge; ReConnect's facets expose only the Chinese names, not source URLs.
Verify each portal before building a crawler.
