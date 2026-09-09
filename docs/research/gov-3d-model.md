# A 3-Dimensional Model of the Chinese Party-State

**Purpose.** Measure and complete our crawl coverage systematically. Coverage is
not a flat map of provinces. It is a three-axis volume, and "how much of China's
government do we hold" only has a defensible answer once every governing body has
a canonical row with a URL slot and a coverage status.

- **Companion data file:** [`gov-entities-schema.yaml`](gov-entities-schema.yaml)
  — the row shape plus the full central tree (Dim C) and the department taxonomy
  backbone (Dim B) as concrete rows.
- **Grounding:** `docs/working/china-admin-divisions.csv` (Dim A enumeration),
  `docs/working/source-access-map.md` (reachability tiers), `data/structure.yaml`
  and `data/government_org_map.json` (the earlier org charts this supersedes),
  `docs/working/coverage-sites-snapshot.tsv` (what we crawl now).
- **Last authored:** 2026-09-09.

---

## 1. The three dimensions

The party-state is a lattice. Any governing body sits at the intersection of
three independent axes.

### Dim A — geographic / administrative depth (the vertical)

The nested territorial hierarchy. Each level is a layer of government that
replicates the one above it at smaller scale:

| Level | Count | Enumerated in our data? |
|---|---|---|
| Central | 1 | yes |
| Provincial (省/自治区/直辖市/特别行政区) | 34 | yes (`china-admin-divisions.csv`) |
| Prefecture (地级市/自治州/地区/盟) | ~333 | yes (~360 rows incl. special county-level) |
| County (区/县级市/县/自治县) | ~2,844 | no (not yet enumerated) |
| Township (街道/镇/乡) | ~38,000 | no (rarely owns a portal) |

This is the axis we have historically thought of as "coverage" — the map of
provinces and cities. It is one axis of three.

### Dim B — functional / department depth (the horizontal, replicated)

*Within* each geographic unit sits a replicated set of departments — 发改委,
财政, 教育, 生态环境, 公安, and ~35 others. The set is not arbitrary: after the
2018–2019 local-government reforms, each unit's departments were aligned to
mirror (对口) the central ministries, so a provincial 生态环境厅 answers
functionally to 生态环境部, a municipal 生态环境局 answers to the provincial
厅, and so on down. This is the **tiao–kuai** (条块) structure:

- **kuai (块)** — the horizontal line: the local government leads the department
  (personnel, budget, buildings).
- **tiao (条)** — the vertical line: the counterpart body one level up sets
  policy and professional direction.

A few systems are **tiao-dominant** (staffed and funded from above rather than
locally): 公安 partially, plus 税务, 海关, 国安, and the 人民银行 branch network.
Those show up as local *branches* of a central system, not as local departments.

The department set is the reusable Dim B backbone. It is defined once (see §3)
and stamped onto every geographic unit.

### Dim C — the central government's own expansive tree

The central level is not one node. It is a deep tree in its own right, and it has
lanes the local levels do not replicate:

1. **State Council executive lane** — 组成部门 (26 constituent ministries) →
   直属特设机构 (SASAC) → 直属机构 (customs, tax, SAMR, NFRA, CSRC…) → 直属事业单位
   (Xinhua, CAS, DRC…) → 部委管理的国家局 (NEA, NDA, CNIPA, SAFE, NMPA… — bureaus
   that hang off a parent ministry).
2. **Party lane** — 中办, 中组部, 中宣部, 统战部, 政法委, plus the commission
   offices that increasingly outrank their state counterparts (中央网信办 = CAC,
   中央金融委办, 中央科技委, 中央社会工作部 — the last three created in 2023).
3. **Legislative / consultative** — NPC + Standing Committee, CPPCC.
4. **Judicial / procuratorial / supervisory** — 最高法 (+ IP Tribunal), 最高检,
   国家监委 (co-located with CCDI since 2018).
5. **Armed-force lane** — 中央军委 → 武警 → 中国海警局, plus 国防部 as the public
   window. This lane sits under the CMC, **not** the State Council.
6. **Mass organizations** — 全国总工会, 共青团, 全国妇联, 中国科协.

Dim C carries reorganization history that the model must track: bodies merged,
renamed, and moved between lanes (银保监会 → 金融监管总局 in 2023; 海警局 →
武警/CMC in 2018; 环保部 → 生态环境部 in 2018). Every such change is a
`reorg_note` + `predecessor_ids` link in the schema, so a citation to a defunct
body still resolves to its successor.

---

## 2. How the dimensions compose

A concrete governing body is a point in the A×B×C volume. Two composition rules
cover every case:

- **Local body = geographic unit × department (Dim A × Dim B).**
  `广东省 · 生态环境厅` = (Guangdong, provincial) × (生态环境, mirrors MEE).
  `广东省 · 深圳市 · 生态环境局` = one level deeper on Dim A, same Dim B slot.
  Its **tiao** parent is the province 厅 (and ultimately 生态环境部); its **kuai**
  parent is the Shenzhen municipal government.

- **Central body = a node in the Dim C tree**, optionally with a bureau/sub-unit
  child. `国家发改委` → `国家能源局` (a 国家局 under it). `最高法` → `知识产权法庭`.

- **Sub-units (直属单位 / 处 / 所).** Every department and ministry has its own
  internal tree — research institutes, affiliated centers, functional 处. These
  are a fourth level of depth *inside* Dim B and Dim C. We model them as
  `body_type: sub_unit` rows with `parent_id` set to their department, and we
  enumerate them only where they publish independently (see §5a — they have
  **independent reachability** from their parent).

The unifying claim: **one canonical entity → one row → one `official_url` → one
`coverage_status`.** The schema (`gov-entities-schema.yaml`) is that table. Dim C
and the Dim B backbone are hand-listed there because they are finite and stable.
The Dim A × Dim B cross-product is *generated*, not hand-listed (§4).

---

## 3. The standard department taxonomy (Dim B backbone)

This is the reusable set that replicates across geographic units. It is fully
populated as template rows in `gov-entities-schema.yaml → dept_taxonomy`
(~44 templates). Naming convention: **厅/委** at province rank, **局** at
prefecture and county rank; 委员会 stays 委员会.

**Core departments mirroring the 组成部门 (present province → county):**

| Dept (province form) | Mirrors (Dim C) | Notes |
|---|---|---|
| 发展和改革委员会 | NDRC | macro planning |
| 教育厅 | MOE | |
| 科学技术厅 | MOST | |
| 工业和信息化厅 | MIIT | |
| 民族宗教事务委员会 | NEAC | prefecture floor |
| 公安厅 | MPS | partly tiao-dominant, runs to township |
| 国家安全厅 | MSS | tiao-dominant |
| 民政厅 | MCA | |
| 司法厅 | MOJ | |
| 财政厅 | MOF | |
| 人力资源和社会保障厅 | MOHRSS | |
| 自然资源厅 | MNR | |
| 生态环境厅 | MEE | |
| 住房和城乡建设厅 | MOHURD | |
| 交通运输厅 | MOT | |
| 水利厅 | MWR | |
| 农业农村厅 | MARA | |
| 商务厅 | MOFCOM | |
| 文化和旅游厅 | MCT | |
| 卫生健康委员会 | NHC | |
| 退役军人事务厅 | MVA | |
| 应急管理厅 | MEM | |
| 审计厅 | CNAO | |
| 人民政府外事办公室 | MFA | office, not 厅 |

**Departments mirroring 直属/特设机构 and 国家局 (province + prefecture, some to county):**
市场监督管理局 (SAMR), 国有资产监督管理委员会 (SASAC), 统计局 (NBS),
医疗保障局 (NHSA), 体育局 (GAS), 广播电视局 (NRTA), 地方金融监督管理局 (NFRA),
政务服务和数据管理局 / 大数据局 (NDA), 林业和草原局 (Forestry Admin),
能源局 (NEA), 药品监督管理局 (NMPA), 知识产权局 (CNIPA), 信访局 (Xinfang),
机关事务管理局 (GGJ).

**Vertical (tiao-dominant) systems — appear as local branches:**
税务局 (STA), 海关 (Customs), 人民银行分行 (PBOC).

**Party-side local organs (mirror the Dim C party lane at each level):**
委办公厅, 组织部, 宣传部, 统战部, 政法委, 网信办, 纪委监委.

The department count per unit shrinks as you descend: a province carries ~40, a
prefecture ~33, a county ~28. Naming also drifts at the margins — the NDA-mirror
in particular is called 大数据局 / 数据局 / 政务服务和数据管理局 depending on the
province, which the discovery step (§5) must treat as aliases.

**Empirical anchor.** We already hold real Dim B department subdomains for several
provinces — Fujian (`fj_*`, ~38 departments), Guangdong (`gd*`), Ningxia (`nx_*`),
Chongqing (`cq_*`), Xizang (`xz_*`), Jilin/Liaoning (`jl_*`/`ln_*`). Cross-checking
the taxonomy above against those existing site_keys is the fastest way to validate
and correct the template list before generating the full cross-product.

---

## 4. The central tree (Dim C) and the cross-product math

The full Dim C tree is enumerated as concrete rows in
`gov-entities-schema.yaml → central_tree` — **~90 bodies**: 26 constituent
departments, ~12 directly-subordinate agencies + special agency, ~20 national
bureaus, ~12 party organs, NPC + CPPCC, 3 judicial/procuratorial, 4 military-lane
bodies, 4 mass organizations, and the standards/statistics bodies. Each carries a
`reorg_note` and, where a body was created by merger, `predecessor_ids` linking to
what it absorbed (e.g. `nfra.predecessor_ids = [cbirc]`,
`cpc_finance_office.predecessor_ids = [fsdc]`).

Adding the long tail of 直属单位 / 研究院 / functional 处 under each ministry would
push Dim C past several hundred, but those are enumerated only where they publish
independently.

**Cross-product implied by generation** (entity counts, not website counts):

| Level | Units (Dim A) | × depts (Dim B) | ≈ entities |
|---|---|---|---|
| Central | 1 | (tree) | ~90 hand-listed |
| Provincial | 34 | ~40 | ~1,360 |
| Prefecture | ~333 | ~33 | ~11,000 |
| County | ~2,844 | ~28 | ~80,000 |
| Township | ~38,000 | few | 100,000+ |

**The crucial distinction: entities ≠ websites.** Below prefecture, most
departments do not run an independent portal; they publish under their county
government's 部门 / 信息公开 sections. So the count of distinct *crawlable sites*
is far smaller than the ~90k+ entity count — on the order of **~3,200 general
government portals** (central + 34 province + ~333 prefecture + ~2,844 county)
plus **a few thousand department subdomains** that exist mainly at provincial and
big-city level. The realistic crawl-target universe is **~5,000–8,000 live
sites**, and the entity table's job is to tell us which of those 5–8k we hold and
which we are missing — while still recording the ~90k entities so a citation to
any of them resolves to a row.

---

## 5. Discovery strategy — finding the complete set of live sites

Two methods, sequenced by yield per unit of effort. The entity table (§2) is both
the input (what to look for) and the output (where results land).

### 5a. Method 1 — URL-per-entity construction + verification

For every entity row with `official_url = null`, construct candidate URLs from
naming conventions, then verify by content, not status code.

**Domain construction rules for `.gov.cn`:**

- Central bodies use a stable acronym/pinyin under `.gov.cn`: `ndrc`, `mof`,
  `samr`, `mee`, `cnipa`. These are already known and mostly filled.
- Province portals: `www.<province>.gov.cn` — but abbreviation domains are common
  and the pinyin heuristic is WRONG for many (`sc`=四川, `nmg`=内蒙古, `jl`=吉林,
  `nx`=宁夏, `zj`=浙江). Use the verified list, not the heuristic.
- City portals: `www.<citypinyin>.gov.cn`, again with heavy abbreviation
  (`sjz`=石家庄, `xa`=西安, `dl`=大连, `nb`=宁波, `xm`=厦门, `dg`=东莞). The
  `candidate_domain` column in `source-map-cities.csv` is the naive heuristic and
  is flagged wrong for these — verify before trusting.
- **Department subdomains** hang off the parent geographic domain in two dialects:
  `<dept>.<place>.gov.cn` (e.g. `czt.gansu.gov.cn` = 甘肃财政厅) or a path under
  the portal (`<place>.gov.cn/<dept>/`). The subdomain slugs are themselves
  patterned (`fzggw`/`fgw` 发改, `czt` 财政, `kjt` 科技, `sthjt` 生态环境, `jyt`
  教育) — the same slugs our `fj_*`/`gd*`/`cq_*` site_keys already use, so the
  existing crawl set is a ready-made slug dictionary.

**Verification (the non-negotiable part).** HTTP 200 is worthless for CN-gov
sites — a 200 routinely returns a 160-byte redirect stub or a ~1 KB anti-bot
shell. Per `source-access-map.md`:

1. `curl -sL` (follow redirects) on **both** the homepage and a policy section
   (`/zwgk/`, `/zcfg/`), browser UA, `--max-time 8`.
2. `curl -s <url> | wc -c`: **< 2 KB = stub/anti-bot**, tens–hundreds of KB = real.
3. Classify into the reachability tiers (Tier A crawled … Tier F dead) and write
   `coverage_status`.

**Sub-departments have independent reachability from parents** — proven repeatedly:
`www.mof.gov.cn` = 200 but `jrs.mof.gov.cn` = 502; a reachable city portal can
still 403 its `/art/` doc pages. So every subdomain and section must be tested on
its own; never infer a child's status from its parent's.

This method is exhaustive and cheap per URL but only finds URLs that follow the
conventions. It will not surface a body whose portal lives on an unexpected host
(e.g. Beijing 海淀 on the `zyk.bjhd.gov.cn` content subdomain). That is what
Method 2 is for.

### 5b. Method 2 — Google keyword harvesting + match against our inventory

For each entity (and for keyword probes that are not tied to a single entity),
pull the top Google results, keep the official domains, and diff against what we
already hold. This finds the non-obvious hosts and the bodies we never listed.

**Query templates** (run per entity `name_cn`, and per keyword for topical sweeps):

```
"<entity name_cn>" 官网
"<entity name_cn>" 政策文件
"<entity name_cn>" 规范性文件
"<entity name_cn>" 信息公开
"<entity name_cn>" site:gov.cn
```

The owner wants roughly the **top 50 results per query, up to ~50 pages** of
harvest depth. Practical ceiling: Google rate-limits aggressive automated
querying, so batch modestly, rotate, and expect to run this in tranches (it is not
a single overnight job). A search-API (SerpAPI-style) or the browser-driven path
is steadier than scraping the results page directly.

**Filter to official domains.** Keep only hosts matching:

- `*.gov.cn` (government), `*.mil` / `81.cn` / `*.gov.cn` military-lane,
  `*.court.gov.cn` (judicial), and the known party outlets (`12371.cn`,
  `chinapeace.gov.cn`).
- Drop `.com`/`.org` news mirrors **except** the ones we deliberately treat as
  document mirrors (`news.cn`, `people.com.cn`) — flag those as `mirror`, not as a
  primary portal.
- Normalize each hit: strip `http/https`, strip `www.`, lowercase, keep host +
  first path segment.

**Match / dedup against our inventory.** For each surviving official URL:

1. Normalize the same way and check the host against
   `coverage-sites-snapshot.tsv` (494 live site_keys — join on the domain we
   crawl for each key).
2. Check against `reconnect-424-urls.csv` (the 424-institution URL map with a
   `reachable` column already populated) and `source-map-cities.csv`.
3. Bucket the result:
   - **HAVE** — host already crawled → confirm, no action.
   - **KNOWN-UNREACHABLE** — in the reconnect map with `BLACKHOLE/WAF403/STUB` →
     tag `proxy_gated`, defer to the residential-proxy campaign.
   - **UNACCOUNTED** — official domain not in any of our lists → **this is the
     yield.** Byte-check it (Method 1 step 2), add an entity row, set
     `coverage_status`.

The 424-URL map already shows the shape of the answer: of 424 institutions,
~161 REACHABLE / ~16 STUB / ~192 BLACKHOLE / ~24 WAF403 / 5 no-portal. Most of the
"unaccounted-and-reachable" wins will be at the department-subdomain and
prefecture-city level, not the central level (which is nearly complete).

### 5c. Sequence — what to run first

Run in this order, cheapest-and-highest-yield first:

1. **Reconcile the entity table against what we already crawl** (pure local join,
   zero network). Join `coverage-sites-snapshot.tsv` + `china-admin-coverage.csv`
   onto the schema rows to fill `site_key` / `coverage_status`. This immediately
   shows the true gap and prevents re-crawling. **← do this first.**
2. **Method 1 on the finite, high-value set**: the ~90 Dim C bodies still
   `unknown`/blocked, then provincial department subdomains for the ~14 provinces
   whose portal we already reach (construct `<dept>.<province>.gov.cn` from the
   slug dictionary and byte-check). High hit rate, bounded set.
3. **Method 2 keyword harvest** for the residual central bodies and any entity
   Method 1 could not resolve, plus a topical sweep on AI/data keywords. Surfaces
   the non-obvious hosts. Rate-limited, so run in tranches.
4. **Generate + probe the prefecture/county cross-product** last — it is the
   long tail, low citation-demand per unit. Pick targets by policy relevance and
   inbound-citation demand (the citation-crawl-queue), not en masse.

The one lever that dwarfs all per-site work is a **residential-CN proxy**: it
converts the entire `proxy_gated` tier (~5 central ministries + ~13 province
portals + the GD-city and long-tail cities) from blocked to crawlable in a single
move. Discovery tells us *what* is behind that wall; the proxy is *how* we reach it.

---

## 6. What this model changes about how we report coverage

Today we can say "17/34 provinces, 107/361 prefectures." That is a Dim A number.
With the entity table we can instead report a coverage *fraction of the volume*:

- Dim C central tree: crawled / reachable / blocked / no-portal, per lane.
- Dim B depth: for each covered geographic unit, how many of its ~40 departments
  do we actually hold (right now, deep for Shenzhen and a few provinces; shallow
  or portal-only for most).
- Dim A breadth: units with any coverage vs. none.

"Complete coverage" is then a well-defined target: every entity row is either
`crawled`, or explicitly classified as `proxy_gated` / `anti_bot` / `spa_gated` /
`no_portal` with a reason. The gaps stop being invisible.
