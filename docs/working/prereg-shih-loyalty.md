# Pre-registration: Shih (2008) loyalty signalling, Xi era

*Written 2026-11-12, before any outcome term was counted. Only denominators (deduped document
counts per province, site and genre) had been computed when this was written. Any later change
to a term set, a rule or a threshold is appended below as a dated note, never edited in place.*

## What is being tested

Shih (2008): in a system with norms against personality cults, exaggerated public praise of the
patron is a costly and therefore credible loyalty signal, so a patron's clients echo the patron's
ideological campaign more than non-clients do. Our analogue: do provinces whose Party secretary
is a career associate of Xi Jinping carry more Xi-personal loyalty formulations in their
government documents than provinces whose secretary is not, relative to ordinary policy
vocabulary?

Competing prediction, Zeng (2016, *Journal of Contemporary China*), measured on 2005-12
provincial newspapers: protégés of Hu and of Jiang were LESS likely to echo their patron's
campaign. That predicts a negative sign.

## Population

- Documents in `doc_identity` with `admin_level_doc` in provincial / municipal / district /
  department, dated 2022-01-01 to 2026-11-12 (`date_published`, ISO date only), body
  `LENGTH(body_text_cn) >= 200`.
- From a site that `build_diffusion_events.province_of(site)` places in a province (this drops
  national sites such as `miit` and `npc` whose pages are about a province but not issued by
  it), and not a media site (the `discourse_vocab` media/party-theory/research sets).
- Province: `doc_identity.province`, else `province_of(site_key)` (the local `f5438b4` copy,
  which carries the `suzhou_ah -> js` override; the droplet checkout is older).
- One copy per (province, normalized title): the copy with the longest body.

## Term sets (frozen)

Counted by Python regex on title + body (no FTS, so the 3-character trigram floor does not apply).

**Loyalty B, discretionary and intensified (PRIMARY outcome):** 两个确立; 两个维护; 坚决拥护;
感恩奋进 | 感恩总书记 | 感党恩; 牢记 ... 嘱托 (within 8 characters); 总书记亲自; 人民领袖.

**Loyalty A, standard and mandated (secondary):** 习近平新时代中国特色社会主义思想;
以习近平同志为核心的党中央; 习近平总书记 ... 重要讲话 / 重要指示 / 重要论述 (within 40 characters).

**Placebo P (no personal-loyalty content):** 高质量发展; 新质生产力; 营商环境.

Rate = documents carrying at least one term of the set, per 1,000 documents. Secondary
intensity = term occurrences per 10,000 body characters.

## Treatment

Secretary in post on the document date (spells in `shih_loyalty.py:SPELLS`, checked against
web sources because `officials.db` is an April-2026 snapshot).

- **core associate**: `officials.db` career record in Fujian overlapping 1985-2002 or Zhejiang
  overlapping 2002-2007 (Xi's sustained provincial tenures), confirmed by a biography.
- **sh07**: Shanghai service in 2007 only (Xi's seven months there). Not treated in the primary
  test; treated in a robustness pass.
- Everyone else: non-associate. A secretary missing from `officials.db` is checked on the web.

## Tests

**T1, cross-section (2023-01-01 to 2026-11-12).** Unit: province x secretary spell with at
least 150 deduped documents. Statistic, spell rates averaged unweighted within group:
`D_rel = ln(B_assoc / B_non) - ln(P_assoc / P_non)` (primary) and
`D_abs = (B_assoc - B_non) - (P_assoc - P_non)` in per-1,000 points. Permutation p-value from
10,000 random relabellings of the spells.

**T2, within-province, the 2022 reshuffle.** Most secretaries changed between 2022-10-28 and
2023-01-03. Gainers of an associate: Guangdong (李希 -> 黄坤明), Shaanxi (刘国中 -> 赵一德).
Losers: Beijing (蔡奇 -> 尹力), Shanghai (李强 -> 陈吉宁), Chongqing (陈敏尔 -> 袁家军).
Controls: every other province with at least 100 deduped documents in both windows (Anhui
excluded: its associate left on 2023-03-14, inside the post window). Common calendar windows
for all: pre = 2022-03-01 to 2022-09-30, post = 2023-01-15 to 2023-08-15. Statistic per
province: `ln(B_post/B_pre) - ln(P_post/P_pre)`.

**T3, new-secretary arrival (any secretary, 2024-06 to 2026-05 arrivals with 120 post days).**
Pre = 120 days before arrival, post = days 15 to 135 after. Same statistic, pooled mean across
switches with at least 60 documents on each side.

**T4, distribution.** Provinces with at least 300 deduped documents in 2023-26: coefficient of
variation of B rates against the CV of P rates and of A rates.

## Predictions

- **Shih sign (the hypothesis):** T1 `D_rel > 0`, roughly +0.2 (associates about 20% higher on
  B, net of placebo). T2: gainers rise relative to controls, losers fall. T4: B more dispersed
  than P.
- **My forecast:** a null. `|D_rel| < 0.15` in T1; no gainer/loser ordering in T2; B no more
  dispersed than P, and A less dispersed than P (the Xi-era formulas are centrally mandated,
  written into the 2022 Party constitution for 两个维护 and into plenum resolutions for 两个确立,
  so they should read as compliance, not as a signal). T3: a short post-arrival rise in
  坚决拥护, which is the appointment-meeting formula, and little else.
- **Power warning, written before measuring:** only two core-associate provinces have usable
  2023-26 coverage (Guangdong 46,619 deduped documents; Shaanxi 1,064). Tianjin (15), Henan (55)
  and Anhui (mostly a mis-placed Suzhou site) cannot carry a test. Guangdong alone is about 45%
  of the population. T1 is therefore close to a two-province comparison, and it will be reported
  as such whatever the sign.

## Robustness (all reported, none chosen after the fact)

Leave-one-site-out (drop each province's largest site); genre splits (promulgation,
implementing, readout separately where a spell keeps at least 100 documents); drop Fujian and
Zhejiang (Xi's own provinces, a place tie rather than a person tie); sh07 counted as treated;
A instead of B; intensity per 10,000 characters; provincial-level documents only.

**Committed:** every test above is reported with n, including nulls and wrong-sign results.

## Amendment 1, 2026-11-12, after counting documents per province per year and before any outcome

Denominators by year (deduped, body >= 200) show the time mix differs by province far more
than expected: Guangdong is spread over 2022-25 (8,939 / 13,699 / 13,580 / 13,466 / 5,748 for
2022-26), while most other provinces are 70-99% 2026 documents (Shaanxi 0 / 25 / 90 / 72 / 854;
Shanxi 1 / 2 / 20 / 54 / 2,957). Placebo P2 新质生产力 was coined in September 2023, and any
formula can trend, so a 2023-26 pooled cross-section compares Guangdong's 2023-25 against other
provinces' 2026. Added, before measuring:

- **T1b, the same statistic restricted to 2026-01-01 to 2026-11-12**, where every province is
  observed in the same months. I expect T1b to be the more credible version; T1 is still
  reported as registered.
- **T1c, year-standardized T1:** each spell's rate computed within calendar year, and the
  associate/non-associate contrast taken within year, then averaged over years weighted by the
  associate group's documents.
- T2 feasibility, counted not tested: Shaanxi has 0 documents in the 2022 pre-window, so the
  gainer group is Guangdong alone; the controls that reach 100 documents in both windows will be
  few (likely Jiangsu, Fujian). T3 likely has one usable switch (Hubei, 2026-05-30). Both are
  reported with their n regardless.

## Amendment 2, 2026-11-12, AFTER the first full run (a deviation, labelled as such)

The first run showed two populations that are not policy text: Qinghai's `qinghai` site stores
the portal's page chrome as the body (1,876 of 1,943 Qinghai documents in 2023-26 have fewer
than three 。 characters; every sampled body begins 藏文版 | 设为首页 | 加入收藏), and Yunnan is
343 of 410 procurement notices (`yuxi`). Both flatten loyalty AND placebo rates toward zero. A
"clean" population is therefore added: body with at least three 。 and a title that is not a
procurement or tender notice (招标|中标|成交|采购|比选|询价|竞价|竞争性磋商|拍卖|挂牌出让).
**The registered population stays the headline;** the clean population is reported beside it,
and the memo says which way it moved each number. It was added after seeing T1 = -0.146, so it
cannot be read as a confirmatory test.

Also added after the first run, as exploratory only: the rich/poor cut (rank correlation of the
B/P ratio with 2024 GDP per capita, `data/provincial_gdp.csv`), dispersion on the log scale,
and where the most effusive terms (感恩, 牢记嘱托, 人民领袖) sit by province.
