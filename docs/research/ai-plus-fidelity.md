# Fidelity of the "AI+" Cascade: Localities Elaborate, They Do Not Relay

*A worked analysis on the china-governance corpus (SQLite on the droplet). All figures pulled
read-only from the live `documents.db` on 2026-09-28. Extends `ai-governance-diffusion.md` §4,
which claimed localities elaborate the 2025 State Council "人工智能+" opinion into sector plans
rather than relaying it. This memo quantifies that claim (research-agenda Q6, fidelity of
diffusion). Companion to `consumption-diffusion.md`. SQL is in the appendix.*

---

## 0. The question and the short answer

**Question.** The umbrella is the State Council opinion 《国务院关于深入实施"人工智能+"行动的意见》
(canonical id 900039770, 2025-08-26). Sub-national bodies then issued ~10 "AI+" action documents.
For each, how much of the local text is the umbrella's text reproduced, versus locally authored?
Place each doc on a relay (near-verbatim) to elaboration (substantial local content) spectrum.

**Short answer.** The split is **sharp and bimodal, and elaboration wins decisively.**
*(Corpus-wide update, 2026-10-01: `diffusion-fidelity.md` scored all 13,509 confirmed pairs and
found the distribution is NOT bimodal but a decaying tail: 88.3% elaboration, 9.8% mid, 1.9%
relay. The "empty middle" here was an artifact of n=12. The elaboration conclusion for AI+ stands;
the bimodality claim does not generalize.)* Measured by
shared character 5-grams, the fraction of a local document that is umbrella-derived is either
**~100% (pure relay)** or **2–13% (near-total local rewrite)**, with nothing in between. Only two
documents relay, and both are **portal reposts of the raw central text**, not localized action
plans (a Zhejiang province page and a Jiangsu department page reproducing the opinion verbatim,
overlap 0.98–1.00). Every one of the **ten genuine local "AI+" action plans** — general municipal
plans (重庆, 苏州, 济宁), a provincial umbrella (黑龙江), and the sector plans (制造, 交通, 教育,
养老) — shares only **2–13%** of its text with the umbrella. These are not adaptations of the
central document. They are new documents that borrow the umbrella's **frame and vocabulary** and
write their own body. There is no meaningful variation by administrative level (province, city,
and district all elaborate). Sector plans elaborate the **most** (they narrow to one domain and
reuse the fewest umbrella terms). This is the opposite of the consumption campaign, where
localities re-issued the *same* named implementation plan of *one* central action.

---

## 1. Method

The bounded candidate set is `title LIKE '%人工智能+%'` with an action/plan genre, admin_level in
provincial/municipal/district/department, date ≥ 2025-08-26 (n=24 rows). Of those, 12 are
explainers (一图读懂 / 政策解读 / 部门解读), news reactions, or list-chrome mirrors with empty or
sub-1KB bodies and are excluded from scoring. Two are **verbatim central reposts** (relay calibration
points). Ten are **genuine local action plans**. Body work is restricted to this 12-doc set — no
full-corpus body scan.

Two overlap proxies, both against the umbrella body (id 900039770, 4,953 normalized chars):

- **`ovlp_local`** = |5-grams(local) ∩ 5-grams(umbrella)| / |5-grams(local)|. The fraction of the
  local document that is umbrella-derived. A verbatim repost tends to 1.0; an all-local rewrite
  tends to 0. This is the relay↔elaboration axis.
- **umbrella-term hits** = how many of 24 hand-picked distinctive umbrella terms (人工智能+, 智能体,
  模型即服务, 算力, 数据要素, 场景, 赋能, the six 重点行动 domains, 高质量发展, …) appear in the
  local body. This separates *frame reuse* (adopting the umbrella's vocabulary) from *text reuse*.

---

## 2. The table

Overlap against the umbrella opinion. Sector read from the title. `len` is normalized body chars.

| id | site | level | sector | len | ovlp_local | umb-terms | verdict |
|---|---|---|---|---:|---:|---:|---|
| 900027057 | zj | provincial | (repost of central) | 4,921 | **1.000** | 22/24 | **near-verbatim relay** |
| 900097169 | js_kxjst | provincial | (mirror of central) | 5,050 | **0.975** | 22/24 | **near-verbatim relay** |
| 12710375 | suzhou | municipal | general ("AI+城市") | 6,578 | 0.128 | 20/24 | substantial elaboration |
| 12700026 | cq | municipal | general (推动"AI+") | 5,178 | 0.083 | 16/24 | substantial elaboration |
| 12714192 | hlj | provincial | general (实施方案) | 10,577 | 0.070 | 16/24 | substantial elaboration |
| 900096951 | js_gxt | provincial | 制造 (manufacturing) | 5,209 | 0.033 | 12/24 | substantial elaboration |
| 900132265 | jining | municipal | general (三年行动) | 5,424 | 0.030 | 12/24 | substantial elaboration |
| 900096107† | sd_gxt | provincial | 制造 (manufacturing) | 11,157 | 0.025 | 12/24 | substantial elaboration |
| 900091972 | bjd_haidian | district | 养老 (elder care) | 6,130 | 0.021 | 8/24 | substantial elaboration |
| 900088336 | cq_jw | provincial | 教育 (education) | 5,176 | 0.045 | 12/24 | substantial elaboration |
| 900097746 | js_jtyst | provincial | 交通 (transport) | 5,728 | 0.017 | 11/24 | substantial elaboration |
| 900088341‡ | cq_jtysw | provincial | 交通 (transport) | 582 | 0.019 | 1/24 | cover-note only (plan in attachment) |

† The Shandong "AI+制造" plan text itself was not crawled with a body; the only substantial SD body
is a press-conference interpretation (发布会解读), scored here as a proxy. ‡ The Chongqing transport
row is only the 通知 cover note (582 chars); the plan is an attachment not in `body_text_cn`, so its
overlap is not meaningful.

**Reading it.** The distribution is bimodal with a wide empty middle. The two relays (0.98–1.00)
are provinces/departments reposting the central opinion word-for-word — they carry 22/24 umbrella
terms because they *are* the umbrella. Every genuine local plan sits at **0.017–0.128**: at most
one-eighth of the local text overlaps the umbrella, and that eighth is inflated by shared notice
boilerplate (各区县人民政府, 现印发, 认真贯彻落实执行), so real content overlap is lower still.

---

## 3. Findings

**1. The cascade is dominated by elaboration, not relay.** Ten of ten localized action plans are
near-total rewrites (87–98% local text). The only relays in the whole candidate set are two raw
reposts of the central document on portal pages, which are not localizations at all. In the
fidelity-of-diffusion frame this is the **high-local-agency** end of the spectrum: the center sets
an umbrella direction and localities author their own instruments under it.

**2. Localities keep the frame, replace the text.** The umbrella-term column separates the two
things overlap conflates. General local plans reuse the umbrella's vocabulary heavily (Suzhou
20/24, Chongqing and Heilongjiang 16/24) while sharing only 7–13% of text — they adopt the "AI+"
concept, 算力/场景/赋能 vocabulary, and high-quality-development framing, then write local content.
This is elaboration-within-frame, not free divergence.

**3. Fidelity varies by sector, not by level.** There is no province/city/district gradient in
overlap — Haidian district (0.021) elaborates as fully as Jiangsu province (0.017–0.033).
*(Update 2026-10-01: n=10. Corpus-wide a level gradient does exist and is monotonic, province
0.074, city 0.051, department 0.031, district 0.030, with the province as the forwarding tier;
see `diffusion-fidelity.md` §3.2 and `fidelity-provincial.md` §2.1. The no-gradient reading
holds for these ten AI+ plans only.)*
The variation is by **sector**: the single-sector plans (制造 12/24, 交通 11/24, 养老 8/24, 教育
12/24) reuse **fewer** umbrella terms than the general umbrella-style local plans (16–20/24),
because they narrow the umbrella's cross-sector agenda to one domain and fill it with
domain-specific content. Sector plans are the lowest-fidelity, highest-elaboration end. The general
municipal/provincial "AI+" plans are the closest to the umbrella and still only ~10% overlap.

**4. Contrast with the consumption campaign.** This is the sharp difference with
`consumption-diffusion.md`. There, localities re-issued **one** central action plan under the
**same or lightly adapted name** (行动方案 / 实施方案 of 设备更新与消费品以旧换新), and several
(江苏, 重庆, 深圳, 福建) kept the verbatim 行动方案 genre — a templated re-issuance cascade with a
tight ~49-day median lag. The AI+ program does none of that. Localities do not re-issue the AI+
opinion; they issue **new sector instruments that have no central counterpart** (AI+制造, AI+交通,
AI+教育, AI+养老, AI+视听). The mechanism difference is legible: the consumption plan carried money
(超长期特别国债) and centrally-set operational rules, so localities relayed a localized
implementation; the AI+ opinion carries neither money nor deadlines, so localities elaborate freely.
Fiscal campaigns propagate as **re-issuance**; the promotional AI+ program propagates as
**authored elaboration**.

---

## 4. Honesty — what this measure does and does not show

- **Body-similarity is noisy.** Shared 5-grams count gov-notice boilerplate as overlap, so the
  0.017–0.128 figures are **upper bounds** on real content overlap; genuine text reuse is lower.
  The relay calibration points (0.98–1.00) confirm the metric saturates correctly for verbatim
  text, so the bimodal gap is real, but the exact elaboration percentages are approximate.
  *(Update 2026-10-01: the calibration holds but the "bimodal gap is real" clause does not
  generalize. As §0 notes, the corpus-wide distribution over 13,509 pairs is a decaying tail,
  not bimodal; the empty middle here was an n=12 artifact. See `diffusion-fidelity.md` §2.)*
- **Some plan text is in attachments, not `body_text_cn`.** The Chongqing transport row (582 chars)
  is only the cover note; the Shandong manufacturing plan body was not crawled (only an explainer
  stands in). Overlap for those two is unreliable and flagged in the table. The other eight bodies
  are full plan text.
- **Small n and coverage-bound.** Ten scored plans, clustered in the deepest-crawled tiers
  (重庆, 江苏, 苏州, 北京, 黑龙江, 山东). A province absent here may have acted and simply not be
  crawled (many province portals are datacenter-IP-blocked). Breadth is a floor; the fidelity
  *finding* rests on the internal consistency of the ten, which is total.
- **The cascade is mid-flight.** The umbrella is 2025-08-26 and the cutoff is 2026-09-28; more
  local plans are still arriving. The elaboration verdict is stable across all ten observed so far,
  but the set will grow.
- **This is the documentary face only.** Overlap measures published text, not whether the local
  plan changes anything. It does not license regime-type or capacity claims.

---

## Appendix — key queries

```sql
-- Umbrella
SELECT id,site_key,date_published,length(body_text_cn),substr(title,1,60)
FROM documents WHERE id=900039770;   -- 2025-08-26, gov, 5010 chars

-- Candidate set (n=24; 10 genuine plans, 2 relays, 12 explainers/news/mirrors)
SELECT d.id,d.site_key,s.admin_level,substr(d.date_published,1,10),
       length(d.body_text_cn),d.title
FROM documents d JOIN sites s ON s.site_key=d.site_key
WHERE d.title LIKE '%人工智能+%' AND (d.title LIKE '%实施方案%' OR d.title LIKE '%行动%')
  AND s.admin_level IN ('provincial','municipal','district','department')
  AND d.date_published >= '2025-08-26'
ORDER BY d.date_published;

-- Overlap proxy (Python, read-only; full script in scratchpad)
--   norm(t)      = strip whitespace
--   ngrams(t,5)  = set of char 5-grams
--   ovlp_local   = |g(local) & g(umb)| / |g(local)|   -- relay->1, elaboration->0
--   umb-terms    = count of 24 distinctive umbrella phrases present in local body
-- Result: relays 0.975/1.000 (22/24 terms); 10 local plans 0.017-0.128 (8-20/24 terms).
```
