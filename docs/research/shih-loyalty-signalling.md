# Loyalty displays and patronage in the Xi era: a scoped replication of Shih (2008)

*First pass, 2026-11-12. Pre-registration: `docs/working/prereg-shih-loyalty.md` (written before
any outcome term was counted, with two dated amendments). Script:
`scripts/rnd/analysis/shih_loyalty.py`. Evidence labels: **measured** = counted in the corpus or
read from a named source, command in the appendix; **stated** = what a source says;
**inferred** = my reading of measured patterns; **unverified** = believed, not checked here.*

## The question

Does a province echo Xi-personal loyalty formulations more when its Party secretary is a career
associate of Xi? Shih's answer (2008) for the Jiang era was yes. This memo asks the same question
of 2023-26 provincial government documents, nets out ordinary policy vocabulary with a placebo
set, and registered its predictions before counting.

**Short answer (measured):** no. Net of placebo vocabulary, the two provinces led by Xi
associates with usable coverage (Guangdong, Shaanxi) carry Xi-personal loyalty formulations at
the same or a slightly lower rate than the other provinces. The registered statistic is
**D_rel = -0.146** (permutation p = 0.79). The Shih-sign prediction did not hold. What the corpus
does show is that uptake is **uneven**, and that the unevenness follows province wealth and the
frontier, not patronage.

## What Shih did, and what we can and cannot replicate

**The paper (stated, abstract read via OpenAlex for DOI 10.1017/S0022381608081139; full text
not accessible from here):** Victor Shih, "'Nauseating' Displays of Loyalty: Monitoring the
Factional Bargain through Ideological Campaigns in China", *Journal of Politics* 70(4), 2008,
1177-1192. The abstract's argument: patrons learn clients' true loyalty only in a crisis, when
they can least enforce the bargain; where norms forbid personality cults, "public, exaggerated
praises" are a credible signal because the flatterer pays the social cost of being despised;
the measure is "content analysis of provincial newspapers between 2000 and 2004"; OLS and PCSE
estimations test whether "provincial faction members were more likely to echo an ideological
campaign launched by their patron" (Jiang Zemin's Three Represents); further analysis asks
whether faction members "in rich and poor localities echoed the campaign in different ways"; the
conclusion is that campaigns work "as radars".

**The follow-up (stated, abstract via OpenAlex):** Jinghan Zeng, "Changing Manners of Displaying
Loyalties through Ideological Campaigns in Post-Deng China", *Journal of Contemporary China*,
2016. On 2005-12 provincial newspapers with PCSE, protégés of both Hu and Jiang were **less**
likely to echo their patron's campaign, read as campaigns shifting from monitoring followers to
recruiting new ones. This gives a registered competing sign.

| | Shih (2008) | this replication |
|---|---|---|
| period | 2000-04 (one patron's campaign, Three Represents) | 2023-01 to 2026-11 (2022 for the within-province test) |
| text | provincial Party newspapers | provincial, municipal, district and department **government** documents, media excluded |
| outcome | echo of the patron's campaign | documents per 1,000 carrying Xi-personal loyalty formulations, net of a placebo set |
| treatment | faction membership (Jiang clients) | secretary in post on the document date shares a Fujian 1985-2002 or Zhejiang 2002-07 career with Xi |
| estimation | OLS / PCSE on a province panel | spell means, exact permutation; a within-province before/after |
| rich/poor | tested (direction not stated in the abstract) | exploratory only |

**What we cannot replicate (inferred from the design):**

1. **The newspaper.** A Party daily is the provincial committee's own voice. Government documents
   are mostly bureaux and city governments, several layers below the secretary. The signal, if
   any, is diluted by distance from the signaller.
2. **A contested patronage market.** Shih's mechanism needs rival coalitions to recruit from.
   After 2022 every Politburo-level patron of note is Xi, so the "alternative coalition" the
   signal deters is weak. A null here is a statement about this period as much as about Shih.
3. **Power.** Only **two** associate-led provinces have usable coverage. Tianjin (陈敏尔) has 1
   document in 2023-26, Henan (楼阳生 until 2024-12-31) 38, Anhui (郑栅洁 until 2023-03-14) 0.
   Every cross-sectional test is close to a two-province comparison, which the prereg said in
   advance.
4. **Shih's own measure.** We count fixed formulations, not his coded "exaggerated praise"; we
   could not read his coding scheme.

## Design (measured where numbers are given)

- **Population.** `doc_identity.admin_level_doc` in provincial / municipal / district /
  department; ISO `date_published` 2022-01-01 to 2026-11-12; body of at least 200 characters; site
  placed in a province by `build_diffusion_events.province_of` (this drops 464 rows from national
  sites such as `miit` that are about a province but not issued by it); media and party-theory
  sites dropped. Province = `doc_identity.province` (73,819 rows) else the site's province
  (39,271 rows). Province fallback taken from the local `f5438b4` module copy, which carries the
  `suzhou_ah -> js` override that the droplet checkout lacks. **One copy per (province,
  normalized title)**, the longest body: **104,391 documents**.
- **Term sets (frozen in the prereg).** Loyalty B, discretionary and intensified (primary):
  两个确立; 两个维护; 坚决拥护; 感恩奋进 | 感恩总书记 | 感党恩; 牢记...嘱托; 总书记亲自; 人民领袖.
  Loyalty A, standard and mandated: 习近平新时代中国特色社会主义思想; 以习近平同志为核心的党中央;
  习近平总书记...重要讲话 / 重要指示 / 重要论述. Placebo P: 高质量发展; 新质生产力; 营商环境.
  Counted by Python regex on title + body, so the FTS trigram floor does not apply.
- **Statistic.** Spell rates averaged unweighted within group;
  `D_rel = ln(B_assoc / B_non) - ln(P_assoc / P_non)`. Positive = associates echo loyalty
  vocabulary more than their general policy vocabulary would predict.
- **Clean population (Amendment 2, added after the first run, not confirmatory).** At least three
  。 in the body and a title that is not a procurement notice. Added because Qinghai's `qinghai`
  site stores portal chrome as the body (1,876 of 1,943 Qinghai documents have fewer than three
  。; every sampled body starts 藏文版 | 设为首页) and Yunnan is 343 of 410 procurement notices.
  90,734 rows survive.

### Treatment: secretaries in post (measured against sources, 2026-11-12)

`officials.db` is an April-2026 snapshot whose `overlaps` table only covers Politburo
co-membership for Xi (all 54 of his overlap rows are 中央政治局), so the rule was applied to
`career_records` directly and every secretary was checked against a web source (en.wikipedia
"List of current Chinese provincial leaders" and the per-province "Party Secretary of X" pages;
zh.wikipedia biographies for 尹弘, 周祖翼, 胡昌升, 黄强, 楼阳生, 赵一德). Thirteen secretaries
changed between 2026-05 and 2026-10 alone; the snapshot knew none of the 2026 changes.

| associate tier | secretary | province, spell | evidence |
|---|---|---|---|
| core | 黄坤明 | Guangdong, 2022-10-28 on | `career_records`: Fujian 1982-99, Zhejiang 2000-10 |
| core | 赵一德 | Shaanxi, 2022-11-27 on | Zhejiang Youth League 1996-2006, 温州 2006-08 (zh.wikipedia) |
| core | 陈敏尔 | Tianjin, 2022-12-08 on | Zhejiang 2001-12 (`career_records`); **1 document**, unusable |
| core | 楼阳生 | Henan, to 2024-12-31 | Zhejiang 1991-2009 incl. 丽水 secretary 2003-08 (zh.wikipedia); **38 documents**, unusable |
| core | 郑栅洁 | Anhui, to 2023-03-14 | 厦门 1997-2008; no Anhui documents in the spell |
| sh07 | 沈晓明 | Hunan 2023-03-14 to 2026-10-24 | Shanghai 2006-08 (`career_records`) |
| sh07 | 尹弘 | Jiangxi | 闸北区 2004-08 (zh.wikipedia) |
| sh07 | 徐麟 | Guizhou | Shanghai 2003-08 (`career_records`); 26 documents, unusable |

Decided as non-associates before measuring: 周祖翼 (Tongji University in 2007, a Ministry of
Education university, not the Shanghai committee); 许昆林 (a 1986-87 teaching secondment to Fujian
from the state price bureau, matched by the province field only); 黄强 (a Shanghai institute post
that ended by 2006). 王晓晖 (Sichuan) is absent from `career_records` and the zh/en pages tried
returned 404; classed non-associate from memory (**unverified**). Full spell list:
`shih_loyalty.py:SPELLS`.

## Results

### 1. The national baseline moves with the political calendar (measured)

| half-year | n | B /1k | A /1k | P /1k | 两个确立 /1k | 新质生产力 /1k |
|---|---|---|---|---|---|---|
| 2022H1 | 5,768 | 57.9 | 241.0 | 261.6 | 42.8 | 0.2 |
| 2022H2 | 5,930 | 32.7 | 187.9 | 232.5 | 25.0 | 0.0 |
| 2023H1 | 8,303 | 48.4 | 215.1 | 377.9 | 40.2 | 0.0 |
| 2023H2 | 8,089 | 31.8 | 207.4 | 334.2 | 26.6 | 3.1 |
| 2024H1 | 8,207 | 42.3 | 224.4 | 365.3 | 34.7 | 66.0 |
| 2024H2 | 8,211 | 26.5 | 169.3 | 314.0 | 21.2 | 67.0 |
| 2025H1 | 7,769 | 36.8 | 193.1 | 337.0 | 30.9 | 68.5 |
| 2025H2 | 9,999 | 29.6 | 152.7 | 320.5 | 22.3 | 56.1 |
| 2026H1 | 10,093 | 34.8 | 160.1 | 329.4 | 24.4 | 72.4 |
| 2026H2 | 32,022 | 38.2 | 127.3 | 264.5 | 25.0 | 39.6 |

B is higher in every first half than the second half before it (the 两会 and annual work-report
season, *inferred*), and the pooled series is not stable composition (2026H2 is three times any
earlier half, the crawl onboarding). This is why the 2026-only cut (T1b) was added before the
outcomes were read.

### 2. T1, the registered cross-section: a null with the wrong sign (measured)

Spells with at least 150 documents, 2023-01-01 to 2026-11-12 (selected rows; all 30 spells are in
the script output):

| province | secretary | tier | n | B /1k | A /1k | P /1k |
|---|---|---|---|---|---|---|
| Guangdong | 黄坤明 | core | 46,493 | 40.2 | 202.1 | 357.5 |
| Shaanxi | 赵一德 | core | 1,041 | 47.1 | 200.8 | 344.9 |
| Fujian | 周祖翼 | - | 5,845 | 37.8 | 128.3 | 210.6 |
| Jiangsu | 信长星 | - | 5,800 | 19.7 | 154.7 | 295.3 |
| Beijing | 尹力 | - | 4,007 | 11.7 | 83.6 | 284.5 |
| Shanxi | 唐登杰 | - | 3,031 | 53.1 | 169.9 | 330.9 |
| Xinjiang | 陈小江 | - | 2,840 | 57.7 | 154.2 | 337.7 |
| Chongqing | 袁家军 | - | 1,999 | 5.5 | 83.5 | 181.1 |
| Inner Mongolia | 王伟中 | - | 1,158 | 71.7 | 168.4 | 371.3 |
| Tibet | 胡昌升 | - | 405 | 192.6 | 318.5 | 286.4 |

| test | associate spells (docs) | non (docs) | B assoc / non | P assoc / non | D_rel | perm p |
|---|---|---|---|---|---|---|
| **T1 registered** | 2 (47,534) | 26 (42,951) | 43.6 / 33.8 | 351.2 / 235.4 | **-0.146** | 0.792 |
| T1b, 2026 only | 2 (6,602) | 25 (33,861) | 47.6 / 35.9 | 361.7 / 232.6 | -0.160 | 0.746 |
| T1 clean | 2 (43,962) | 21 (34,084) | 45.6 / 46.9 | 364.2 / 314.3 | -0.175 | 0.739 |
| T1b clean | 2 (6,159) | 20 (26,638) | 49.3 / 50.2 | 374.6 / 310.9 | -0.204 | 0.671 |

The raw loyalty rate **is** 29% higher under associates (43.6 against 33.8 per 1,000), which is
the comparison Shih's design would have made. But the placebo rate is 49% higher (351.2 against
235.4). Associate-led Guangdong and Shaanxi simply write denser policy prose; per unit of policy
vocabulary they carry slightly less loyalty vocabulary. In the clean population the raw gap
disappears altogether (45.6 against 46.9). *Inferred:* a raw-count replication of Shih on this
corpus would have "confirmed" him through document composition alone.

The term-level split (2026, pooled documents, associate n = 6,602, non n = 34,250) points the same
way: 两个确立 1.43x and 两个维护 1.40x, below every placebo term (高质量发展 1.44x, 营商环境 1.97x,
新质生产力 2.19x); and the most effusive formulas run **lower** under associates: 感恩 0.52x,
牢记嘱托 0.84x, 人民领袖 0.31x (0.2 against 0.5 per 1,000).

### 3. Robustness: no variant reaches the Shih sign with any support (measured)

| variant | window | assoc (docs) | non (docs) | D_rel | perm p |
|---|---|---|---|---|---|
| leave largest site out | T1 | 2 (41,316) | 17 (27,557) | -0.513 | 0.322 |
| leave largest site out | T1b | 2 (5,803) | 17 (21,499) | -0.600 | 0.287 |
| drop Fujian and Zhejiang | T1 | 2 (47,534) | 23 (35,661) | -0.150 | 0.793 |
| sh07 counted as treated | T1 | 4 (48,911) | 26 (42,951) | -0.033 | 0.936 |
| sh07 counted as treated | T1b | 4 (7,865) | 25 (33,861) | -0.057 | 0.887 |
| A (mandated) set instead of B | T1 | 2 (47,534) | 26 (42,951) | +0.139 | 0.616 |
| provincial-level documents only | T1 | 1 (4,551) | 16 (19,979) | +0.155 | 0.929 |
| provincial-level documents only | T1b | 1 (1,006) | 13 (13,490) | -0.228 | 0.917 |
| genre promulgation | T1 | 2 (6,953) | 11 (5,659) | +0.046 | 0.936 |
| genre readout | T1 | 2 (16,273) | 19 (7,693) | -0.119 | 0.776 |
| genre other | T1 | 2 (21,769) | 24 (22,170) | -0.482 | 0.500 |
| clean + leave largest site out | T1 | 2 (38,312) | 17 (22,391) | -0.537 | 0.327 |
| genre implementing | T1b | no associate spell reaches 100 documents | | | |

Intensity per 10,000 body characters (2026): B 0.531 under associates against 0.500 (+6%), P
6.225 against 4.100 (+52%). Same reading.

### 4. T1c, year-standardized: positive, and why it should not be believed (measured, then inferred)

| year | assoc cells (docs) | non cells (docs) | B assoc / non | P assoc / non | D_rel |
|---|---|---|---|---|---|
| 2023 | 1 (13,699) | 5 (2,409) | 43.4 / 18.9 | 365.9 / 284.8 | +0.582 |
| 2024 | 1 (13,580) | 5 (2,271) | 38.2 / 8.8 | 347.2 / 285.5 | +1.274 |
| 2025 | 1 (13,466) | 8 (3,588) | 37.9 / 13.9 | 347.5 / 287.2 | +0.816 |
| 2026 | 2 (6,602) | 26 (33,978) | 47.6 / 34.5 | 361.7 / 231.2 | -0.127 |

Weighted mean **+0.748** (clean: +0.715). Before 2026 the only non-associate cells that reach 100
documents a year are Beijing, Jiangsu, Shanghai, Chongqing and Fujian, four of which are the
lowest-B provinces in the country (section 6). *Inferred:* 2023-25 compares Guangdong with the
rich municipalities, not with the median province; as soon as every province is observed (2026)
the sign returns to the T1 value. A positive T1c is a coverage artifact, reported because it was
registered.

### 5. T2 and T3, within-province switches: not testable at this coverage (measured)

The 2022 reshuffle is a clean natural experiment on paper: Guangdong and Shaanxi **gained** an
associate, Beijing (蔡奇), Shanghai (李强) and Chongqing (陈敏尔) **lost** one, the rest changed
between non-associates. Pre = 2022-03-01 to 09-30, post = 2023-01-15 to 08-15, statistic
`ln(B_post/B_pre) - ln(P_post/P_pre)`:

| province | group | n pre | n post | B pre / post | P pre / post | statistic |
|---|---|---|---|---|---|---|
| Guangdong | gainer | 4,998 | 8,095 | 47.8 / 46.9 | 230.3 / 388.0 | -0.540 |
| Beijing | loser | 665 | 463 | 19.5 / 49.7 | 327.8 / 334.8 | +0.912 |
| Jiangsu | control | 625 | 643 | 19.2 / 15.6 | 281.6 / 312.6 | -0.315 |
| Fujian | control | 163 | 110 | 18.4 / 54.5 | 159.5 / 254.5 | +0.619 |
| Shaanxi | gainer | 0 | 0 | | | |
| Shanghai, Chongqing | losers | 75, 71 | 97, 65 | (under 100) | | |

The one gainer falls and the one loser rises, the wrong way round for Shih, but the two
controls span -0.32 to +0.62, so one province per arm is inside the noise. **Null, untestable
as registered.** T3 (any new secretary, 120 days either side) found **no** arrival from 2024-06
to 2026-07 with 60 documents on both sides; the best, Hubei on 2026-05-30, has 44 before. The
Henan (2024-12-31, associate out) and Anhui (2023-03-14, associate out) switches have 0 documents
around them.

### 6. T4, distribution: uptake is uneven, but not along patronage lines (measured, then inferred)

Provinces with at least 300 documents in 2026 (registered n = 22; clean n = 20):

| measure | B (loyalty) | A (mandated) | P (placebo) |
|---|---|---|---|
| CV, registered | 0.696 | 0.562 | 0.383 |
| CV, clean | 0.634 | 0.425 | 0.182 |
| SD of ln(rate), clean | 0.712 | 0.419 | 0.201 |
| share within 25% of the median, clean | 0.30 | 0.55 | 0.90 |

A binomial floor (every province at the pooled B rate of 46.1 per 1,000) predicts a CV of about
0.13. Loyalty vocabulary is **3.5 times as dispersed** as placebo vocabulary on the log scale
(clean). My forecast (B no more dispersed than P) was **wrong**; this is the result in the
direction Shih's framing expects.

The dispersion has a shape (clean, 2026, ordered by 2024 GDP per capita from
`data/provincial_gdp.csv`):

| province | GDP pc (k yuan) | B/P | 两个确立 /1k | 感恩 /1k | 牢记嘱托 /1k |
|---|---|---|---|---|---|
| Beijing | 228 | 0.034 | 7.3 | 0.0 | 0.7 |
| Shanghai | 217 | 0.072 | 12.2 | 0.0 | 4.4 |
| Jiangsu | 161 | 0.089 | 16.9 | 8.1 | 9.8 |
| Fujian | 138 | 0.208 | 31.9 | 4.4 | 20.3 |
| Guangdong (core) | 111 | 0.111 | 33.9 | 3.0 | 9.8 |
| Chongqing | 101 | 0.052 | 6.1 | 0.0 | 2.0 |
| Shaanxi (core) | 90 | 0.157 | 43.7 | 5.9 | 7.1 |
| Xinjiang | 79 | 0.173 | 43.6 | 15.4 | 22.8 |
| Jiangxi | 76 | 0.198 | 35.5 | 31.3 | 35.5 |
| Tibet | 75 | 0.434 | 96.5 | 34.6 | 14.6 |
| Heilongjiang | 54 | 0.206 | 56.2 | 8.2 | 12.3 |

Spearman(GDP per capita, B/P) = **-0.355** (clean, n = 20; registered -0.282, n = 22). An
exploratory OLS gives `ln(B/P) = 6.10 - 0.720 ln(GDP pc) + 0.160 assoc` (clean, n = 20, 2
associate provinces); the associate coefficient turns positive once wealth is held, but its exact
permutation p over all 190 relabellings is **0.711** (registered: +0.221, p = 0.714).

*Inferred:* the loudest loyalty registers are the frontier and old-base provinces (Tibet,
Xinjiang, Inner Mongolia, Jiangxi), where 感恩 / 感党恩 and 牢记嘱托 are campaign formulas in their
own right, and the quietest are the richest municipalities. That is a rich/poor pattern, the
second dimension Shih's abstract says he explored, but here it is a property of the province, not
of the secretary's patron. Two readings fit and the corpus cannot separate them: poorer and
frontier provinces have more to signal (transfers, security mandates), or their document mix
leans to political-education material whatever the secretary's ties.

## Verdict against the pre-registration

| registered prediction | result |
|---|---|
| Shih sign: T1 D_rel > 0, about +0.2 | **did not hold.** -0.146 (p 0.79); every B variant is negative or null |
| My forecast: \|D_rel\| < 0.15 | held for T1 (-0.146, barely); missed for T1b (-0.160) and clean (-0.175, -0.204) |
| Shih: T2 gainers rise, losers fall | wrong direction at n = 1 per arm; untestable |
| T3 arrival rise in 坚决拥护 | untestable (no switch with 60 documents per side) |
| Shih: T4 B more dispersed than P | **held** (SD of ln 0.71 against 0.20, clean); my null forecast was wrong |
| My forecast: A less dispersed than P | wrong (A 0.42 against P 0.20) |

Zeng's negative sign is closer to what we see than Shih's positive one, but our negatives are
nowhere near significance, so the honest summary is a null on the patronage question.

## Caveats

- **Two treated provinces.** Guangdong is 46,493 of the 47,534 associate documents in T1. Every
  cross-sectional number is in effect "Guangdong and Shaanxi against the rest". The smallest
  attainable permutation p with 2 of 28 spells treated is 1/378.
- **Coverage is not the province.** Shanxi is 72% `jcgov` (晋城), Jiangxi 98% `ganzhou`, Sichuan 93%
  `abazhou`. Leaving the largest site out moves T1 from -0.146 to -0.513, the largest shift of any
  robustness pass: the statistic is sensitive to which sites we hold, in a direction that only
  strengthens the null.
- **Government documents are not the secretary's voice.** Most rows are municipal, district and
  bureau texts; the provincial-level-only cut keeps 1 associate spell.
- **Term validity.** 坚决拥护 also endorses work reports (揭阳代表团...完全赞同、坚决拥护报告, doc
  913996), not only the leader; it is 1 to 2 per 1,000, so it cannot move the totals. A sample of
  8 B hits was read: 7 were Xi-personal formulas in Party-building or meeting contexts, 1 was the
  work-report use.
- **Mandated formulas.** 两个维护 entered the Party constitution in 2022 and 两个确立 is a plenum
  formula (*stated*, from memory, not re-checked here), so the B set mixes compliance with
  discretion. The most discretionary terms (感恩, 人民领袖) are also the rarest.
- **Treatment completeness.** The rule only sees co-location in Fujian, Zhejiang and Shanghai.
  Xi's ties made through the central apparatus after 2007 (中央党校, 中办) are not coded, and a
  broader rule would treat more secretaries (*inferred*; not tested).
- **Publication is not adoption**, and one copy per title per province means a 两个确立 sentence
  repeated across forty bureau reposts counts once.

## Appendix: reproduce

```bash
# droplet, read-only; scripts staged in /tmp/shih (module copies from local main f5438b4)
cd /tmp/shih
/root/china-governance/.venv/bin/python3 -u shih_loyalty.py --db /root/china-governance/documents.db \
    --repo /tmp/shih/repo --coverage            # denominators only (run before the prereg)
/root/china-governance/.venv/bin/python3 -u shih_loyalty.py --db /root/china-governance/documents.db \
    --repo /tmp/shih/repo --measure --out /tmp/shih/flags.tsv   # 104,391 rows, ~14 s
# anywhere, from the flags file
python3 scripts/rnd/analysis/shih_loyalty.py --analyze --flags flags.tsv   # every table above
```

The core selection, as SQL (the script adds the site-province gate, the media exclusion and the
per-province title dedup in Python):

```sql
SELECT d.id, d.site_key, d.title, substr(d.date_published,1,10), i.genre,
       i.province, i.admin_level_doc, LENGTH(d.body_text_cn), d.body_text_cn
FROM doc_identity i JOIN documents d ON d.id = i.doc_id
WHERE i.admin_level_doc IN ('provincial','municipal','district','department')
  AND substr(d.date_published,1,10) BETWEEN '2022-01-01' AND '2026-11-12';
```

Sources for the secretary spells: en.wikipedia.org/wiki/List_of_current_Chinese_provincial_leaders
and the "Party_Secretary_of_<Province>" pages for Anhui, Hunan, Hubei, Henan, Hebei, Tibet, Gansu,
Xinjiang, Liaoning, Zhejiang, Ningxia, Qinghai, Shanxi, Jilin, Inner Mongolia, Yunnan, Hainan;
zh.wikipedia biographies of 尹弘, 周祖翼, 胡昌升, 黄强, 楼阳生, 赵一德 (all read 2026-11-12). Day-level
dates for 王忠林 (Hubei, "December 2024") and 沈晓明 (Hunan, "March 2023") were set to 2024-12-31 and
2023-03-14 to match the same-day reshuffles (**unverified** to the day).
