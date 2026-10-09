# Geoeconomic Pressure, Read Off the Instruments

**Companion to NBER w34020, not a replication of it.** Built 2026-10-09 with
`scripts/rnd/analysis/pressure_instruments.py`.

## 1. The paper and what we can add

**"Geoeconomic Pressure"** — Clayton, Coppola, Maggiori & Schreger, **NBER w34020, July 2025** —
uses large language models over large textual corpora to find episodes in which governments use
existing economic relationships to pressure other countries, classifying **which government
pressures which target, through which instrument, and which firms and products are involved**. It
then measures firm responses (tariff-hit firms adjust prices; export-control-hit firms raise R&D)
and, notably, quantifies the uncertainty of its own LLM classification across several open-weight
models and many prompt variants. Its theory companion is **w33309, "A Theory of Economic Coercion
and Fragmentation"** (Clayton, Maggiori & Schreger, Dec 2024 rev. Apr 2025), which estimates that
US leverage rests mainly on finance and Chinese leverage mainly on manufacturing.

Their unit of analysis is exactly what this corpus holds for one of the two principals — except we
hold it as **primary instruments** rather than as episodes inferred from news text. A 商务部公告 or
a 不可靠实体清单工作机制公告 carries its own date, its own 文号, the named firms, and an attached
official justification. That removes *their* specific measurement uncertainty (no classifier, so no
classifier variance to report) and introduces a different limitation that must be stated plainly:
**an instrument is not an economic effect.** They have firm-level R&D and price outcomes; we have
none. This is the same complement/replication distinction `related-literature.md` draws for the
AI-tocracy program, and calling it a replication would be the relabelling `consistency-review.md`
exists to catch.

## 2. The corpus records pressure in BOTH directions, and that is the design point

A naive extractor over the 161 candidate documents reports **278 US entities and also 196 Chinese
and 220 Japanese entities**. Those do not add up, because they point in opposite directions: China
issues instruments against foreign firms, *and* Chinese documents record foreign measures against
Chinese firms (`美国在出口管制"实体清单"中增列40个实体`,
`2021年7月美商务部"实体清单"新增34个实体 其中23个为中国实体`), and some documents are plain
explainers of the US regime (`美国出口管制制度之实体清单制度介绍`).

So the extractor classifies the **sender** first and never sums across directions. After dropping
22 off-domain documents (see §5):

| direction | instrument | justification | explainer |
|---|---|---|---|
| **outbound** (China applying) | **57** | 16 | 1 |
| **inbound** (China recording) | 10 | **37** | 2 |
| unplaced | 15 | — | 1 |

The asymmetry is itself informative and is *not* a coverage artifact: China's own measures arrive as
**instruments**, while foreign measures enter the Chinese record as **spokesperson justifications**
(37 of 49 inbound documents). The corpus is the issuing state's archive, so it holds its own actions
as documents and others' actions as commentary on them.

## 3. Who is targeted

Entity counts read from instrument titles (`将16家美国实体列入`, `将斯凯迪奥公司等11家美国企业列入`),
**deduplicated by the instrument's own 文号** — 454 before dedup, 338 after, because mirrors and news
restatements repeat one announcement:

| target | entities named | share |
|---|---|---|
| 美国 | **151** | 45% |
| 日本 | **120** | 36% |
| 欧盟 | 49 | 14% |
| 美国相关子公司 | 10 | 3% |
| 台湾地区 | 8 | 2% |

**338 entities across 28 distinct outbound instruments.** The US-plus-Japan concentration (81%) is
consistent with w34020's finding that the US and China direct most pressure at each other, and adds
Japan as a clear second target — the 2026 dual-use controls following the Takaichi Taiwan remarks.

Outbound instruments by year (deduplicated): **2023: 1 · 2024: 4 · 2025: 26 · 2026: 22**. The
instrument stream is overwhelmingly post-2024. This is a **count, not a trend** — it has no
fixed-site panel (`panel.py`), and the corpus's own coverage of mofcom deepened over the same
window, so the slope is not separable from acquisition here.

## 4. The justification ships with the instrument

From the Unreliable Entity List sub-series (39 documents, 2020-09-18 to 2025-11-05: the 2020 规定,
22 instruments, 15 justifications, 15 instrument titles naming a firm — 洛克希德·马丁, 雷神,
波音防务, 通用原子, PVH, 因美纳, 斯凯迪奥, 护盾人工智能, 萨罗尼克科技, 反无人机技术):

**17 of 22 instruments pair with a justification inside 21 days. Median lag 0 days. 12 of 17 (71%)
are same-day or next-day.**

On this record the state does not announce a listing and explain it later; the explanation is
issued with the instrument. That is a different communicative posture from the campaign documents
in `attention-campaigns.md`, where 解读 trails an instrument for weeks. The lag *appears* to tighten
(6-7 days on the 2024 actions, 0-1 across most of 2025) and this memo does **not** call that a
finding: n = 17, one 2025 action still lags 8 days, and 5 instruments have no justification inside
21 days at all.

## 5. What the extractor refuses, and why that list matters

22 candidate documents are dropped as off-domain, and reading that bucket — rather than the counts —
is what caught them. They are the same bug shape as the resolver's `ORG_TAIL` false positives: **a
term borrowed by an unrelated field.**

- **反制设备** — `民用无人驾驶航空器探测反制设备唯一识别码` and three siblings are *counter-drone
  hardware* standards. 反制 there is "counter" in an engineering sense.
- **关注名单** — `深圳市水务局关于将深圳市凯丰实业有限公司列入水土保持"重点关注名单"的通告` is a
  municipal soil-conservation watch list.
- **op-eds** — guancha columnists (`兔主席：中方严厉反制…`, `梅新育：贸易反制和军事上…`) carry 反制
  in a byline-prefixed title.

15 instrument documents remain **unplaced** by direction and are reported as such rather than
assigned. Most are media restatements with no masthead and no named actor.

## 6. Limitations

1. **No economic outcomes.** This is the instrument record. w34020's firm-level price and R&D
   responses need data we do not hold, and nothing here speaks to whether the pressure worked.
2. **No fixed-site panel**, so the yearly counts in §3 are counts and not a trend.
3. **Title-level extraction.** Entity counts come from titles; an instrument that names its firms
   only in an annex contributes 1 instrument and no count. The 338 is therefore a **floor**.
4. **Inbound coverage is incidental.** China records foreign measures when it comments on them, so
   the 10 inbound instruments are not a census of measures against China.
5. **`doc_identity` does not pool these instruments**, which is why dedup uses a 文号 parsed from
   the title instead. Five held copies of 商务部公告2026年第11号/第12号 each carry a *distinct*
   `instrument_id`, so `instrument_role` is `unique` for every copy — the
   length-floor-on-a-folded-string family in CLAUDE.md, where stripping the 文号 and date tail
   leaves a core under `_best_core`'s `KEY_MIN`. Logged as its own defect; this memo's numbers do
   not depend on it being fixed.
