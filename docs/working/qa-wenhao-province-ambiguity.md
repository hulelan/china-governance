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
