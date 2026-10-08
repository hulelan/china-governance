# A 文号 head can belong to two governments — and 22 Wuxi documents were filed in Guangdong

*Read-only measurement on the droplet's `documents.db` (346,955 documents), 2026-10-08.
Nothing was written: the nightly classifier holds the write lock until ~10:00 UTC
2026-10-09. The fix is committed; the rebuild is listed in §7.*

`docs/research/fidelity-wuxi.md` §10 logged, without fixing it, that 22 `wxd_huishan`
documents carry `doc_identity.province = 'gd'` (Guangdong) instead of `js`, and are then
dropped by the same-province gate in `build_diffusion_events` — so they are missing from
every Jiangsu figure in that memo. This note measures the whole ambiguity class the
instance belongs to, corrects two premises about where the fault lies, and settles a
title-percentage discrepancy in the same memo.

---

## 1. The mechanism, located precisely

`derive_province` (A6) reads the issuing locality from the document's own header fields in
priority order: `lead_issuer` → the 文号 agency → `publisher` → the title masthead → the
`localize()` locality → the title head. For the 22 documents:

| field | value | province |
|---|---|---|
| `lead_issuer` | *(none — `doc_issuers.lead_issuer` is NULL for all 22)* | — |
| **文号 agency** | `惠府发〔2023〕12号` → registry `惠府` → **惠州市人民政府** | **gd ← wins** |
| title masthead | `无锡市惠山区人民政府` | js |
| `localize()` locality | `无锡市` (once the masthead corroborates the core) | js |

So the 文号 wins because it is consulted *before* the masthead, and it is wrong because
`issuer_parser.DOCNUM_SUBNATIONAL` lists `惠府`/`惠府办` as 惠州市 while 无锡市惠山区 signs
its documents with exactly the same head (`惠府发`, `惠府办`, `惠府办规`, `惠府规发`).
A 文号 prefix alone cannot disambiguate them.

**Two premises in the hand-off were wrong, and the correction matters for §4.**

1. **`localize()` does *not* return `惠山区`** on these titles. It returns `无锡市`
   (`localize('无锡市惠山区人民政府办公室关于印发惠山区镇（街道）基层法治审核工作办法的通知',
   'wxd_huishan')` → `('惠山区镇街道基层法治审核工作办法', '无锡市', 2)`), because
   `locality_in_core` accepts the core prefix only when the masthead corroborates it. The
   `_loc` path is in any case consulted *after* the 文号, so it never got a turn.
2. **`province_name_of_place('惠山区')` already returned `None`** — it does not "match a key
   `惠`". The keys in that fallback are full division names (`惠州市`), and
   `'惠山区'.startswith('惠州市')` is false. The loose match that actually caused this bug is
   in `docnum_agency`: `prefix.startswith(registry_key)` (`惠府发`.startswith(`惠府`)).
   See §5.

The absence of Wuxi from `geo.DISTRICT_CITY` is still the enabling condition — with no
Wuxi sub-division in any table, the district portals' own localities resolve to nothing, so
the 文号 is the only field left that produces an answer at all. It just produces a *wrong*
answer rather than being merely outranked.

---

## 2. The ambiguity class, measured

87,146 documents carry a 文号. 42,620 carry a prefix the sub-national registry does not
list, ~8,300 carry no parseable prefix, and **36,243 resolve to a registry agency with a
province**. For each of those 36,243, compare that
province against the province of the SITE the document was crawled from
(`build_diffusion_events.province_of`, i.e. the hand table then `geo.province_code_of_site_name`).

| 文号 prefix | registry agency | conflicts | agrees | site(s) |
|---|---|---:|---:|---|
| `惠府办` | 惠州市人民政府办公室 | **15** | 603 | `wxd_huishan` site=js, 文号=gd |
| `惠府办规` | 惠州市人民政府办公室 | **4** | 0 | `wxd_huishan` site=js, 文号=gd |
| `惠府发` | 惠州市人民政府 | **2** | 0 | `wxd_huishan` site=js, 文号=gd |
| `惠府规发` | 惠州市人民政府 | **1** | 0 | `wxd_huishan` site=js, 文号=gd |
| *every other registry prefix (155 of them)* | — | **0** | 36,219 | — |

**22 conflicts in the whole corpus, one prefix family, one site.** 2 further documents sit
on a site `province_of` cannot place, so there is nothing to compare.

**Which reading is correct, and how we know.** Independently of the site: compare the
文号-derived province against the province named by the document's OWN masthead (or title
head) wherever both resolve — 23,183 documents.

| | agree | conflict |
|---|---:|---:|
| 文号 vs own masthead | 23,160 | **23** |

22 of the 23 are these Wuxi documents (masthead `js`, 文号 `gd`), and all 22 titles begin
`无锡市惠山区人民政府(办公室)` — the masthead names the issuing government outright, and
`province_of_name('无锡市惠山区人民政府办公室') == 'js'` with no site and no 文号 involved.
Three witnesses (site, masthead, `localize()`) say Jiangsu; one (the 文号 registry) says
Guangdong. The 23rd conflict is the counter-example that keeps the fix narrow:
`粤府函〔2015〕170号` *福建省人民政府广东省人民政府关于闽粤经济合作区发展规划的批复* — a
jointly-issued 批复 where the masthead names Fujian first but the 文号 is correct, because
the instrument was issued out of the Guangdong registry. A blanket "masthead beats 文号"
precedence change would have broken that one.

**The short heads named in the hand-off produce no conflicts.** Measured:

- `锡` — **no registry key starts with 锡 at all.** Wuxi has no 文号 registry entry. That
  absence has a second consequence, §4.
- `江` — `江府`/`江府办` = 江门市; `江府函` (415 docs) and `江府办函` (353) resolve to gd
  and their sites agree. 0 conflicts.
- `新` — `新政`/`新政办` = 新疆维吾尔自治区. 0 conflicts. Wuxi's districts sign with heads
  the registry lists nowhere (`锡滨政发` on 滨湖区, `梁政发` on 梁溪区, `澄政发` on 江阴市),
  so they never enter this path at all — only 惠山区's borrowed `惠府` head does.
- `常`, `台` — no registry key starts with either.

**Latent, not yet fired.** 42 of the 114 registry keys share their leading character with a
prefecture-level division elsewhere in China: `东府` (东莞市 / 东营市), `中府` (中山市 /
中卫市), `阳府` (阳江市 / 阳泉市), `武政` (武汉市 / 武威市), `晋政` (山西省 / 晋中市 /
晋城市), `河府` (河源市 / 河池市 / 河南 / 河北), `青政` (青海省 / 青岛市), `宁政` (宁夏 /
宁波市 / 宁德市), `新政` (新疆 / 新乡市 / 新余市), `云府`+`云政` (云浮市 / 云南省),
`吉政` (吉林省 / 吉林市 / 吉安市), `黔府` (贵州省 / 黔东南州 …), and 30 more. **The key
that actually bit is not in that list** — `惠` collides with a *district* (惠山区), and the
repo holds no district table to audit against. So the ambiguous set cannot be derived; it
has to be evidence-driven, which is how §6 implements it.

---

## 3. Which fallback is loose, and what tightening would cost

`geo.province_name_of_place` resolves a place string in five tiers. Over every place string
the corpus actually hands it (site names via `chinese_place`, `locality_of_head(lead_issuer)`,
and `localize()` localities for all 346,955 documents), **before** this change:

| tier | distinct strings | doc-weighted |
|---|---:|---:|
| `PROVINCE_CODE` exact | 31 | 80,866 |
| `CITY_PROVINCE` exact (`data/city_province.csv`) | 325 | 153,610 |
| `DISTRICT_CITY` exact | 38 | 3,479 |
| `<city><district>` prefix loop | 91 | 20,771 |
| longest place-name prefix fallback | 127 | 187 |
| unresolved → `None` | 425 | 2,016 |

**Requiring an exact table hit would lose 20,958 doc-weighted resolutions over 218 distinct
strings, and all 218 are correct.** Hand-checked, every one:

- the prefix loop is the `<city><district>` site-name form — `武汉硚口区`, `苏州张家港市`,
  `南京鼓楼区`, `重庆九龙坡区`, `无锡惠山区`, `那曲地区`, `苏州工业园区` …
- the place-prefix fallback is institution names whose place is their prefix —
  `福建省民政厅` and 40 more Fujian departments, `重庆市市场监督管理局` and 43 more Chongqing
  bureaus — plus doubled-suffix noise (`广东省省` ×21, `江苏省省` ×19) that still resolves
  correctly.

So **exact-only loses 20,958 correct resolutions and zero wrong ones. Do not tighten it.**
The CLAUDE.md length-floor family does not apply here: this fallback is not standing in for
a missing table entry, it is parsing a compound name.

The genuinely loose match is `docnum_agency`'s `prefix.startswith(registry_key)`. Tightening
*that* to exact keys is also not an option: **18,365 of the 36,243 registry-matched 文号
(50.7%) match only by prefix**, and they are the series suffixes the registry deliberately
does not enumerate — `沪府发` (1,136), `粤府函` (973), `苏府地名函` (1,154), `中府函` (1,255),
`黑政办发` (647), `京政发` (417), `渝府办发` (507), `深府规` (230) … all correct. Neither
fallback should be narrowed; the lever is arbitration at the caller.

---

## 4. The title-percentage discrepancy in `fidelity-wuxi.md` §10 — and what replaces it

The memo says `localized_of` fires on 2 Wuxi pairs against 44 Suzhou because "581 of 2,209
Wuxi titles (26%) contain no 无锡 at all … against 182 of 4,919 for Suzhou (3.7%)". An
independent count of titles containing no city name gives 43.2% and 54.1%.

**Both are arithmetically right; they count different things, and only one matches the
sentence.** The memo's appendix query is a four-branch `CASE` evaluated in order:

```sql
CASE WHEN title LIKE '无锡市%' THEN 'starts 无锡市'
     WHEN title LIKE '市政府%'  THEN 'starts 市政府'
     WHEN title LIKE '%无锡%'   THEN '无锡 elsewhere' ELSE 'no 无锡' END
```

The second branch absorbs 866 Wuxi / 3,629 Suzhou titles, and most of them contain no city
name either. So `581` is not "titles containing no 无锡" — it is "titles that neither start
with `无锡市`, nor start with `市政府`, nor contain `无锡` anywhere".

| statistic (`site_key` portal only) | wuxi (n=2,209) | suzhou (n=4,919) |
|---|---:|---:|
| memo's `CASE` residual bucket | 581 (26.3%) | 182 (3.7%) |
| **titles containing no 无锡 / 苏州 anywhere** | **954 (43.2%)** | **2,660 (54.1%)** |
| `title_core` containing none | 954 (43.2%) | 2,660 (54.1%) |
| masthead containing none | 1,992 (90.2%) | 4,509 (91.7%) |
| masthead empty | 1,387 (62.8%) | 3,741 (76.1%) |
| instrument core STARTS with the city name | 666 (30.1%) | 1,203 (24.5%) |
| **`localize()` yields no qualified locality** | **1,986 (89.9%)** | **3,308 (67.2%)** |

**The right denominator for the claim as written is 43.2% / 54.1%, and on it the
explanation is refuted: the ordering flips.** Wuxi titles carry the city name *more* often
than Suzhou's (43.2% missing vs 54.1%), and Wuxi cores *start* with the city name more often
(30.1% vs 24.5%), yet `localized_of` fires 2 vs 44. (The memo's appendix also prints its own
four counts out of `CASE` order — "866 / 581 / 400 / 362" where the branches emit
362 / 866 / 400 / 581 — which is how the `市政府` bucket came to be read as the no-city one.)

**The masthead-style explanation does not survive. The real gate is another missing table
entry.** `localize()` places a document only if `locality_in_core` accepts the core's
locality prefix, and that function accepts a name only when it is in
`build_doc_identity.KNOWN_LOCALITIES` — a 54-name set built from `_PROV_MUNI` plus the
localities named in the 文号 registry `DOCNUM_SUBNATIONAL`. **`苏州市` is in it (via `苏府`);
`无锡市` is not, because Wuxi has no 文号 registry entry** (the same absence as §2's `锡`).
Verified directly:

```
'苏州市' in KNOWN_LOCALITIES                                   -> True
'无锡市' in KNOWN_LOCALITIES                                   -> False
locality_in_core('苏州市户籍准入登记管理办法', '')               -> '苏州市'
locality_in_core('无锡市见义勇为称号评定实施办法', '')            -> None
localize('市政府关于印发苏州市户籍准入登记管理办法的通知','suzhou') -> ('户籍准入登记管理办法','苏州市',2)
localize('市政府关于印发无锡市见义勇为称号评定实施办法的通知','wuxi') -> ('无锡市见义勇为称号评定实施办法', None, None)
```

and the placement rates follow it: `localize()` places 223 (10.1%) of Wuxi's titles against
1,611 (32.8%) of Suzhou's. Same shape as the province bug — a missing table entry, not a
portal's title convention. **Do not propagate 26% / 3.7% as an explanation of the
`localized_of` gap.** Seeding `KNOWN_LOCALITIES` from `CITY_PROVINCE` would close it, but
that changes instrument pooling corpus-wide and needs its own measurement; logged here, not
done.

---

## 5. What changed

**`scripts/rnd/analysis/geo.py`** — Wuxi's five districts (`梁溪区 锡山区 惠山区 滨湖区
新吴区`) and two county-level cities (`江阴市 宜兴市`) added to `DISTRICT_CITY` → `无锡市`.
All seven names are nationally unique, so no `<city><district>` qualifier is needed; the two
county-level cities belong here rather than in `data/city_province.csv` because they are not
prefectures. `province_name_of_place` itself is untouched — still pure, still returns `None`
for an unmapped bare district. Nine self-test cases added, including two unmapped districts
with ambiguous heads (`惠城区`, `江岸区`) pinned at `None`.

**`scripts/build_doc_identity.py`**

- `docnum_registry_key(docnum)` factored out of `docnum_agency` (same behaviour), so the
  matched key is testable, with the 50.7%-match-by-prefix measurement in its docstring as
  the reason the loose match stays.
- `AMBIGUOUS_DOCNUM_PREFIXES = frozenset({"惠府", "惠府办"})` — a declared, commented set of
  heads more than one government uses, with §2's measurement and the instruction to extend
  it from evidence (the latent set is not derivable, §2).
- `derive_province(doc, lead_issuer, site_prov=None)` — the site's province arrives as an
  **arbiter, not a candidate**: when the 文号 candidate disagrees with it *and* the matched
  registry key is in the ambiguous set, the 文号 candidate is dropped and the remaining
  fields (publisher → masthead → `localize()` → title head) decide. Explicitly not a
  precedence change: the 文号 still beats the masthead everywhere else, which is what keeps
  the joint `粤府函` 批复 correct. The old 2-argument call still works.
- `build()` now calls `load_site_names(conn)` itself, so a direct `build(conn)` caller (the
  read-only shim `fidelity-wuxi.md` used) does not silently lose the arbitration.

## 6. Effect on the live corpus, old code vs new, read-only

`derive_province` recomputed for all 346,955 documents under both trees:

| | docs |
|---|---:|
| scanned | 346,955 |
| **changed** | **1,185** |
| corrected `gd` → `js` (the bug) | 22, all `wxd_huishan` |
| newly resolved `None` → `js` (the geo additions) | 1,163 — `wxd_jiangyin` 664, `wxd_xinwu` 316, `wxd_binhu` 58, `wxd_liangxi` 51, `wxd_yixing` 35, `wxd_huishan` 21, `wxd_xishan` 18 |
| **lost a province (`code` → `None`)** | **0** |
| **moved between two non-null provinces other than the 22** | **0** |

Tests: 216 collected, 215 passed + 1 pre-existing skip (was 202 before; `tests/test_wenhao_province_ambiguity.py`
adds 14). `build_doc_identity.py --self-test` 203/203 (was 195); `geo.py --self-test` 32/32 (was 23).

## 7. Rebuild needed for the fix to reach the live data

None of this is in the database yet — `doc_identity` is a precomputed side table and the
nightly holds the write lock. In order, after the lock clears:

```
python3 scripts/build_doc_identity.py --write --force              # Phase 2b, ~37s
python3 scripts/build_instrument_succession.py --write --force     # reads doc_identity, ~70s
python3 scripts/rnd/analysis/build_diffusion_events.py --write     # reads level/province/pooling
python3 scripts/build_tracker_rollup.py                            # per topic × week × level
python3 scripts/validate_cascades.py                               # 15 read-only checks
```

The nightly `daily_sync.sh` Phase 2b/2c runs all five in that order, so a plain nightly run
is sufficient; the manual sequence is only for getting it sooner.

**Expect topic-labelled aggregates to move.** 1,163 Wuxi district documents gain a province
and so become eligible for the same-province gate in `build_diffusion_events` for the first
time. Per CLAUDE.md's 2026-10-07 lesson, a cascade is labelled by its ANCHOR's `topics_algo`,
so re-base any topic-level series after this rebuild rather than assuming only Jiangsu's
counts grew. `fidelity-wuxi.md`'s Jiangsu figures were computed on a shim that had the bug;
they are floors by 22 documents on the citation basis and by more on the `localized_of`
channel, which §4 shows is gated elsewhere anyway.

---

## 8. §5's deferred question, measured: seed `KNOWN_LOCALITIES` from `CITY_PROVINCE`?

§5 shipped `AMBIGUOUS_DOCNUM_PREFIXES` and the Wuxi `DISTRICT_CITY` rows but deliberately
left a larger thing alone, and that larger thing is the most consequential finding in this
report. `build_doc_identity.KNOWN_LOCALITIES` held **54 names**, seeded from `_PROV_MUNI`
plus the localities that appear in the 文号 registry (`issuer_parser.DOCNUM_SUBNATIONAL`).
`locality_in_core` accepts a locality prefix inside an instrument core **only if it is in
that set**. The registry is a list of 文号 heads, not a list of localities, so it vouched
for exactly 23 cities — every Guangdong gkmlpt city, plus 南京市 / 苏州市 / 杭州市 / 武汉市 —
and for no other city in China:

```
locality_in_core('苏州市户籍准入登记管理办法','')  -> '苏州市'     (via 苏府)
locality_in_core('无锡市见义勇为称号评定实施办法','') -> None        (Wuxi has no 文号 entry)
```

Consequence: `localized_of` fired on **2** 无锡市 pairs against **83** 苏州市 pairs. That
ordering is impossible as a fact about Wuxi — §4 measured that Wuxi titles carry the city
name MORE often than Suzhou's (43.2% lack it vs 54.1%) — and obvious as a fact about a
hand-maintained list. It is the shape CLAUDE.md now names: a hand-maintained table silently
bounding a measurement, here the renaming-channel floor in `pair-channels.md`.

The question deferred in §5 was whether to seed the set from `geo.CITY_PROVINCE` (354
prefecture-level divisions, already complete, already read by the province resolver and by
`jurisdiction_chain()`). The stated reason not to was that it "changes instrument pooling
corpus-wide". **That is the right caution and it turns out to be false.** Measured, not
argued, below.

### Method

Two full `build_doc_identity` rebuilds of the live 346,955-document corpus, run read-only
(`?mode=ro`) against the droplet's `documents.db` while the nightly held the write lock,
each dumped to its own scratch SQLite file and compared side by side — the pattern
`fidelity-wuxi.md` used. Nothing was written to `documents.db`, `doc_identity` or any live
table. For the cascade checks, a 590 MB **slim scratch copy** of the DB was made (every
table the identity → diffusion → tracker → validator chain reads, with the body/html
columns blanked — none of that chain reads them; it reproduces `validate_cascades` 15/15),
then forked into `slim_old` / `slim_new`, each loaded with its own identity table and
rebuilt through `build_diffusion_events --write` + `build_tracker_rollup`.

54 → **381** names (354 prefectures ∪ the 27 province names the registry already carried).

### Blast radius

| | 54 names | 381 names |
|---|---|---|
| docs with a `localize()` locality that differs | — | **11,312** (11,057 NULL→locality, 255 locality→other) |
| `instrument_id` values changed | — | **1** |
| pools MERGED (a new pool drawing on >1 old pool) | — | **1** |
| pools SPLIT (an old pool scattered across >1 new pool) | — | **0** |
| `instrument_role` flips | — | **1** (`unique` → `mirror`) |
| instruments / pools with ≥2 docs | 336,394 / 6,222 | 336,393 / **6,222** |
| `localized` (kept out of a higher pool) | 4,617 | 9,359 |
| `localized_of` edges | 2,075 | **3,411** (+1,336 added, **0 removed, 0 retargeted**) |
| genre transitions | — | **only** `promulgation`→`implementing`, 1,336 |
| `province` resolved (sub-national) | 181,606 (81.1%) | 182,716 (81.6%) — all NULL→code, **0 re-codings** |
| `diffusion_events` after rebuild | 45,679 rows | 45,679 rows, **byte-identical** (sha 24fb70f2…) |
| `tracker_weekly` after rebuild | 46,208 rows | 46,208 rows |
| `validate_cascades` | 15/15 | **15/15** |

**Why pooling barely moves, structurally.** A doc that is NOT localized pools on its FULL
normalized core (`instrument_key`), and a doc that IS localized pools on `(stem, locality)`.
Recognizing a city therefore only re-keys a doc that *also* has a higher-level same-stem
sibling — and when it does, every copy of that same text re-keys with it, so the group moves
intact. Hence 0 splits. The single merge is real and correct:

```
900171141 wuxi      2015-12-31  canonical  市政府办公室关于印发无锡市临时救助实施办法的通知
900173939 wxd_xinwu 2015-12-31  mirror     无锡市临时救助实施办法
900171351 wuxi      2016-01-08  unique -> mirror
                                无锡市人民政府办公室关于印发无锡市临时救助实施办法的通知
```

One text, three copies; the third was `unique` only because its full core (`人民政府办公室…`)
differed from the first's (`政府办公室…`). Stripping the locality makes both stems
`临时救助实施办法` and they pool. Hand-checked: correct, 1/1.

**Why `diffusion_events` is byte-identical.** `build_diffusion_events` reads
`IMPLEMENTING_IDENTITY_GENRES = {"promulgation", "implementing"}`, so a
`promulgation`→`implementing` flip does not change `source_implementing`. The 1,336 flips
are therefore invisible to the matcher, the tracker, and every memo built on them. The AI+
count reads 30 rather than the live 29 in **both** rebuilds — that is the identity table
being refreshed to include today's documents, not an effect of the widening.

### Blast radius per city — this is not a Wuxi fix

`localized_of` edges by the doc's own locality:

| | 54 names | 381 names |
|---|---|---|
| distinct localities with ≥1 edge | 85 | **308** |
| 无锡市 | 2 | **73** |
| 苏州市 | 83 | **83** (unchanged) |

The cities that already worked do not move at all; only the invisible ones appear. The
1,336 added edges by host site: `npc` **1,287**, `wuxi` 37, `wxd_xinwu` 4, `shanwei` 2,
`liaoyuan` 2, and one each on `hami` / `shantou` / `qingdao` / `sm`. By the document's own
province: ha 154, js 135, sd 130, ln 109, nm 85, he 77, jl 76, zj 59, ah 58, sn 55, sc 54,
sx 53, hlj 45, gs 37, gx 32, hn 24, gz 22, nx 21, jx 19, yn 17, fj 14, xz 13, hb 12, xj 12,
qh 11 — i.e. **25 provinces**. The dominant beneficiary is the `npc` 地方法规 tier: 28.6k
local 人大 instruments, titled `<city>X条例`, which could not reach the localization channel
at all because their cities were not in the 54. Trigger level of the added edges: provincial
842, central 493, district 1.

Documents whose locality CHANGED, by site: `npc` 9,125, `wuxi` 614, `shanwei` 161, `hlj` 129,
`jilin` 76, `wxd_xinwu` 67, `yuxi` 61 … — 11,312 over 45+ sites. Note the asymmetry: 11,312
documents get a locality, only 1,336 gain an edge and only 1 changes pool. A locality by
itself has no consequence unless a higher-level same-stem text exists.

### Adversarial hunt: does a mentioned city get mistaken for the issuer's?

The 54-name set existed to stop a locality word inside a title being read as the issuer's
own locality. With 354 names that risk grows, so it was hunted two ways over all 11,312
affected documents.

**1. Against the site's province** (`geo.province_of`): 2,149 resolvable, **2,149 agree, 0
mismatch**, 9,163 unresolvable (the site or the locality has no province code — overwhelmingly
`npc`, which is a national site).

**2. Against the document's OWN evidence** (`publisher` ∪ `doc_issuers.lead_issuer` ∪ 文号,
which covers the `npc` rows the site cannot place): **9,873 confirm** the core-prefix
locality, **0 name a city in a different province**, 1,439 are silent (no locality in any
header field — typically a news item whose title is the only evidence).

**Zero misplacements on either arbiter.** Three structural reasons, each pinned in
`tests/test_known_localities.py`:

* `locality_in_core` anchors at `^` on the instrument CORE, so a mid-title mention cannot
  reach it. `广东省人民政府办公厅关于学习推广无锡市经验的通知` keeps `广东省`, and 无锡 stays
  inside the stem; `江苏省人民政府关于支持无锡市深化改革的若干意见` keeps `江苏省`.
* a 转发 wrapper keeps the wrapper as its core, so `关于转发《无锡市城市管理办法》的通知` on a
  Guangdong site localizes to **nothing** — the forwarder does not acquire Wuxi.
* `CITY_PROVINCE` holds **prefecture-level divisions only**, which is load-bearing and was
  not obvious in advance: the word-collision-prone county-level city names are absent, so
  `东方市` (Hainan) is not a known locality and `东方市场建设管理办法` stays unlocalized. Had
  the seed been "every administrative division", that title would have lost its 市 to a
  locality. `批发市场管理办法` / `超市食品安全管理规定` / `民族地区教育发展规划` are refused
  the same way.

A compound-break scan (stems beginning with 场/政/容/区/民/级/外/…) flagged 222 documents.
Reviewed: in every case the LOCALITY is right and only the stem is garbled —
`七台河市场监管局…` is 七台河 + 市场监管局 and that bureau *is* 七台河市's; `汕尾市局深入…`
is 汕尾市 + 局; `大连市外商投资促进条例` is a false alarm of the heuristic. A garbled stem is
harmless unless it collides with a higher-level identical garbled stem, which none does.

**38 documents on central / media / research sites gained a city locality** (the inherently
suspicious class). Every one is genuinely about that city — `商务部关于印发《成都市服务业扩大
开放综合试点总体方案》的通知`, `国家发展改革委关于印发宁波市灵活就业人员支持政策典型经验的通知`,
MIIT news about 宁波市 telecoms, `chinapeace` readouts about 西安市 — and **none flips genre**
(the flip requires a sub-national `admin_level_doc`).

### Hand-check

**30 newly-localized documents**, one per site across the 30 largest affected sites (seed 7):
**30/30 localities correct** — 郑州市 / 无锡市 / 汕尾市 / 七台河市 / 长春市 / 玉溪市 / 石家庄市 /
潜江市 / 泉州市 / 朝阳市 / 青岛市 / 漳州市 / 晋城市 / 锡林郭勒盟 / 吕梁市 / 伊春市 / 乐山市 /
山南市 / 朔州市 / 莆田市 / 芜湖市 / 汕头市 / 福州市 / 通辽市 / 克拉玛依市 / 沈阳市 / 柳州市 /
喀什地区 … and **none of the 30 gained a `localized_of` edge**, which is the asymmetry above.

**Newly-merged pools: there is exactly 1**, so the 15 asked for cannot be sampled. It is
hand-checked above (correct). In its place, **30 of the 1,336 newly-added `localized_of`
edges** (seed 7) were hand-checked — the substantive change:

**29/30 correct.** Every one has the shape `<city>X条例 → <province>X条例`, or the central
行政法规 of the same name where the province has none: 无锡市不动产登记条例 → 江苏省不动产登记条例;
百色市非物质文化遗产保护条例 → 广西壮族自治区…; 三明市城市园林绿化管理条例 → 福建省…;
广元市优化营商环境条例 → 四川省…; 昆明市生猪屠宰管理条例 → the State Council's 生猪屠宰管理条例;
徐州市航道管理条例 → 江苏省…; 齐齐哈尔市城镇燃气管理条例 → 黑龙江省…; 乌鲁木齐市大气污染防治条例
→ 新疆维吾尔自治区…; 周口市文明行为促进条例 → 河南省文明行为促进条例 (lag 14 d). Lags run 12 d to
2,503 d, all forward.

**1 wrong, and it is a known class, not a new one:** `12730074 大同市人民代表大会常务委员会人事
任免办法 → 山西省人民代表大会常务委员会人事任免办法`. A city legislature's own appointment
procedure is self-government housekeeping — the error class `qa-genre-flip.md` identified and
`GENERIC_STEM_RE` exists to block (议事规则, 制定地方性法规条例, 三定规定, 政府工作规则) — and
`人事任免办法` simply is not on that denylist. Measured across all 1,336 added edges, this
residue is **2 documents** (大同市, plus 三沙市人民代表大会常务委员会人事任免规定; a third
match, 汕尾市突发事件应急管理专家组工作规则 → the Guangdong text, is a genuine localization).
By `instrument_kind` the added edges are **framework 1,329 / housekeeping 6 / other 1**,
against the existing 2,075 which are framework 1,829 / other 133 / housekeeping 113 — so the
widening adds *proportionally fewer* housekeeping flips than the channel already carried.
Precision on the added edges is ~97% by sample and ≥99.8% on the housekeeping class by census.
Extending `GENERIC_STEM_RE` with 人事任免 is a separate, 2-document fix that would also
re-base the existing 2,075, and is left as a logged follow-up rather than bundled here.

### Invariants

Each checked read-only against both scratch builds. **All five identical old vs wide**; only
the flip count moves, which is the intended effect.

| invariant | 54 names | 381 names |
|---|---|---|
| 政府信息公开条例 stays 2 instruments | 2 pools: `12742206` n=19 (2019-04-03…2026-07-28), `900045292` n=4 (2008-03-28…2017-08-24) | identical |
| 城乡规划法 trio: `12685270` canonical, 2015 edition separate | `12685270` canonical (mee), `12742122` mirror (npc), `12747143` 2015 **unique** | identical |
| every 中华人民共和国国务院令 stays `unique` | 29 docs, 29 `unique` (29 not 20 — the corpus grew) | identical |
| annual-series split separates 政府工作报告 per year | 12 pools with ≥2 docs, **0 spanning >1 calendar year** | identical |
| in-chain genre flip count | 2,075 (not 2,014 — same growth) | 3,411 |
| `validate_cascades` after a full diffusion + tracker rebuild | 15/15 | **15/15**, line for line |

On the flip count: it is the one number that moves, and it moves by design — the set's whole
job is to decide which documents can reach the channel. It was pinned as an invariant because
a pooling change could have perturbed it sideways; the measurement shows it does not move
sideways at all (0 edges removed, 0 retargeted, 0 pools split), it only grows, and the growth
hand-checks at ~97%.

### Decision

**Ship the `CITY_PROVINCE` seed.** The caution in §5 was correct to demand measurement and
wrong on the substance: the change does not touch instrument pooling corpus-wide (1 document,
1 merge, 0 splits), leaves `diffusion_events` byte-identical, leaves all five named invariants
untouched, passes `validate_cascades` 15/15, and places 11,312 localities with **zero**
measured misplacements against two independent arbiters and 30/30 by hand.

The narrower alternatives were considered and rejected on the numbers:

* **"only the cities that host documents"** would fix `wuxi` (37 edges) and miss **1,287** —
  the `npc` 地方法规 tier's cities (百色市, 吕梁市, 三明市 …) mostly do not host a site, so this
  option forfeits 96% of the gain while leaving the same hand-maintained-list shape in place,
  one city at a time.
* **"require masthead corroboration for the wider names"** is already the fallback that exists
  (`locality_in_core`'s second branch) and it is exactly what fails on `npc`: a 地方法规's title
  IS `<city>X条例` with no masthead. It would re-create the gap it is meant to close.
* **"change nothing"** keeps a documented 36× artefact (2 vs 73 Wuxi edges) inside a published
  floor, with no measured harm on the other side of the ledger.

What is NOT in scope, and was not measured: seeding from `geo.DISTRICT_CITY` (bare district
names — 开发区 / 园区 / 城区 are a far more collision-prone surface). `locality_in_core`'s
`_LOC_DISTRICT` branch still accepts a district prefix only via the 文号 registry, the
masthead, or a `<city><district>` qualifier.

### What `pair-channels.md` should say about its floor (not edited here)

The memo currently reports the renaming / `localized_of` channel's figures as a floor set by
coverage. They were a floor set by a **hand-maintained 54-name table**, and the two bounds are
different in kind: a coverage floor rises when documents arrive, this one rose by 64% —
2,075 → 3,411 edges, 85 → 308 localities — with no new documents at all. Specifically it should
record that (a) the pre-2026-10-08 `localized_of` counts are not comparable to the post ones
and any per-city figure computed before that date is an artefact of which cities had a 文号
head, not of which cities re-issue; (b) 无锡市 went 2 → 73 while 苏州市 stayed at 83, so the
earlier Wuxi-vs-Suzhou contrast in `fidelity-wuxi.md` measured the table and not the cities;
(c) the `npc` 地方法规 tier entered the channel for the first time, which makes the
sub-national-legislation share of the renaming channel a genuinely new series rather than a
grown one; and (d) the citation-only relay figures are unaffected — `diffusion_events` rebuilt
byte-identical, so the `+0.2 pt` fidelity note stands as written.

### Rebuild sequence

The code change is a pure function of the title; nothing is in the database yet, and the
nightly holds the write lock. After it clears, in this order (the same five as §7 — this
change adds no new step):

```
python3 scripts/build_doc_identity.py --write --force            # ~2 min on the droplet
python3 scripts/build_instrument_succession.py --write --force   # reads doc_identity, ~70s
python3 scripts/rnd/analysis/build_diffusion_events.py --write   # measured byte-identical
python3 scripts/build_tracker_rollup.py
python3 scripts/validate_cascades.py                             # expect 15/15
```

A plain nightly `daily_sync.sh` run is sufficient (Phase 2b/2c runs all five in that order);
the manual sequence only gets it sooner. Expect `doc_identity.genre='implementing'` to go
18,699 → 20,035 and `localized_of` 2,075 → 3,411. Do **not** expect any tracker or cascade
figure to move: both were rebuilt and compared.

Verification that what is committed is what was measured: the shipped `_known_localities()`
produces a `doc_identity` dump byte-identical to the monkeypatched wide build
(sha `2b2a667c282efc32` over `(doc_id, instrument_id, instrument_role, genre, localized_of,
province, loc, stem)` for all 346,955 docs; the 54-name baseline is `5a95b415e7dcabd1`).

Tests: 230 collected, **229 passed + 1 pre-existing skip** (was 215 + 1);
`tests/test_known_localities.py` adds 14. `build_doc_identity.py --self-test` 203/203
unchanged.
