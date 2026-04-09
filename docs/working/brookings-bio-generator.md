# Brookings-Style Biography Generator — Design Notes

*Drafted 2026-04-08. Status: planning, not started.*

## Motivation

For every official in `officials.db`, auto-generate an analyst biography in
the format of Brookings' "20th Party Congress Chinese Leaders" series.

**Canonical example:** [Ding Xuexiang (丁薛祥), October 2022](https://www.brookings.edu/wp-content/uploads/2022/10/20thpartycongress_ding_xuexiang.pdf), compiled by Cheng Li and the John L. Thornton China Center at Brookings.

The value of these biographies over Wikipedia-style entries is in the
**analytical framing** — patron-client ties, personality signals, factional
reads, forward-looking political prospects. Cheng Li's team writes these by
hand for a few dozen top leaders. Our database could scaffold the equivalent
for ~1,628 officials with substantive career records.

## The format, section by section

### Section 1: Header
```
{name_en} {name_cn}
Born {year}
```

### Section 2: Current Positions
Bulleted list of all active roles with year ranges, e.g.:
- Director of the General Office of the CCP Central Committee (2017–present)
- Member of the Politburo (2017–present)
- Director of the Office of the General Secretary (2013–present)

### Section 3: Personal and Professional Background
Narrative paragraph(s) covering:
- Birth date + place
- Party entry year
- Education (institutions + degree years)
- Chronological career (each position + year range + concurrent roles)
- Promotion inflection points ("he was then promoted to...", "finally...")

### Section 4: Family and Patron-Client Ties
- Family background (humble vs connected, mentions in Beijing)
- How they met / gained trust of their current patron
- Key promotion moments ("Within two months, Xi promoted Ding as...")
- Personal details (wife, children, spouse's career)

### Section 5: Policy Preferences and Political Prospects
- Known personality / reputation traits
- Political-survival track record
- Documented policy interests
- Forward-looking assessment (expected next roles, structural constraints)

### Footer
"Compiled by [source]" + numbered footnotes with URLs.

---

## Feasibility by section

| Section | Data source | Feasibility | LLM needed? |
|---|---|---|---|
| Header | `officials` table | ✅ trivial | no |
| Current Positions | `career_records` with `end_year IS NULL` or `end_year >= current_year` | ✅ mechanical | no |
| Personal & Professional Background | `officials` + full `career_records` ordered by start date | ✅ template-based | no (but LLM could polish prose) |
| Family & Patron-Client Ties | `overlaps` + rank trajectory; family info is scraped in `baike_html` but not parsed | ⚠ hybrid | yes (narrative) |
| Policy Preferences & Political Prospects | Not in our data directly; needs cross-reference with `documents.db` author attribution | ⚠ hardest | yes |
| Footnotes | `baike_url` + source article links | easy | no |

---

## Staged implementation plan

### v0 — mechanical MVP (1-2 days of work)

**Scope:** Sections 1-3 only. No LLM. Template-driven.

**Output:** One markdown file per official in `docs/bios/{official_id}_{name_cn}.md`
plus a `/officials/{id}/bio` web view rendering the same content.

**Script:** `scripts/generate_bios.py` that queries officials.db and writes
markdown via a Jinja2 template:

```jinja2
# {{ name_en }} {{ name_cn }}
Born {{ birth_year }}

## Current Positions
{% for pos in current_positions %}
- {{ pos.position }} ({{ pos.start_year }}–present)
{% endfor %}

## Personal and Professional Background
{{ name_cn }} was born in {{ birth_year }} in {{ home_province }}.
He joined the Chinese Communist Party in {{ party_year }}.
{% for edu in education %}{{ edu.narrative }} {% endfor %}

After completing his studies, {{ name_cn }} began working at
{{ first_org }}, where he served as
{% for job in careers %}{{ job.position }} ({{ job.start }}–{{ job.end }}){% if not loop.last %}; {% endif %}{% endfor %}.
```

**Pre-work needed:**
- Parse Baike `career_text` more richly to separate "education" lines from "work" lines (currently lumped together in `career_records`).
- Extract "party entry year" — usually mentioned in Baike as "加入中国共产党" but we filter it out in `compute_overlaps.py` SKIP_ORG_PATTERNS. Need to keep a *separate* stash of that date per official.
- Detect "current positions" by filtering career_records where end_year is NULL, or > current year - 1.

**Output quality bar:** matches Wikipedia-equivalent chronological summary.
Not yet analyst-grade, but genuinely useful as a searchable English bio for
1,628 officials whose data currently only lives in Chinese Baike pages.

**Ship as:** markdown files in repo + static bio pages on `/officials/{id}/bio`.

---

### v1 — patron-client ties (2-4 days of work)

**Scope:** Add Section 4 using computable signals from our existing data.

**Key insight:** The Brookings bio identifies Xi→Ding patronage through
specific empirical signals we can replicate:

1. **Overlap duration** — how long did A and B work in the same organization?
   (we have this in the `overlaps` table)
2. **Rank asymmetry at overlap time** — was one of them senior to the other?
   (derivable from `position` strings — words like 书记/省长/部长/主任 indicate higher rank than 副/副书记/处长)
3. **Post-overlap promotion velocity** — did the junior get promoted shortly
   after the overlap began or ended?
4. **Patron's peak rank** — is the senior now on the PSC / in the Politburo?
   (we have `is_psc`, `is_politburo`)

**Algorithm sketch for computing "primary patron"**:

```python
def identify_patrons(focal_id, odb):
    """Return ranked list of likely patrons for one official."""
    overlaps = odb.fetch("""
        SELECT * FROM overlaps
        WHERE official_a = ? OR official_b = ?
        ORDER BY overlap_months DESC
    """, focal_id, focal_id)

    focal_career = get_career_records(focal_id)
    candidates = []

    for o in overlaps:
        peer_id = o.official_b if o.official_a == focal_id else o.official_a
        peer = odb.fetchrow("SELECT * FROM officials WHERE id = ?", peer_id)
        peer_career = get_career_records(peer_id)

        # Rank at overlap time — compare position strings
        focal_rank = infer_rank(focal_career, o.overlap_start_year, o.organization)
        peer_rank = infer_rank(peer_career, o.overlap_start_year, o.organization)
        rank_asymmetry = peer_rank - focal_rank  # positive = peer is senior

        # Post-overlap promotion velocity for focal
        post_promos = count_promotions(focal_career, after=o.overlap_end_year, window=5)

        # Score: longer overlap + bigger rank gap + more promotions + higher peer terminal rank
        score = (
            o.overlap_months * 0.1
            + max(0, rank_asymmetry) * 5
            + post_promos * 3
            + (10 if peer.is_psc else 5 if peer.is_politburo else 1)
        )
        candidates.append((peer, score, o))

    return sorted(candidates, key=lambda x: -x[1])[:3]
```

**For narrative generation**, feed the top 1-2 patrons into an LLM prompt:

```
Here is the career history of {{ focal_name }}:
{{ focal_career_timeline }}

Here is the overlap history with their most likely patron, {{ patron_name }}:
- They worked together at {{ org }} from {{ start }} to {{ end }} ({{ months }} months)
- During this overlap, {{ focal_name }} held the role of {{ focal_position }}
  while {{ patron_name }} held the role of {{ patron_position }}
- Within {{ N }} years after the overlap ended, {{ focal_name }} was promoted
  to {{ next_position }}

Write a 3-sentence "Family and Patron-Client Ties" paragraph in the style of
Brookings analyst biographies. Mention the patron relationship, the moment of
trust, and the post-overlap promotion arc. Be specific about dates.
```

**Validation:** The Ding Xuexiang Brookings bio says Xi only worked with Ding
for "a few months in 2007" and promoted him "within two months." Our data
should reproduce this claim independently: Xi Jinping (id 1135) + Ding
Xuexiang (id 1694) in the Shanghai Municipal Party Committee, overlap ~2007.
Run the generator on Ding as a regression test.

---

### v2 — policy preferences (5-10 days)

**Scope:** Add the first half of Section 5.

**Approach:** Cross-reference `officials.db` with `documents.db` to find
documents the official signed, authored, or is named in. For each, use the
existing DeepSeek v2 classifications (doc_type, policy_significance,
references_json) to build a per-official policy fingerprint.

**Blockers:**
1. **Author attribution is missing.** Most `documents` rows have `publisher`
   (an organization) but not `author` (a person). For a real "what has this
   person written" view we'd need to parse speech attributions in body text.
2. **The 24k/138k v2 classification backlog.** DeepSeek v2 extracts
   references_json but we're only 17% through the corpus. A robust v2 bio
   needs full-corpus classification first. Tie this to the classification
   backlog item.

**MVP shortcut:** Use citation data. If we find the official's name or
tenure period mentioned in other classified documents, we can infer what
policy domains they interact with even without authorship attribution.

**LLM prompt structure:**

```
Here are the policy documents associated with {{ name }} ({{ tenure }}):
{% for doc in docs %}
- {{ doc.title_en }} — {{ doc.doc_type }} — {{ doc.policy_significance }} score
{% endfor %}

Write a 3-4 sentence "Policy Preferences" paragraph in the style of Brookings
analyst biographies. Focus on thematic patterns, not individual documents.
What policy domains does this person consistently engage with? Any signature
phrases or initiatives? If the record is sparse, say so explicitly.
```

---

### v3 — political prospects (structural signals)

**Scope:** The forward-looking second half of Section 5.

**Insight:** Brookings says "Ding is expected to gain a seat on the Politburo
Standing Committee at the 20th Party Congress." We can't hand-write that
prediction, but we CAN compute structural signals that inform it:

1. **Age at next party congress** — Party norms cap retirement at ~68 for
   new PSC members. Compute `(current_age, congress_year, eligibility)`.
2. **Recent promotion velocity** — how many rank steps in last 5/10 years.
3. **Patron's trajectory** — is their identified patron ascending or purged?
4. **Slot availability** — what's the composition gap in the next Politburo?
   (e.g., who's retiring, what regions/factions need representation)
5. **Current role as pipeline indicator** — certain roles (e.g., executive
   secretary of the Secretariat, Shanghai Party Secretary, Chongqing Party
   Secretary) historically predict PSC promotion; others don't.

**Output:** A structured "Political Prospects Score Card" alongside a
narrative generated from the same signals.

```
Age at 21st Party Congress (2027):       65 ✓ (eligible)
Promotion velocity (last 10 years):       +3 ranks
Primary patron:                           Xi Jinping — ascending
Historical pipeline role match:           Shanghai Party Sec → PSC (past 3 of 5 cases)
Factional alignment (inferred):           Zhijiang clique
Structural gap in 21st PSC:               1 open seat for finance/tech
```

---

## Storage & pipeline

- **Generation script:** `scripts/generate_bios.py` — orchestrates v0-v3
  phases depending on `--stage` flag. Writes one markdown file per official
  to `docs/bios/{id}_{name}.md` and optionally an HTML render for the web.
- **LLM calls:** DeepSeek for cost (same provider as existing v2
  classification). Estimated cost for v1 (1,628 officials × ~500 tokens
  patron-narrative each) ≈ $1-2. v2 and v3 are more expensive.
- **Web integration:** Add a `/officials/{id}/bio` route that renders the
  generated bio. Link to it from the existing `/officials` detail panel.
  Cache indefinitely — bios only regenerate on manual re-run.
- **Idempotence:** Keep a `bio_generated_at` timestamp per official so
  partial runs resume cleanly.

## Why this is worth doing

1. **Immediate corpus value** — v0 alone turns the 1,628 officials with
   career data into a searchable English biographical reference. That's a
   resource nothing else online provides at this scale.
2. **Distinct analytical angle** — v1 (patrons) and v3 (prospects) are
   exactly the analytical layer Brookings and similar think tanks hand-craft
   for a few dozen leaders. Our database scaffolds the same work for
   thousands.
3. **Feeds the research agenda** — bios become the natural "about page" for
   every name surfaced by the documents corpus (document signatories,
   cited officials, speech attributions).
4. **Low-risk incremental** — v0 requires no LLM and can ship as a weekend
   job. Each subsequent stage independently adds value. Abort at any stage
   and the prior stages still work.

## Open questions

- **Family data**: Do we parse the Baike `baike_html` for family paragraphs,
  or skip that section entirely in v1? (Privacy concerns are minimal for
  public figures but the parsing is finicky.)
- **Language**: English-only, bilingual, or Chinese-only? Brookings writes
  English. Our corpus is mostly Chinese. v0 could output bilingual (EN from
  `name_en` + CN chronology) as a stepping stone.
- **Verification**: How do we handle officials where our `career_records`
  are sparse or likely wrong? The collision-twin fix showed the data quality
  is uneven — bios should note confidence levels or skip ambiguous cases.
- **PDF output**: Brookings publishes as PDFs with the Brookings header
  image. Do we want a branded PDF export too, or just markdown + web view?

## Related backlog items

- Cross-link officials ↔ documents (prerequisite for v2)
- DeepSeek v2 classification resume (prerequisite for v2 at full corpus scale)
- Parse narrative biographies (prerequisite for 527 officials with prose-only
  Baike entries — currently they have 0 career records)
- Add missing collision twins (completeness — some historical CC members are
  entirely absent from the DB)
- Party vs state organization distinction (enriches the "position" hierarchy
  the patron-ranking algorithm relies on)
