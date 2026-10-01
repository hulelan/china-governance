# From archive to instrument: a daily/weekly policy tracker with auto-matched diffusion

*Concept note, 2026-10-01. The strategic shift the user proposed: stop treating the corpus
only as a retrospective archive (analyze 2020-2026 back-histories) and add a LIVE layer that
tracks what is happening in major implementation areas day-to-day and week-to-week, with
cascades auto-detected as they unfold. Builds on `consumption-diffusion.md`,
`ai-governance-diffusion.md`, the Policy Lens, and the 29-topic facet.*

---

## The idea in one line

For a chosen set of implementation areas, show **what is new this week, at every level**, and
**auto-match each new sub-national document to the central instrument it is implementing**, so
the diffusion cascade is a live feed, not a paper written a year later.

## Why this is the right move now

- The retrospective diffusion studies (consumption: 49-day median cascade; AI+: authored
  elaboration) already *proved the method works*. Running it live is the same machinery pointed
  at the incoming nightly documents instead of the archive.
- It is the thing that distinguishes us from a repository. ReConnect China holds ~24x more
  documents but is broad-and-shallow with no citation graph and no diffusion. A live,
  auto-matched cascade tracker is something no one else has (see `reference_reconnect_china`).
- The speed precondition is now met: the `/browse` cold hang went from 72s to 2.3s this
  session. A daily tool has to be fast, and the worst bottleneck is gone.

## The three pieces it needs

### 1. Implementation areas (the rows of the tracker)

We already have a **29-topic subject facet** (`topics_algo`, ~64% coverage / ~95% precision,
from the ReConnect taxonomy) orthogonal to genre. The tracker does not need all 29. Start with
a curated high-priority set where cascades are active and policy-relevant, for example:
**AI / 人工智能**, **consumption / 消费**, **real estate / 房地产**, **employment / 就业**,
**data governance / 数据**, **elder care & population / 养老·人口**, **local debt / 化债**.
Each is a row; each has a daily/weekly "what's new" and an "active cascades" view.

### 2. The weekly feed (the easy half, mostly built)

For each area: new documents since last week, grouped by level (central / provincial /
municipal / district), newest first, with issuer and genre. This is a bounded query over
`topics_algo` × `date_published` × `admin_level` — all indexed. The only work is a **tracker
view** and, for speed, a small **precomputed per-area-per-week rollup table** (same pattern as
the `site_stats` fix: compute nightly, read instantly) so a daily tool never runs a cold scan.

### 3. Auto-matching (the new capability, the hard-and-valuable half)

This is what the user means by "auto matching." When a new sub-national document arrives, match
it to the central instrument it implements, and emit a **diffusion event** with a lag. Three
signals, in increasing difficulty, all already present in the corpus:

- **Citation match** — the new doc cites a known central anchor (resolved `citations` edge).
  Direct, already computed nightly.
- **Title-reissuance match** — the new doc's title is a localized version of an anchor's title
  (the 《》/文号-normalized matcher that drives citation resolution already does this).
- **Topic + genre + recency match** — a new provincial 实施方案 in an area within N months of a
  central 意见 in the same area is a probable implementation even with no citation. (Lower
  precision; flag as "likely," let citation/title confirm.)

The output is a per-anchor **live cascade**: "central issued X on day T; as of today, these M
localities have re-issued or cited it, median lag L days, newest arrival yesterday." That is
exactly the `consumption-diffusion.md` §3 table, but updating itself nightly instead of being
hand-built once.

## What to build, in order

1. **Nightly diffusion-events table.** Wire the existing citation + title-reissuance matchers to
   emit, per new doc, `(topic, matched_anchor_id, match_type, lag_days)` into a small table.
   This is the auto-matcher. Pure CPU, no crawling, runs in the nightly after citations.
2. **Per-area weekly rollup table** (precomputed, like `site_stats`) for instant tracker views.
3. **Tracker UI** — an area picker → this week's new docs by level + the active cascades for
   that area (each a live version of the diffusion table). Fast because it reads the two
   precomputed tables.
4. **Anchor registry** — a small curated/scored list of the central "anchor" instruments per
   area (high `citation_rank` + framework genre), so the auto-matcher knows what to match
   against. Partly derivable, partly curated.

## Why it is also novel research, not just a product

Most policy-diffusion scholarship is retrospective because the data arrives in annual dumps.
A corpus refreshed nightly lets diffusion be measured **while it happens** — the speed and
breadth of a cascade in its first weeks, which localities move first, whether the 2025-26 AI+
pattern (authored sector elaboration) repeats for the next central push. A real-time cascade
instrument for a bureaucracy this size would be a genuine methodological contribution, not only
a dashboard. It also directly serves the volume: every chapter's retrospective finding gets a
"and here is the same mechanism unfolding now" companion.

## Honest constraints (carry from the research agenda)

Coverage bias still bounds *breadth* (the proxy-blocked provinces are invisible, so "who moved"
is a floor); publication date is not adoption date; citation resolution is ~52% so the matcher
misses some real implementations; and the topic tagger is ~64% coverage. The tracker must show
these as floors, never as "province X did not act." Keep it mechanism-level, no regime labels.
