# Whose authority is invoked: the General Secretary channel against the Premier channel, 2012-2025

*Replication memo, 2026-10-08. "Aligning Agendas in Public-Activity Reports: Provincial Leaders and
Central Signals in China, 2016-2022" (Journal of Chinese Political Science, 2026) topic-models
71,460 leader activity releases and finds provincial issue shares track the General Secretary more
than the Premier, and party secretaries more than governors. It was item #5 of the seven
highest-corpus-fit papers in `related-literature.md` and the last one outstanding. We cannot run it
as specified, for a reason that is itself a finding; we can ask the same question in a different
medium, on a fixed-site panel, across three levels and fourteen years. Companion to
`attention-campaigns.md`, `recentralization-experimentation.md` and `joint-issuance.md`.*

---

## The short version

**Their design is not available here, and the reason is structural.** The Party hierarchy is
nearly absent from our corpus *as an issuer*: **104** provincial party-committee documents against
**19,015** provincial government ones, a 1:183 ratio, versus 1:12 at the centre. That is mostly not
a coverage gap — China's 政府信息公开 regime covers government bodies, so 党内文件 do not appear on
disclosure portals. A party-secretary-versus-governor test cannot be built on 104 documents.

**But the Party channel is highly visible as invoked authority**, and that is measurable: 45,308
documents mention 习近平, 30,638 总书记, 26,358 党中央 — against **936** for 国务院总理 and 1,614
for 李强. So on their central question the answer is not a ratio, it is an **absence**: the Premier
channel sits at **0.0-1.0% of documents at every level in every year**, with no trend, while the
General Secretary channel goes from **0.0% before 2013 to 30-43% by 2024**.

Two findings they could not see, both of which need the level dimension:

1. **The gradient inverts.** In 2016 central documents invoked 习近平 more than municipal ones
   (8.0% vs 7.0%). By 2024 **municipal invokes far more than central: 42.9% vs 31.7%.** Personal
   authority is now invoked hardest at the bottom of the hierarchy.
2. **Institutional authority runs the opposite way, throughout.** 党中央 in 2024: central 33.0% >
   provincial 22.0% > municipal 14.6% — a steep decline downward, in the same years that personal
   invocation rises downward. The person travels all the way down; the institution does not.

---

## 1. Why the paper's design is unavailable, measured

| channel | documents |
|---|---|
| central, Party issuer (中共中央 / 中央办公厅) | 1,026 |
| central, state issuer (国务院 / 国办) | 12,028 |
| **provincial, Party issuer (省委 / 党委)** | **104** |
| provincial, government issuer | 19,015 |
| municipal, Party issuer | 874 |
| municipal, government issuer | 50,707 |

The asymmetry is a property of the disclosure regime, not of the crawl: `政府信息公开条例` obliges
*administrative* organs. The sub-national party-committee documents we do hold are mostly joint
党委+政府 issuances, which is why they are not zero.

This is worth stating plainly as a limit on the whole volume: **any finding about the Party
hierarchy's own documents is out of reach for this corpus**, and a study that needs it (theirs, and
the cadre-incentive literature in `related-literature.md` §6) cannot be run here regardless of how
much more we crawl from government portals.

---

## 2. The answerable form: invocation, not issuance

If the Party cannot be observed issuing, it can be observed being *invoked*. Per year and level we
compute the share of bodied, dated, levelled documents whose full text names each channel.

**On a fixed-site panel**, because the uncontrolled series is untrustworthy here — raw municipal
document counts run 1,257 (2008) → 11,280 (2025) as newly-crawled sites arrive, and the raw series
shows a 2025 *collapse* (municipal 25.7% → 18.8%) that the panel shows is composition. Panel = the
18 sites with ≥30 bodied documents in every year 2012-2024: bj, chinatax, gd, gov, gz, huizhou,
jiangmen, jieyang, js, mof, ndrc, sh, shaoguan, suzhou, sz_gazette, zhongshan, zhuhai.

### 习近平 (personal invocation), % of panel documents

| year | central | provincial | municipal |
|---|---|---|---|
| 2012 | 0.0 | 0.0 | 0.1 |
| 2013 | 0.9 | 1.6 | 1.7 |
| 2015 | 4.9 | 8.5 | 2.9 |
| 2016 | 8.0 | 13.5 | 7.0 |
| 2017 | **25.5** | 15.1 | 8.4 |
| 2018 | 19.8 | **26.1** | 13.3 |
| 2020 | 31.2 | 22.1 | **20.0** |
| 2021 | 37.5 | 36.9 | 28.3 |
| 2022 | 37.2 | 31.2 | 33.9 |
| 2023 | 28.3 | 33.2 | 40.4 |
| **2024** | 31.7 | 32.3 | **42.9** |
| 2025 | 30.3 | 31.3 | 38.6 |

### 党中央 (institutional invocation), % of panel documents

| year | central | provincial | municipal |
|---|---|---|---|
| 2012 | 8.2 | 3.8 | 2.4 |
| 2015 | 29.7 | 5.3 | 1.9 |
| 2018 | 19.1 | 12.3 | 5.1 |
| 2021 | 36.4 | 19.1 | 9.1 |
| 2022 | **42.5** | 18.5 | 12.3 |
| **2024** | 33.0 | 22.0 | 14.6 |
| 2025 | 31.5 | 19.5 | 12.2 |

### 国务院总理 (the Premier channel), % of panel documents

Central 1.0 / 0.6 / 0.0 / 0.0 / 0.5 / 0.2 / 0.4 / 0.5 / 0.1 / 0.0 / 0.0 / **0.7** / 0.2 / 0.5
(2012→2025). Provincial never exceeds 0.9. Municipal is **0.0 in eleven of fourteen years**.
国务院常务会议 behaves the same way and declines.

---

## 3. Reading the three series

**A regime shift, not a drift.** Personal invocation is *exactly* 0.0% at central and provincial
level in 2012 and 0.1% municipal — not low, absent. It then rises monotonically for a decade. A
measure that starts at a hard zero and ends near 40% is not a slow change in register.

**It diffuses downward with a lag of three to four years.** The 20% threshold is crossed at the
centre in 2017, provincially in 2018, municipally in 2020. That is the same central-signal-to-local
-tracking structure the paper reports, recovered from a different variable, and it is consistent
with `diffusion-atlas.md`'s province-before-city ordering.

**Then it inverts, which is the finding.** From 2022 the municipal line crosses above both others
and keeps rising: 33.9 → 40.4 → **42.9** against central 37.2 → 28.3 → 31.7. A central document can
*be* the authority; a municipal document must *cite* one. So the invocation rate is not a measure
of attention so much as of distance from the source, and once the practice saturated it became
heaviest where authority has to be borrowed. This is the same mechanism
`recentralization-experimentation.md` found in the citation record — a 2013-17 rise in
authority-borrowing — appearing in the lexical record and persisting past 2017 where the citation
version reverted. **The two records disagree about the reversion, and that disagreement is the
most useful thing here:** borrowing *authority by name* did not revert, borrowing it *by citation*
did.

**Institutional and personal invocation have opposite gradients.** 党中央 declines steeply
downward in every single year (2024: 33.0 / 22.0 / 14.6). The centre speaks of the Party as an
institution; localities name the person. Register, not just intensity.

**A detail that falls out of the same table.** At the centre, 习近平 and 总书记 diverge sharply
(2022: 37.2% vs 12.8%; 2024: 31.7% vs 9.7%), while sub-nationally they track closely (municipal
2024: 42.9% vs 38.4%). Central documents use the **name**; sub-national documents pair it with the
**title**. The honorific is a local device.

---

## 4. What this adds, and what it cannot settle

**Adds.** The Premier comparison as an absence rather than a ratio. Three levels including the
municipal tier they did not reach, over fourteen years rather than seven. The inverted gradient,
which needs the level dimension. The personal/institutional register split. And a disagreement with
the citation-based recentralization measure that neither study could find alone.

**Cannot settle.** Invocation is not agenda: a document naming 习近平 is not thereby *about* his
agenda, and this memo measures **whether** authority is cited, never **which topic** it is cited
for. The paper's actual dependent variable is issue shares, which would need the invocation joined
to `topics_algo` per document — a real next step, and gated on the caveat in `policy-tempo.md` that
topic labels move when anchor identity changes. The party-secretary-versus-governor half stays
unavailable (§1). And a name-mention is a crude unit: it counts a 学习贯彻 boilerplate line and a
substantive citation the same way.

---

## Limits

- **A mention is not a stance.** No sentiment, no topic, no position in the document.
- **The panel is Guangdong-heavy** (gd, gz, huizhou, jiangmen, jieyang, shaoguan, zhongshan, zhuhai,
  sz_gazette of 18), so the municipal line is substantially a Guangdong line. The inversion should
  be re-checked when a second province reaches comparable municipal depth (`corpus-lessons.md` B1).
- **Panel central means gov/mof/ndrc/chinatax**, which is an executive-and-fiscal view of the
  centre, not the whole of it.
- **2-character names need the segmented index.** 李强 returns **0** from the trigram index
  (3-character minimum) and 1,614 from the segmented one. Every count here is from whichever index
  is valid for the term; mixing them silently reports an absence. See `rmb-coverage.md` §4. The
  shipped script prints each term's index so the routing cannot be silently wrong.
- **李强 is a very common personal name**, so its 1,614 documents certainly include officials and
  private individuals who are not the Premier. That is why §2's Premier series uses the **title**
  国务院总理, which is unambiguous, and why the name count appears only in §'s short version as an
  order-of-magnitude contrast. The same caution applies to any name-based measure here except
  习近平, which is effectively unique in this corpus.
- **Pre-2013 zeros are informative but shallow** — the panel holds ~1,300 central and ~900
  provincial documents in 2012, so a rate below ~0.1% is not resolvable.
- **`admin_level_doc` is ~98% precise**, and the inversion is a 11-point gap, comfortably above it.

---

## Replication

```bash
# counts by channel (note WHICH index each term needs)
sqlite3 "file:documents.db?mode=ro" "
  SELECT COUNT(*) FROM doc_search     WHERE doc_search     MATCH '\"习近平\"';
  SELECT COUNT(*) FROM doc_search_seg WHERE doc_search_seg MATCH '李强';"
```

The panel series is `scripts/rnd/analysis/authority_invocation.py` (read-only, `--min-per-year`,
`--terms`), which prints both the raw and the fixed-panel tables so the composition effect in §2 is
visible rather than asserted.
