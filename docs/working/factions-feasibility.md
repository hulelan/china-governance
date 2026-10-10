# w22775 (Factions in Nondemocracies): measured NOT feasible, and why

*`related-literature.md` rated Trebbi et al. (NBER w22775 / Econometrica 91(2):565, 2023) at
corpus fit **C** without looking, which was worth checking: the paper's data type is elite
biographies plus co-service ties, and `officials.db` holds 2,181 Central Committee members, 17,727
career records and 5,121 computed shared-posting overlaps. **Measured 2026-10-10: the rating is
right, but not for the stated reason.** We are not missing biographical data. The tie network is
**26% deliberative-body co-membership**, and once that is removed it reaches only **13 ties
between two Politburo members** — too shallow at the top, which is exactly where a balance test
lives.*

Probes: `probe_officials.py`, `probe_ties.py` (scratchpad; the measurements are below).

## 1. What officials.db actually supports

| | |
|---|---|
| officials | 2,181 (145 Politburo, 45 PSC) |
| with `birth_year` | 2,179 · with `home_province` **2,181** |
| `cc_congresses` parses | **2,181 / 2,181**, 0 failures — clean cohort axis (15th CC 317 … 20th CC 375) |
| career records | 17,727, **all** with `start_year`, `organization` and `admin_level` |
| officials with ≥1 career record | 1,628 of 2,181 (75%) |
| officials with ≥1 overlap | **629 of 2,181 (29%)** |

The biographical half is in good shape. Cohorts are clean, provinces are complete, and
`admin_level` on career records resolves (provincial 6,851 · central 3,711 · district 847 ·
municipal 202 · unknown 6,116).

## 2. The tie table is partly circular, and the rest is thin

5,121 overlap edges reduce to **2,312 distinct unordered pairs**. The single largest
tie-generating "organization" is **中央政治局, with 1,327 edges (26%)**.

That is not a shared posting. Two people both sitting on the Politburo co-occur there by
construction, and the composition of that body is the thing a factional-balance test is trying to
explain — so including it makes the measure partly circular. The same applies to 全国人民代表大会
and the Central Committee itself.

Dropping deliberative-body co-membership (中央政治局 / 中央委员会 / 中央书记处 / 全国人民代表 /
全国政协 / 中央军事委员会 / 中央纪律检查):

| | |
|---|---|
| working-posting pairs | **1,625** (70% of pairs) |
| officials with ≥1 working tie | 561 · with ≥2 ties 422 |
| **Politburo members with ≥1 working tie** | **47 of 145** |
| **PSC members with ≥1 working tie** | **13 of 45** |
| **working ties between two Politburo members** | **13** |

Thirteen internal ties cannot carry a claim about factional structure in the body, and 47 of 145
with any tie at all means two thirds of the relevant population is unconnected in the data.

## 3. And the surviving ties are geographically skewed

The working-tie organizations are dominated by autonomous regions and one north-eastern province:

    西藏自治区 618 · 广西壮族自治区 539 · 内蒙古自治区 345 · 新疆维吾尔自治区 176 ·
    宁夏回族自治区 164   = 1,842 of the tie-generating records

Five autonomous regions plus 黑龙江 (298) supply more ties than every ministry combined
(中国科学院 125 · 中央纪委 94 · 中央组织部 71). That is not plausible as a fact about where
officials co-serve; it is a fact about the data path. Either Baidu Baike bios enumerate
autonomous-region postings more fully, or `compute_overlaps.py` matches on organization-name
strings that happen to be more standardised for regions than for central bodies. **Which of the
two is untested**, and it should be settled before anyone uses this network for anything, because
it is the same shape as the hand-maintained-table bugs in CLAUDE.md: a result that describes our
own extraction rather than the world.

## 4. What would change the verdict

* **Matching on position strings, not just organization.** 6,116 of 17,727 career records have
  `admin_level='unknown'`, and ministries appear to lose ties that regions keep. A tie definition
  that normalised 部/委/办 names would test §3's two explanations directly.
* **Deeper bios for the top bodies.** 47 of 145 is the binding constraint, and it is an input
  problem: `officials.db` is a static April-2026 snapshot built from a Mac-local Excel seed and is
  not in the nightly (CLAUDE.md, officials.db section).
* **The cohort panel is usable NOW for something else.** 15th-20th CC with complete
  `home_province` and `birth_year` supports descriptive questions about who enters the Central
  Committee — provincial origin, age at entry, central-vs-provincial career share — none of which
  need the tie network. That is a smaller claim than w22775's and is not blocked.

**Verdict: w22775 stays fit C.** The entry in `related-literature.md` now says so for this reason
rather than for a missing-data reason, and the 13-tie number is the one to quote if it is raised
again.
