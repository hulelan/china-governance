# The RMB in the corpus: strong fiscal record, near-absent monetary record, and one real signal

*Coverage-and-method memo, 2026-10-08. Written to answer a direct question — what do we hold on
how the RMB is managed relative to other currencies — and to record the three measurement traps
that corrupt the obvious way of asking it. The short answer: we can measure **attention** to the
RMB against the dollar in the administrative record, and we cannot yet study **how** it is managed,
because the two managing institutions are the two thinnest sites in the corpus. Companion to
`rmb-coverage`'s sibling finding in `patient-capital-cascade.md` (state capital) and to
`source-access-map.md` (what is reachable).*

---

## 1. Institutional coverage: the managers are missing

> **SUPERSEDED 2026-10-09 for the PBC specifically.** This section's central claim — that the
> monetary apparatus was the corpus's biggest institutional hole at **31 PBC documents** — was
> correct and is now fixed. `crawlers/pbc.py` had its 沟通交流 section capped at 40 pages, and
> CLAUDE.md's documented historical backfill (`--max-pages 411`) **did not work** because the code
> read `min(max_pages, cap)` so the cap always won. With an explicit `--max-pages` now overriding
> the cap, the 411-page walk listed **5,558** documents against 494 before, and **pbc holds 6,099
> documents** (规范性文件 430, 部门规章 111, 沟通交流 5,558), all with body text.
>
> Still missing, so the section's shape holds even where its PBC number does not: **SAFE 22**, and
> **NFRA absent entirely**. And a defect this section could not have seen: **every pbc, chinatax,
> csrc, safe and spp document has `date_written = 0`** — those crawlers populate only
> `date_published` — so until `panel.py` was fixed the same day, these institutions were invisible
> to every time series regardless of how many documents we held.



| body | docs | with body | span |
|---|---|---|---|
| 国家税务总局 (chinatax) | 5,018 | 4,778 | 1984-09 – 2026-09 |
| 财政部 (mof) | 3,395 | 3,394 | 2005-04 – 2026-10 |
| 证监会 (csrc) | 272 | 272 | 2008-11 – 2026-09 |
| **中国人民银行 (pbc)** | **31** | 31 | **2025-12 – 2026-09** |
| **国家外汇管理局 (safe)** | **22** | 22 | **2024-12 – 2026-09** |

Plus roughly 1,000 provincial 财政厅 / 财政局 documents (gdczt 299, fj_czt 283, nx_czt 129, …).
There is **no 国家金融监督管理总局 (NFRA)**, no CBIRC, no CFETS, no interbank-market body.

So the fiscal apparatus is well covered and the **monetary apparatus is not covered at all**: 53
documents between the central bank and the foreign-exchange regulator, none older than
December 2024.

The *legal* framework is held, through the national-laws tier, and it is well cited:
外汇管理条例 (77 citing documents), 银行业监督管理法 (72), 商业银行法 (50), 外资银行管理条例 (48),
中国人民银行法 (46), 人民币管理条例 (33). But that tier is **metadata-only** — `crawlers/npc.py`
stores an empty body by design — so we hold these statutes' titles and dates and not a word of
their text.

### The gap is a crawler bound, not a vantage bound

Probed from the droplet's NYC IP, 2026-10-08, byte-checked per `source-access-map.md`'s method:
`pbc.gov.cn` returns 141,326 bytes, `safe.gov.cn` 102,128, and the PBC 条法司 section index 54,286.
These are real pages, not the ~1KB anti-bot shells that block MIIT. **The sites are reachable.**

The crawler walks **page 1 only**. Section 144957 (部门规章) shows 7 article links on page 1 and
3581332 (规范性文件) shows 20 — which is essentially the 31 documents we hold, and explains the
2025-12 floor. `index_1.html` and `index_2.html` return 404, so it is not the common
`index_N.html` dialect; the pager is JS-driven and needs a dialect of its own. The
中国人民银行令 series runs back to the 1990s.

**Careful with the probe itself:** without `curl -L` those section URLs return a **138-byte
redirect stub with HTTP 200**. That is the exact failure `source-access-map.md` warns about, and
it is why a reachability sweep must byte-check and follow redirects.

### What the citation graph says is missing

Ranked by distinct citing documents, the unresolved monetary references are all PBC/CBRC
部门规章 — the 16% "ministerial 令" wall named in CLAUDE.md:

| instrument | citers |
|---|---|
| 人民币银行结算账户管理办法 | 22 |
| 非金融机构支付服务管理办法 | 18 |
| 商业银行服务价格管理办法 | 14 |
| 金融租赁公司管理办法 | 11 |

The second of those is the 2010 rule that created third-party payment licensing, so its absence is
felt by anything touching payments.

---

## 2. Topical coverage: thin but real

Full-text document counts (trigram index, so ≥3 characters):

| term | docs | | term | docs |
|---|---|---|---|---|
| 人民币 | 9,543 | | 本币结算 | 55 |
| 跨境人民币 | 587 | | 汇率形成机制 | 55 |
| 数字人民币 | 469 | | 去美元化 | 44 |
| 人民币国际化 | 237 | | 货币互换 | 29 |
| 资本项目可兑换 | 149 | | 本币互换 | 25 |
| 离岸人民币 | 104 | | 特别提款权 | 16 |
| 自由兑换 | 82 | | 一篮子货币 | 15 |
| 人民币跨境支付系统 | 57 | | | |

And the comparators, which need the **segmented** index (see §4): 美元 8,454 · 外汇 3,468 ·
汇率 1,290 · 欧元 778 · 港元 415 · 日元 360 · 英镑 223 · 卢布 54.

The explicit currency-management vocabulary is **tens of documents**, not thousands. Anything that
requires reading how an exchange-rate or settlement decision was justified is out of reach now.

---

## 3. The one real signal, and the structural finding

> **RE-BASED 2026-10-09, and the "flat" half is WITHDRAWN.** Two things changed on the same day.
> The PBC crawler's cap bug was fixed, taking **pbc from 31 to 6,099 documents** — so §1's
> "the managers are missing" is itself superseded, and the central bank is now in the panel for the
> first time. And `panel.py` was keying on `documents.date_written`, which **whole institutions never
> populate** (pbc 6,099 of 6,099, chinatax 5,018 of 5,018, csrc 272 of 272), so the panel used below
> structurally could not contain them. On an effective date (written, else published) the default
> panel is **21 sites including pbc**, with a 2013 denominator of 4,053 rising to 8,950 by 2023.
>
> | | 2013 | 2017 | 2023 | 2026 |
> |---|---|---|---|---|
> | 美元 panel share | 2.71% | 0.93% | 0.53% | **0.33%** |
> | 人民币 panel share | 5.95% | 5.04% | 3.49% | 5.58% |
> | **美元 : 人民币** | **0.455** | **0.185** | **0.152** | **0.059** |
>
> **The ratio does not sit flat after 2017 — it keeps falling, another ~3x.** 美元 is SIGN_FLIP with
> panel-share ρ **−0.952**, close to perfectly monotonic, while 人民币 is roughly flat
> (ρ −0.538, with a 2023 trough and recovery). So the phenomenon is not a decline in currency talk;
> it is **dollar-specific reference being progressively displaced while RMB reference holds steady**.
>
> **And the comparison is bilateral, not multilateral — which is the sharper finding.** Every other
> currency is THIN on the same panel: **欧元 16, 港元 8, 日元 2, 本币 20** panel documents, against
> 美元's **684**. The dollar has roughly **43x** the euro's presence and **340x** the yen's. So the
> dollar's share falls 8x and **no other currency rises to replace it**. A basket story would show
> euro or yen share climbing as the dollar's fell; they do not register at all. This is the retreat
> of a single reference point, not diversification of reference.
>
> 汇率 (0.37% → 0.24%, ρ −0.451, trough 0.16% in 2019) and 跨境人民币 (0.67% → peak 1.63% in 2015 →
> trough 0.23% in 2019 → 0.59% in 2022) are both SIGN_FLIP and both noisy; neither carries a trend
> this memo would state. Raw counts for all four rise, which is why §4's traps matter: the 2026 raw
> 美元 count is **4,858** against a panel count of **11**.



### Signal: the dollar's relative salience halved, 2013-2017

On a **fixed 17-site panel** (sites with ≥40 bodied documents in every year 2012-2024: bj,
chinatax, gd, gov, gz, hlj, huizhou, jiangmen, jieyang, js, mof, sh, shaoguan, suzhou, sz_gazette,
zhongshan, zhuhai), the ratio of documents mentioning 美元 to documents mentioning 人民币:

| 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2019 | 2021 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.68 | 0.70 | 0.46 | 0.33 | 0.52 | 0.31 | 0.32 | 0.32 | 0.36 | **0.24** | 0.31 |

**It halves between 2013 and 2017 and then sits flat for eight years.** Cross-border-RMB mentions
peak in 2015 (51, against ~22 before and ~30 after) rather than trending upward.

Two honest qualifications. The panel is Guangdong-heavy, and the dollar enters local documents
largely through FDI and trade figures, so part of the fall may be local reporting re-denominating
rather than policy changing. And the break's timing brackets the August 2015 exchange-rate regime
change and the SDR-inclusion campaign, which is suggestive but is not identification.

### Structure: currency management arrives as zone-and-plan policy

The most-cited documents carrying 跨境人民币 / 本币结算 / 人民币国际化 are not monetary
instruments. They are plans and zone charters:

粤港澳大湾区发展规划纲要 (365 citers) · 十五五规划建议 (209) · 二十届三中全会决定 (197) ·
深圳先行示范区意见 (139) · 横琴粤澳深度合作区方案 (47) · 要素市场化配置意见 (47) ·
广东自贸区总体方案 (28) · 长三角一体化纲要 (29) · 成渝双城经济圈纲要 (29)

By site the lexicon sits in `gov` (207), `guancha` (134, commentary), `sz_gazette` (77), `gd` (70),
`sh` (48), `gz` (41), `mofcom` (36). **PBC and SAFE are not in the top fourteen.**

So in the documentary record, RMB internationalization is **delegated to special zones and written
into plans** rather than promulgated as monetary regulation. That is a mechanism-level claim of the
kind this volume is for, and it is consistent with what `patient-capital-cascade.md` found on state
capital: the financial-policy vocabulary that matters is built in named places first.

It is also, in part, an artifact of *which* institutions we hold — the zone-and-plan reading is
what you see when the central bank is 31 documents. Both halves of that sentence are true, and the
fix in §1 is how to find out which dominates.

---

## 4. Three measurement traps, recorded because each returns a clean zero

Each of these produced a confident wrong answer during this memo, and none raised an error.

1. **`美元` returns 0 from the trigram index.** `doc_search` is `tokenize='trigram'`, which needs
   **3 characters**; 美元 is two. 人民币 is three and works, so a side-by-side comparison of the
   two silently reported the dollar as absent from a corpus containing it 8,454 times. This is the
   project's named *length-floor* bug shape (CLAUDE.md), now in the search layer. Use
   `doc_search_seg` for any 1-2 character term.
2. **`跨境人民币` returns 0 from the segmented index.** `doc_search_seg` is jieba-segmented, so the
   compound is stored as 跨境 + 人民币 and never matches as a phrase token. **The two indexes are
   complementary and neither covers both cases:** trigram for compounds, segmented for short words.
   A per-year series built on the wrong one shows a flat zero that looks like a real absence.
3. **The raw year series reverses the trend.** Uncontrolled, the 美元:人民币 ratio *rises* to 1.72
   by 2026 — because 2026 holds 98,402 documents against 2024's 29,269, as newly-crawled sites
   dump recent material. The fixed-site panel in §3 **reverses the sign**. Any currency series on
   this corpus must be built on a fixed panel.

---

## What would change the answer

1. **Page the PBC crawler** (§1) — the site is reachable and the archive runs to the 1990s. This
   is the single highest-value fix and it is a dialect, not a vantage.
2. **SAFE**, if it shares the CMS dialect. 外汇 is the densest of the management terms (3,468
   documents mention it) and its regulator holds 22.
3. **NFRA / 金融监管总局**, which does not exist in the corpus at all.
4. The 部门规章 wall in §1's table, which is the same wall the AI memos hit, and the same answer
   (a residential or HK vantage, or 北大法宝).
