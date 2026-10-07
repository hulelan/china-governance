# Do Pilots Scale? A Successor-Instrument Detector for the Wang & Yang Gap

*Read-only analysis against the live `documents.db` (droplet, 2026-10-06, `?mode=ro`).
Lever: `scripts/rnd/analysis/successor_detector.py`. Addition B3 from
`docs/research/corpus-lessons.md`. The question is narrow: the experimentation
replication (`docs/research/experimentation-wang-yang.md` §3b) saw only 0.4-1.2% of
central pilot themes reach a visible national instrument, against Wang & Yang's 53.9%
success rate. Is that gap real, or is it an artifact of matching a later title on the
pilot's theme string? This note builds a stronger detector, hand-checks every pair it
finds, hand-classifies a sample of the pilots it does not match, and says how much of
the gap each step closes. No regime-type labels; mechanism-level claims only.*

---

## 0. Answer in one paragraph

The detector finds a national successor for **75 of 1,271** central pilot instruments
(**5.9%**; **6.9%** once pilots under three years old are excluded), at a **median lag of
564 days (1.5 years)**. That is five to fifteen times the memo's 0.4-1.2%, and the lag
now sits inside Wang & Yang's 2.25-year mean duration instead of outside it. Hand-check
precision is **76% strict, 87% lenient** on all 75 pairs (80% / 90% on the 40-pair
sample), so the precision-adjusted rate is **4.5-5.1%**, **5.2-6.0%** ex-mid-flight.
The level is still an order of magnitude below 53.9%, and the no-successor hand sample
says why: **the dominant reason is not that pilots fail to scale but that the rollout
is published under a renamed or absorbing instrument** the core match cannot reach
(海南自由贸易试验区 → 海南自由贸易港建设总体方案; 刑事速裁试点 → the 2018 刑事诉讼法;
证照分离全覆盖试点 → 国发〔2021〕7号). Among substantive, mature no-successor pilots in
the sample, a successor exists in the corpus for 9 of 12. Two of 12 show no successor
anywhere we can see. The rest of the "gap" is a definition mismatch: 40% of unmatched
pilots are zone designations (自贸试验区, 自创区, 示范区 batches) whose scaling takes the
form of more zones in later 批复 that keep the pilot cue. **Evidence-labeled reading:**
the better detector closes roughly a tenth of the raw gap; the hand sample says most of
the remaining gap is measurement (renaming, zones, mid-flight), not substance, but that
inference rests on 12 hand-read cases and is stated as a range, not a point.

---

## 1. Definitions (from `doc_identity`, no body reads)

**Pilot.** A document with `admin_level_doc='central'`, `genre='promulgation'`,
`date_quality='good'`, dated 2000-2026, whose title carries 试点 | 试验区 | 先行先试 |
示范区. Mirrors collapse on `instrument_id` (the gov republish of a ministry notice is
one instrument).

- Central promulgations: **35,027 docs → 30,198 instruments**. *(Build note 2026-10-07: this
  ran before the A4 correction (`12453df`), when `date_quality='crawl_stamped'` still excluded
  ~29k docs on 76 shallow-archive sites, MIIT among them. Live 2026-10-07 the same filter admits
  36,902 central promulgations (+1,875), almost all dated 2026 and so mid-flight; the pilot
  universe and the 5.9% are on the smaller set and were not re-run.)*
- Pilot-cued: **1,490 docs → 1,271 instruments** (the memo's title-family set was 1,592
  docs / 1,296 themes on `sites.admin_level` and a regex genre; `doc_identity` re-levels
  ~28k npc local 人大 rows and drops explainers/readouts, hence the lower doc count).
- Of these, **872** are 试点-cued trials with no zone name (示范区/试验区/先行区/综试区/
  自创区); the remaining 399 are zone designations, which Wang & Yang largely exclude
  by reading the text.

**Successor.** A later central promulgation (date strictly after the pilot), with no
pilot cue in its title and not a 批复/函 reply, whose normalized title core matches the
pilot's core with the pilot marker stripped, or contains the pilot's core and carries a
generalization cue (全面推开 / 全面实施 / 全面推广 / 推广 / 在全国范围 / 扩大…范围 /
正式实施 / 复制推广 / 办法 / 条例 / 规定 / 实施细则), issued by the same or a higher
`lead_issuer`, with `topics_algo` overlap when both sides carry topics. Candidates:
**26,878** instruments.

**Core.** The citation layer's `_title_cores_of_title` (the 《X》 inside a promulgation
wrapper, the 关于… body after an issuer masthead, else the bare title) with masthead,
文号, waves, years and genre boilerplate removed and the pilot markers stripped, then
`_norm_title`. The scoring sketch is in the appendix.

**Mid-flight.** Pilot dated after 2023-10-08 (less than three years before the corpus
horizon). 239 of 1,271 pilots.

---

## 2. Scale rate

| universe | pilots | successors | rate | ex-mid-flight | median lag |
|---|---|---|---|---|---|
| Wang & Yang (1980-2020, hand-coded) | 633 experiments | 341 | **53.9%** | n/a | mean duration 2.25 y (~820 d) |
| Memo §3b title-family proxy | 1,296 themes | 5-16 | 0.4-1.2% | n/a | 738-1,070 d |
| **Detector, all pilots** | 1,271 | **75** | **5.9%** | 71 / 1,032 = **6.9%** | **564 d** |
| strict core-match only (exact / containment) | 1,271 | 50 | 3.9% | 46 / 1,032 = 4.5% | 615 d |
| + citation channel (cites the pilot, carries a cue) | 1,271 | 85 | 6.7% | 81 / 1,032 = 7.8% | 564 d |
| **试点-cued trials, no zone names** | 872 | **70** | **8.0%** | 66 / 696 = **9.5%** | 606 d |
| trials, strict only | 872 | 48 | 5.5% | 44 / 696 = 6.3% | 712 d |
| trials, + citation channel | 872 | 78 | 8.9% | 74 / 696 = 10.6% | 534 d |
| long-horizon central sites only | 1,168 | 73 | 6.2% | 69 / 1,007 = 6.9% | 538 d |
| long-horizon, strict | 1,168 | 48 | 4.1% | 44 / 1,007 = 4.4% | 525 d |

**Evidence.** Three things hold across every row. (1) The level is 4-11%, five to
fifteen times the memo's proxy and still an order of magnitude under 53.9%. (2) The
median lag is 1.5-2.0 years, now inside Wang & Yang's 2.25-year mean; 60% of detected
successors arrive within 820 days (p25 294 d, p75 1,306 d). (3) The strict subset (exact
or containment match, no fuzzy similarity, no cue needed) carries two thirds of the
hits, so the result does not depend on the fuzzy tier. Threshold sensitivity is flat
(0.55 → 78, 0.75 → 63 successors).

**By cohort.** 2000-2009: 3/59 (5.1%, median lag 2,713 d). 2010-2015: 13/197 (6.6%,
1,891 d). 2016-2019: 32/373 (8.6%, 598 d). 2020-2023: 24/432 (5.6%, 449 d). The
2016-2019 cohort scales most visibly, which is also the cohort whose successors fall
inside the best-crawled years of the central sites; the early cohorts' long lags are a
coverage artifact (their successors are the first same-theme instrument we hold, not
the first that existed).

**Match anatomy (75 pairs).** Kinds: containment 39 + 1, exact 10, bigram Dice 25.
42 carry a generalization cue; 14 cite the pilot directly; issuer relation same 70,
higher 5 (国办 or 国务院 settling a ministry's pilot).

---

## 3. Hand-check precision

Every one of the 75 detected pairs was read (the 40-pair random sample is a subset; its
ids are in `handcheck.tsv`). Verdicts: **T** = the successor is the de-piloted national
or settled instrument of the pilot, or the de-piloted continuation of the same
programme; **P** = same programme but not a rollout (a sub-instrument, the next wave, a
partial-area launch); **F** = a different instrument.

| set | T | P | F | strict (T) | lenient (T+P) |
|---|---|---|---|---|---|
| all 75 pairs | 57 | 8 | 10 | **76.0%** | **86.7%** |
| 40-pair sample | 32 | 4 | 4 | **80.0%** | **90.0%** |
| by kind: exact (10) | 9 | 1 | 0 | 90% | |
| containment (40) | 26 | 6 | 8 | 65% | |
| Dice + cue (25) | 22 | 1 | 2 | 88% | |

**Precision-adjusted scale rate:** 4.5% strict / 5.1% lenient on all pilots; 5.2% /
6.0% ex-mid-flight; roughly 6-8% on the trials-only universe.

**Evidence, what the true positives look like.** 商业健康保险个税试点 (2015) →
推广实施 (2017, 511 d). 税务证明事项告知承诺制试点工作方案 (2019) → 全面推行…实施方案
(2020, 494 d). 行政执法三项制度试点 (2017) → 全面推行…指导意见 (2019, 692 d).
生育保险与职工医保合并实施试点 (2017) → 全面推进 (2019, 776 d). 境外旅客购物离境退税
海南试点管理办法 (2010) → 离境退税管理办法(试行) (2015). 三网融合试点 (2010) → 三网融合
推广方案 (2015). 棉花流通体制改革试点批复 (江苏/山东/河南, 2010) → 国务院深化棉花流通
体制改革意见 (2016). 大豆完全成本保险试点 (2022) → 扩大政策实施范围 (2024). These are
exactly Wang & Yang's "successful experiment" shape.

**Evidence, where the detector errs.** The containment tier is the weak one (65%).
Its false positives are a short pilot core landing in a longer later title about
something else: 教育信息化试点 (2012) → 教育信息化标准化工作管理办法 (2025);
社会信用体系建设示范区名单 → 社会信用体系建设行动计划; 现代医院管理制度试点 → 电子电器
行业管理制度改革 (Dice); 保税物流中心扩大试点审批办法 → 保税物流中心统计办法 (Dice).
The partials are instruments that operate the pilot rather than end it: 个税递延养老
保险试点 → 产品开发指引 23 days later; REITs试点 → 新购入项目申报. A length floor of 8
on the containment core would remove most of the F cases at a cost of a few T cases;
left as is so the table reports the detector as specified.

---

## 4. Why pilots show no successor: the 30-pilot hand sample

A seed-fixed random sample of 30 of the 1,190 no-successor pilots, each read against
the corpus (the loose probe in `nomatch_sample.tsv` lists later instruments sharing
half the core's bigrams, and the successors named below were confirmed by title query).

| reason | n | share | what it means |
|---|---|---|---|
| **zone_wave** | 12 | 40% | the designation is the policy (自贸试验区 总体方案, 国家自主创新示范区 批复, 跨境电商综试区 批复, 共同富裕示范区, 要素市场化配置试点). Scaling takes the form of more zones in later 批复 that keep the cue, or 典型经验 lists. Not a trial-then-rollout shape. |
| **renamed** | 7 | 23% | a national successor exists in the corpus under a renamed or absorbing instrument: 海南自贸试验区 → 海南自由贸易港建设总体方案 (2020); 刑事案件速裁程序试点 (2014) → 认罪认罚试点 (2016) → 刑事诉讼法 (2018); 证照分离全覆盖试点 → 国务院深化“证照分离”改革…通知 (国发〔2021〕7号); 社会救助综合改革试点 (2018) → 中办国办 改革完善社会救助制度的意见 (2020); 总分机构试点纳税人办法 → absorbed into the 2016 全面推开营改增; REITs试点税收政策 → REITs 常态化发行. |
| **midflight** | 6 | 20% | under three years old, or a pilot renewed by 继续/延续实施 (创新企业 CDR 试点税收政策, extended 2023 and 2026). |
| **detector_miss** | 2 | 7% | a title-preserving successor exists but keeps the 试点 word (营商环境创新试点 → 复制推广营商环境创新试点改革举措的通知) or is an 扩大范围 variant the topic gate dropped (扩大专属商业养老保险试点范围 → 促进专属商业养老保险发展). |
| **pilot_is_rollout** | 1 | 3% | 全面推开营改增试点: the "pilot" was already nationwide. |
| **never_scaled** | 2 | 7% | NPC 四级法院审级职能定位改革试点 (expired 2023, no national instrument); 政府网站集约化试点工作方案 (absorbed into routine 政府网站 supervision, no titled successor). |

**Evidence.** Set aside the 12 zone designations (a definition mismatch with Wang &
Yang's experiment unit) and the 6 mid-flight pilots. Of the **12 substantive, mature**
no-successor pilots, **9 (75%) have a successor in the corpus** that the core match
cannot reach, 1 was itself the rollout, and **2 (17%) show no successor anywhere we can
see**. With n=12 the 75% carries a wide interval (roughly 43-95%, Wilson). Applied to
the 630 mature no-successor trials, that implies the true in-corpus scale rate for
substantive, mature trials lies somewhere around **45-75%**, a range that brackets Wang
& Yang's 53.9%. We report the range, not a point: it is an extrapolation from 12 cases
read by one coder.

**The top reason pilots show no successor is therefore a renamed or absorbing
instrument**, not a missing rollout. The detector cannot see a successor that drops the
pilot's theme string: 自由贸易试验区 becomes 自由贸易港; a 速裁程序 trial becomes an
amended code; a 全覆盖试点 becomes 深化改革…激发市场主体发展活力. This is the same
asymmetry the replication memo named (the corpus sees designation flowing down better
than generalization flowing up), now with its mechanism identified: **generalization
renames.**

---

## 5. Who scales, and what

**By pilot `lead_issuer` (≥15 pilots).**

| issuer | pilots | successors | rate |
|---|---|---|---|
| 文化和旅游部 | 29 | 5 | 17.2% |
| 交通运输部 | 19 | 3 | 15.8% |
| 税务总局 | 62 | 8 | 12.9% |
| 国家知识产权局 | 25 | 3 | 12.0% |
| 国家卫生健康委 | 20 | 2 | 10.0% |
| 国家发展改革委 | 64 | 6 | 9.4% |
| 财政部 | 152 | 14 | 9.2% |
| 住房城乡建设部 | 23 | 2 | 8.7% |
| 教育部 | 39 | 3 | 7.7% |
| 国务院办公厅 | 66 | 5 | 7.6% |
| 工业和信息化部 | 49 | 3 | 6.1% |
| 金融监管总局 / 国家医保局 | 19 / 19 | 1 / 1 | 5.3% |
| 商务部 | 71 | 2 | 2.8% |
| 农业农村部 | 36 | 1 | 2.8% |
| 科技部 | 42 | 1 | 2.4% |
| 市场监管总局 | 65 | 1 | 1.5% |
| **国务院** | **255** | **3** | **1.2%** |
| 全国人大常委会 | 30 | 0 | 0.0% |

**Evidence.** The pattern is a genre pattern before it is a ministry pattern. Tax,
finance, transport and culture pilots are **procedural** (a tax treatment, a certificate,
a settlement channel, a resumption of a business line); their rollout is a de-piloted
notice from the same bureau and the detector sees it. The State Council's 255 pilots are
mostly 批复 approving a locality's zone or reform (the zone_wave shape) and 自贸试验区
总体方案; their "scaling" is more 批复, or a renamed instrument from a higher body, and
the detector sees 1.2%. 商务部 (自贸区, 跨境电商综试区) and 市场监管总局 (证照分离 in
自贸区) sit low for the same reason. 全国人大常委会 pilots are 授权 decisions whose
successors are code amendments (刑诉法, 民诉法) that never carry the trial's name; 0 of
30 by construction. Read these rates as the **visibility** of each body's rollouts, not
their propensity to scale.

**By pilot `topics_algo` (≥20 pilots).** Government 19.2% (26), Tourism 17.2% (29),
Transport 15.2% (66), Culture 12.2% (49), Personnel 12.0% (25), Housing 10.5% (38),
Finance 10.0% (321), Legal 9.6% (52), Infrastructure 9.1% (55), Health 8.0% (75),
Welfare 7.9% (63), Commerce 6.8% (118), Energy 6.7% (30), Education 6.2% (48), Tech 4.9%
(163), Trade 3.3% (239), Environment 3.2% (31), Agriculture 2.4% (126), no topic 2.0%
(246). Trade (自贸区) and Agriculture (示范区 / 创建 programmes) are the zone-shaped
topics; the no-topic rows are mostly 批复.

---

## 6. How much of the gap does the detector close?

| step | rate | share of the 53.9% |
|---|---|---|
| memo §3b proxy | 0.4-1.2% | 1-2% |
| detector, all pilots | 5.9% (6.9% ex-mid-flight) | 11-13% |
| detector, trials only, precision-adjusted | ~6-8% | 11-15% |
| + hand-sample extrapolation (renamed / absorbed successors present in corpus) | ~45-75% (n=12, wide) | brackets 100% |

**Evidence-labeled conclusion.** The better detector by itself closes about a tenth of
the raw gap: the visible rate rises from ~1% to ~6-9% and the lag falls inside Wang &
Yang's duration. The hand sample says most of the remaining gap is measurement, split
three ways: **renamed or absorbing successors** (the largest substantive share, 7 of 12
mature non-zone cases), **zone designations** that are not trial-then-rollout
experiments (40% of unmatched pilots), and **mid-flight** pilots (20%). What remains a
true visibility floor after those three is small in the sample (2 of 12 never scaled
that we can see) but it is a floor in two further senses the sample cannot measure:
successors on central sites we do not crawl, and rollouts carried by instruments that
neither re-title nor cite the trial. The honest statement is that the corpus is
consistent with a scale rate in Wang & Yang's range once renaming is accounted for, and
that no title-matching detector will measure it directly. Closing it requires either an
LLM read of pilot and candidate bodies (does this instrument end that trial?) or an
external register of rollouts.

---

## 7. Threats to validity

1. **~52% citation resolution.** The citation channel (+10 successors) and the cite
   bonus in the score are floors. Unresolved edges can hide a successor that cites the
   pilot under a 文号 we do not hold.
2. **Title-core matching.** The detector is blind to any successor that drops the
   pilot's theme string. §4 shows this is the dominant failure, so every rate in §2 is a
   floor, and the direction of the bias is known.
3. **2000-start truncation.** The 2000-2009 cohort's 2,713-day median lag is the first
   same-theme instrument we hold, not the first that existed. Early cohorts under-count
   successors and over-state lags.
4. **Off-corpus rollouts.** ~60 central bodies crawled, not the ministerial universe.
   A ministry whose pilot sits on gov but whose 办法 sits on its own uncrawled site shows
   no successor.
5. **Pilot definition.** Title-only. 示范区 catches standing zone names (40% of the
   unmatched sample); untitled trials are missed. The trials-only universe (872) is the
   closer analog to Wang & Yang's unit but still over-inclusive.
6. **One coder.** Hand-check and no-successor categories were assigned by one reader
   with corpus lookups, not blind double-coding. The 12-case extrapolation in §4 is the
   weakest number here and is reported as a range.
7. **Publication date ≠ decision date.** Lags are proxies.
8. **Instrument collapse.** `instrument_id` pools mirrors across sites; a successor
   detected for one pilot wave (扩大启运港退税试点范围 2014 and 2016 both → 2024) counts
   twice at the instrument level. Wang & Yang count once per experiment. Their 53.9% is
   per experiment; ours is per pilot instrument, which pushes ours down.
9. **Scope.** Mechanism-level claims about a published document record. No regime-type
   labels.

---

## 8. Bottom line

Pilots detected: **1,271 instruments** (1,490 docs; memo 1,592 docs). Successors found:
**75** (5.9%; 6.9% ex-mid-flight; 8.0% / 9.5% on 试点-cued trials; 3.9% strict). Median
pilot → successor lag **564 days (1.5 years)**, inside Wang & Yang's 2.25 years. Detector
precision **76% strict / 87% lenient** on all 75 pairs (80% / 90% on the 40-pair
sample). The top reason a pilot shows no successor, once zone designations and
mid-flight pilots are set aside, is that **its rollout was published under a renamed or
absorbing instrument** (9 of 12 mature substantive cases have a successor in the corpus
the core match cannot reach). The replication's 0.4-1.2% was a detection artifact of
its title-family method by roughly an order of magnitude; the remaining distance to
53.9% is mostly renaming and definition, with an unmeasurable off-corpus floor
underneath.

---

## Appendix: method, SQL, scoring sketch

All queries ran against `file:/root/china-governance/documents.db?mode=ro` from
`scripts/rnd/analysis/successor_detector.py` (run time ~70 s on the droplet). Rerun:
`.venv/bin/python3 scripts/rnd/analysis/successor_detector.py --out /tmp/succ` writes
`pairs.tsv` (all pairs with score components and cores), `handcheck.tsv` (the 40-pair
sample), `nomatch_sample.tsv` (30 no-successor pilots with a loose-probe list). The
hand verdicts live in the script (`HANDCHECK`, `NOMATCH_WHY`) so precision is recomputed
on every run for the pairs still detected.

```sql
-- Universe: central promulgations with a clean date (doc_identity side table)
SELECT d.id, d.title, d.date_published, d.site_key, d.document_number, d.topics_algo,
       di.lead_issuer, di.instrument_id, di.instrument_role
FROM doc_identity di JOIN documents d ON d.id = di.doc_id
WHERE di.admin_level_doc = 'central' AND di.genre = 'promulgation'
  AND di.date_quality = 'good';
-- then in Python: parse date (2000-2026), collapse on instrument_id (canonical copy,
-- topics unioned over mirrors), pilot = title ~ 试点|试验区|先行先试|示范区,
-- candidate = later, no pilot cue, not 批复/的函/复函.

-- Long-horizon central sites (robustness subset)
SELECT d.site_key FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level = 'central' AND length(d.date_published) >= 10
  AND d.date_published BETWEEN '2000' AND '2027'
GROUP BY d.site_key
HAVING min(substr(d.date_published,1,4)) <= '2012'
   AND max(substr(d.date_published,1,4)) >= '2026' AND count(*) >= 500;
-- -> cac chinatax cppcc gov mee mof mofcom most ndrc npc sic

-- Citation channel / cite bonus: edges among central promulgations, pooled on instrument
SELECT source_id, target_id FROM citations WHERE target_id IS NOT NULL;
```

**Core.** `theme_core(title)` = shortest institutional core from
`extract_citations._title_cores_of_title` (else the title) → strip issuer masthead
(`^(国务院办公厅|…|[一-鿿]{2,12}(部|委|局|署|行|会|院|总局|办公厅|办公室))(…)*`) → strip
boilerplate (文号, 第N批, years, 关于/印发/开展/进一步/做好/实施/推进/…, 的通知/的意见/
方案/办法/工作/名单/试行/暂行/的/和/及/与/等) → strip pilot markers (试点工作/试点城市/
…/试点, 综合试验区/试验区, 先行先试/先行区, 示范区/示范城市/示范园区/示范基地/示范) →
remove punctuation → `_norm_title`. Keep if ≥4 chars.

**Candidate pool.** Bigram inverted index over candidate cores; a candidate is scored
only if it shares ≥ max(2, 40% of the pilot core's bigrams) and is dated after the pilot.

**Score.**
```
sim   = 1.00 if cores equal
        0.85 if pilot core (≥5) ⊂ candidate core
        0.80 if candidate core (≥6) ⊂ pilot core and covers ≥70% of it
        else bigram Dice(pilot core, candidate core)
gate  : sim ≥ 0.60; if sim < 0.85 the candidate title must carry a generalization cue
        (全面推开|全面实施|全面推广|全面推行|推广|在全国范围|全国范围|扩大…范围|正式实施|
         复制推广|总结推广|经验推广|深化|办法|条例|规定|实施细则)
issuer: same lead_issuer or a higher body (国务院/国办 over a ministry; 中共中央/全国人大
        over 国务院) = 1.0; either side unknown = 0.5; a different peer body = reject
topic : Jaccard(topics_algo) when both carry topics (0 = reject); 0.5 if either is empty
cite  : 1 if the candidate (or a mirror) cites the pilot (or a mirror)
lag   : > 0 days required; −0.05 if > 10 years
score = 0.50·sim + 0.20·topic + 0.15·cue + 0.15·issuer + 0.10·cite + lag_pen
keep  : best candidate per pilot with score ≥ 0.62 (tie: shorter lag)
strict: kind ∈ {exact, containment}
citation channel: any later non-pilot central promulgation that cites the pilot and
        carries a cue (no core match required); reported as a union, not in the headline
```
