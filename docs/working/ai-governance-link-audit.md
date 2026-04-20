# AI Governance Link Audit (Substack post — 2026-04-08)

Full audit of every substantive link from the OpenClaw / domestic AI
governance Substack post. Each link was checked against `documents.db`
using exact match, fuzzy match (trailing slash / http/https variants),
and URL-slug LIKE search.

**Result: 0 / 24 exact matches in the corpus.** But the misses split
into 4 structurally different categories — some are trivially fixable
with a one-off fetch, some require new crawler sections, and some are
intentionally out of scope.

## Summary by category

| Category | Count | Fixable? |
|---|---|---|
| One-off fetch from existing crawlers' target hosts | 3 | ✅ same day |
| New crawler needed (target host not yet covered) | 6 | ⚠ 1-3 days each |
| WeChat articles (anti-bot, no crawler) | 10 | ❓ needs dedicated strategy |
| Out of scope (English media, academic, video) | 5 | ❌ intentional |

**2026-04-13 correction:** Original audit (04-08) classified item #23
(Xinhua Jan 24) as "lost to retention." Empirical recheck shows the
article is **still live** (HTTP 200, 6,755 chars of body text). The
real gap is discovery + title-extraction, not retention. See corrected
item #23 below.

---

## Full list with per-URL status

Work through this top-to-bottom. Each row: label, URL, current status,
remediation.

### 1. OpenClaw / Domestic AI Governance section

| # | Label | URL | Status | Remediation |
|---|---|---|---|---|
| 1 | sixthtone "rapid" | https://www.sixthtone.com/news/1018285 | MISS (0 docs from host) | **Out of scope** — English media. Skip. |
| 2 | thewirechina "proliferation" | https://www.thewirechina.com/2026/03/29/how-the-openclaw-frenzy-is-testing-chinas-ai-commitment/ | MISS (0 docs from host) | **Out of scope** — English media. Skip. |
| 3 | NVDB announcement | https://nvdb.org.cn/publicAnnouncement/2019330237532790786 | MISS (0 docs from host) | **New crawler needed.** NVDB = National Vulnerability Database (中国国家漏洞库). High value for cybersecurity research. Worth a dedicated `crawlers/nvdb.py`. |
| 4 | CNCERT March warning | https://www.cert.org.cn/publish/main/11/2026/20260312144519429724511/20260312144519429724511_.html | MISS (0 docs from host) | **New crawler needed.** CNCERT = 国家互联网应急中心 (National Computer Network Emergency Response Technical Team). High value. Worth a dedicated `crawlers/cncert.py`. |
| 5 | MSS guidance | https://mp.weixin.qq.com/s/VOSy-kWs6zuNIBn40dWGWQ | MISS (WeChat, 493 unrelated docs from host) | **WeChat strategy.** See WeChat section below. |
| 6 | People's Daily report | https://mp.weixin.qq.com/s/UqGeD00-Y7JWa2fh8LUHNg | MISS (WeChat) | **WeChat strategy.** |
| 7 | CNCERT tailored guidance | https://mp.weixin.qq.com/s/L9AKvAFMB6kE2EcRSvTxZw | MISS (WeChat) | **WeChat strategy.** |
| 8 | TC260 draft practice guide | https://www.tc260.org.cn/portal/article/2/160310cea5f6411d92fd99a52a42424f | MISS (0 docs from host) | **New crawler needed.** TC260 = 全国信息安全标准化技术委员会 (National Information Security Standardization TC). Core source for Chinese cybersecurity and AI safety standards. Worth `crawlers/tc260.py`. |
| 9 | AIIA cloud providers | https://mp.weixin.qq.com/s/cxxZQJVjA3KlqeNQTAInFA | MISS (WeChat) | **WeChat strategy.** |
| 10 | AIIA best practices | https://mp.weixin.qq.com/s/UMrNKdCBM_rbd1581bMQCg | MISS (WeChat) | **WeChat strategy.** |
| 11 | AIIA security tests | https://mp.weixin.qq.com/s/B1ayWZRhLaN9p2j4Pliqgg | MISS (WeChat) | **WeChat strategy.** |
| 12 | AIIA industry standards | https://mp.weixin.qq.com/s/n2Vp0qMp1zRC5fP3LQl2aQ | MISS (WeChat) | **WeChat strategy.** |
| 13 | AIIA agent standards | https://mp.weixin.qq.com/s/xQL4gknil3bkVdrDT0P4kg | MISS (WeChat) | **WeChat strategy.** |
| 14 | AI agent safety commitments | https://mp.weixin.qq.com/s/qeELmpD4MHJ7N1Oiu1LCBw | MISS (WeChat) | **WeChat strategy.** |
| 15 | NDA Liu Liehong argument | https://www.nda.gov.cn/sjj/jgsz/jld/llh/llhldhd/0323/20260323202204680553721_pc.html | MISS (385 docs from host, wrong section) | **One-off fetch** — URL is live, verified 10,357 bytes. Path is `/sjj/jgsz/jld/llh/llhldhd/` (机构设置/局领导/刘烈宏/领导活动) — a "leader activities" section we don't crawl. Can ingest this specific URL immediately via `_extract_body` from `crawlers/nda.py`. **Also adds a structural backlog item:** crawl all `jld/*/llhldhd/` leader-activity sections for NDA (and potentially add equivalent for other ministries). |
| 16 | Cybersec firms "issued" guidance | https://mp.weixin.qq.com/s/nmBguRFOyXifa3HnNmJnig | MISS (WeChat) | **WeChat strategy.** |
| 17 | Secure deployment guidance | https://mp.weixin.qq.com/s/IXQDrj3WeDR7Qgqu1cvtGA | MISS (WeChat) | **WeChat strategy.** |
| 18 | Tsinghua/Ant five-layer framework | https://arxiv.org/pdf/2603.11619 | MISS (0 docs from host) | **Out of scope** — academic paper on arxiv. Skip (unless we add an academic-paper tracker as a separate initiative). |
| 19 | Beijing AI Safety Institute audit tool | https://mp.weixin.qq.com/s/hDZgrm4INui-wCV1_uD6ww | MISS (WeChat) | **WeChat strategy.** |
| 20 | CAICT/SJTU/Nanjing vuln disclosure | https://mp.weixin.qq.com/s/van2N3tshZ_AitdMs5qJnQ | MISS (WeChat) | **WeChat strategy.** |
| 21 | TC260 national standard (URL truncated in source) | https://www.tc260... (incomplete) | MISS (0 docs from host) | **Same as #8** — needs TC260 crawler. If user can resupply the full URL we can verify it separately. |

### 2. Domestic AI Governance — "study session" sub-section

| # | Label | URL | Status | Remediation |
|---|---|---|---|---|
| 22 | CCTV Politburo study session | https://tv.cctv.com/2026/01/20/VIDEx0VMRP7T9t8V3w6PF6JF260120.shtml | MISS (3 unrelated docs from host) | **Out of scope (video)** — CCTV video page, body content is a video player. Could capture title + transcript if available, but video pages require different handling. Skip for MVP; revisit if we add a video-metadata crawler. |
| 23 | Xinhua Jan 24 report | https://www.news.cn/20260124/3f1f3cead780463b9f8119285fe6fb4f/c.html | MISS (2,551 xinhua docs but none from that date) | **~~Lost to retention.~~** ⚠️ **CORRECTED 04-13: article is still live.** HTTP 200, 15,043 bytes, 6,755 chars of visible body text. Title: 省部级主要领导干部专题研讨班侧记. The `<title>` tag is empty (Xinhua populates via JS), but body text and `og:title`-equivalent metadata are intact. Real root cause: **discovery gap** — our `general` homepage section was added 2026-04-07, and xinhuanet.com's homepage no longer links to this Jan 24 article. The article never entered our URL discovery pipeline because it was published before the scraper existed. **Recoverable today** with a one-off fetch. Also reveals a title-extraction hazard: Xinhua's empty `<title>` tags need an `og:title` / first-`<h1>` fallback in `crawlers/xinhua.py`. |
| 24 | CAC draft chatbot measures (CN) | https://www.cac.gov.cn/2025-12/27/c_1768571207311996.htm | MISS (754 CAC docs including 3 *expert interpretations* of this exact draft from the same day) | **One-off fetch + structural fix.** The URL is live, verified 24,712 bytes, title `国家互联网信息办公室关于《人工智能拟人化互动服务管理暂行办法（征求意见稿）》公开征求意见的通知`. We crawled 3 `专家解读` (expert interpretation) pieces from 2025-12-27 but missed the original draft they all interpret — consecutive slug IDs (`...207311996` vs `...208...`). **⚠️ SHARPENED 04-13: the asymmetry is far worse than one URL.** Empirical check: CAC corpus has **215 解读 (interpretations) vs 0 征求意见稿 (original drafts)**. Of 45 official notices with title format "国家互联网信息办公室关于...", zero are drafts. The `zcfg` channel (A093703) that our crawler queries returns interpretations but not the drafts they interpret. Additionally, the `zcfg` HTML listing URL (`/zcfg/A093703index_1.htm`) now returns **404** — the JSON API fallback masks this. The correct channel code for drafts has not yet been located. Also notable: some CAC pages like [c_1773925231290620.htm](https://www.cac.gov.cn/2026-02/28/c_1773925231290620.htm) have the real content in **PDF attachments** while the HTML body is just a 219-char stub — our crawler stores only the stub. |
| 25 | CAC draft chatbot measures (EN translation) | https://www.chinalawtranslate.com/en/chatbot-measures-draft/ | MISS (0 docs from host) | **Out of scope** — English translation site, third-party legal translations. Not our corpus remit. If we want the English version of the CAC draft, better to commission a translation ourselves. |

---

## Root-cause summary

### Category A: One-off fetch — 3 URLs (items #15, #23, #24)

All three are from hosts we already crawl, and all are still live.
Can be fetched today with existing `_extract_body` functions.

- **CAC draft chatbot measures (#24)** — surfaces a much deeper problem:
  our CAC crawler has **215 解读 vs 0 征求意见稿** across the entire corpus.
  The `zcfg` channel (A093703) returns only interpretations; drafts live
  in a different channel not yet located. The HTML listing path
  `/zcfg/A093703index_1.htm` is also now 404 (JSON API masks this).
  Additionally, some CAC pages contain PDF attachments where the real
  content lives, but we only store the brief HTML stub.
- **NDA Liu Liehong speech (#15)** — our 5 NDA sections are all under
  `/sjj/zwgk/` and `/sjj/xxgk/`. The leader-activity tree at
  `/sjj/jgsz/jld/*/llhldhd/` is entirely uncovered (verified: 0 docs
  with `/jgsz/` in URL).
- **Xinhua Jan 24 report (#23)** — ~~originally classified as
  "lost to retention"~~. **Corrected 04-13**: the article is still live
  (HTTP 200, 6,755 chars visible). Gap is discovery + title-extraction:
  the `general` homepage section was added after the homepage cycled past
  this URL, and Xinhua's `<title>` tag is empty (JS-populated) which
  would break our extractor. Fully recoverable with a one-off fetch.

### Category B: New crawler needed — 3 hosts (items #3, #4, #8)
All three are authoritative Chinese cybersecurity / standards bodies
that nobody else in our corpus covers:

- **NVDB (nvdb.org.cn)** — 国家漏洞库 — National Vulnerability Database.
  Source of authoritative CVE disclosures. New `crawlers/nvdb.py`.
- **CNCERT (cert.org.cn)** — 国家互联网应急中心 — CERT-equivalent. Source
  of cybersecurity warnings, incident reports, AI/security advisories.
  New `crawlers/cncert.py`.
- **TC260 (tc260.org.cn)** — 全国信息安全标准化技术委员会 — Standards
  committee. Source of Chinese AI safety standards, draft practice
  guides. Core reference for any AI governance research.
  New `crawlers/tc260.py`.

These three together would massively improve coverage for the
cybersecurity-adjacent corner of Chinese AI governance, which is
currently almost entirely absent.

### Category C: WeChat articles — 10 URLs (items #5-7, #9-14, #16-17, #19-20)
Over 40% of the Substack post's citations are `mp.weixin.qq.com/s/{id}`
URLs. This is how **most Chinese policy and industry think-tanks now
publish** — WeChat public accounts (公众号) are the primary distribution
channel for AIIA, CAICT, MSS, CNCERT, MPS, cybersec firms, research
institutes, etc. Our corpus has 493 WeChat docs already but they come as
side effects of other crawlers (local govt sites linking out to WeChat);
we don't have a dedicated WeChat strategy.

**The gap is structural**: WeChat enforces strict anti-bot protections
on `mp.weixin.qq.com`. Options:
1. **Headless browser + cookies** — scrape via a logged-in WeChat account
   in a headless Chromium. Fragile and easily breaks.
2. **Manual curation** — maintain a seed list of target public accounts
   and their known article archives, fetch periodically.
3. **RSS/API wrappers** — some public accounts publish via third-party
   RSS mirrors. Quality varies.
4. **Partner with a WeChat data provider** — paid services that already
   scrape public accounts. Adds cost and dependency.

**Recommendation**: Start with a manual-curation MVP for 5-10 priority
public accounts (AIIA, CAICT, CNCERT, MPS, TC260 if they have one),
seeded from the Substack post's citation list. Don't try to crawl all
of WeChat.

### Category D: Out of scope — 5 URLs (items #1, #2, #18, #22, #25)
- **English media** (sixthtone, thewirechina, chinalawtranslate):
  Intentional — the corpus is Chinese-source. These live in the
  analyst / secondary-source layer.
- **Arxiv** (item #18): Academic paper — separate initiative if we
  want an academic-tracker.
- **CCTV video** (item #22): Video player page — different media
  type, different handling.

### ~~Category E: Lost to retention — 1 URL (item #23)~~
**Dissolved 04-13.** Item #23 was moved to Category A after verifying
the Xinhua article is still live. No URLs in this audit are actually
lost to retention.

---

## Action plan (work through in order)

*Updated 04-13 with corrections from empirical recheck.*

1. **Immediate**: One-off fetch 3 URLs — CAC draft (#24), NDA Liu
   Liehong speech (#15), Xinhua Jan 24 report (#23, still live).
   Also fix Xinhua title extraction (`<title>` is empty; need
   `og:title` or first-`<h1>` fallback in `crawlers/xinhua.py`).
2. **This week**: Investigate CAC channel structure — find where
   征求意见稿 drafts live. The `zcfg` channel (A093703) has 215
   解读 and 0 drafts. Also: extend NDA crawler to include
   `jld/*/llhldhd/` leader activities. Add CAC PDF attachment
   extraction (some pages like c_1773925231290620.htm have real
   content in PDF, HTML body is just a 219-char stub).
3. **This week**: Build `crawlers/nvdb.py`, `crawlers/cncert.py`,
   `crawlers/tc260.py`. Each ~200 lines, same ministry-crawler
   pattern. Biggest topical win for AI safety research.
4. **Medium-term**: Design a WeChat strategy. Start with manual
   curation of 5-10 priority public accounts.
5. **Out of scope permanently**: English media, arxiv, CCTV video
   (unless explicitly re-scoped).

## Why this list matters

The Substack post is exactly the kind of research consumer we want to
serve: someone building an argument about Chinese AI governance using
primary Chinese-language policy sources. That the post draws on 24
sources and we have **zero exact matches** is a crisp measure of the
gap between "large corpus" and "analytically useful corpus for this
specific research question." The fix is not "crawl more stuff" — it's
"crawl the right stuff," which in this case means the
cybersecurity/standards layer (NVDB, CNCERT, TC260) and the WeChat
distribution layer.

---

## Strategic takeaways

The four insights below are the reason this audit matters more than a
typical "coverage check." Worth re-reading before scoping any of the
remediation work.

### 1. "0/24 against a real bibliography" is the most useful gap measure we have

Counting total documents tells you **size**; counting matches against
someone's actual bibliography tells you **analytical usefulness for a
specific research question**. We've been measuring the corpus by
volume (138k docs, 66 sites, 93% body coverage) — all legitimate
metrics, but none of them would have flagged that we have zero of the
things this particular researcher cites.

This is the single best kind of gap analysis because it's grounded in
how a real analyst actually cites sources, not in our own guesses
about what's important. Running similar audits against 2-3 more
recent Chinese AI-governance pieces (e.g., CNAS or CSET reports,
Asia Society commentary, academic papers from policy journals) would
quickly reveal whether the gap shape we found here is idiosyncratic
to one author or structural to the research community.

**Action:** Turn this into a recurring practice. Pick 3-5
well-researched Chinese AI-governance pieces per quarter and run the
same audit. If the cybersecurity/standards + WeChat pattern
replicates, we know where to prioritize. If different gaps appear
each time, we know coverage needs to be more breadth-oriented.

### 2. The WeChat finding is the structurally biggest lesson

Over 40% of the Substack post's citations are `mp.weixin.qq.com`
URLs. For AIIA, CAICT, cybersec firms, and most Chinese policy
think-tanks, **WeChat IS the primary publication venue.** They don't
publish on their own websites first — they push to 公众号 (public
accounts) and the "official" site is often a stale mirror.

Any Chinese AI-governance corpus that doesn't crawl WeChat has a
systematic blind spot. Ours does, and we were treating it as noise —
our 493 existing WeChat docs are side-effects of other crawlers (local
government sites linking out). That's backward: WeChat should be a
first-class source, not an accidental one.

Fixing this is a **different kind of problem** than adding more
ministry crawlers. WeChat's anti-bot posture means none of our
existing patterns work. The real options are:

1. **Headless browser + logged-in cookies** (fragile, account bans)
2. **Manual curation** (start with 5-10 priority accounts, seeded
   from audits like this one) ← **recommended MVP**
3. **Third-party RSS mirrors** (quality varies, coverage sparse)
4. **Paid WeChat data provider** (adds ongoing cost + dependency)

The MVP path is: maintain a seed list of ~10 priority public accounts
(AIIA, CAICT, CNCERT, MPS/中央政法委官微, TC260 if present, 人民日报评论,
and the major cybersec firms), curate a "known article URLs per
account" list, and fetch each URL through a polite headless browser
pipeline once per week. Accept that this won't scale to thousands of
accounts — the value is in depth, not breadth.

**This deserves its own design doc before implementation** (similar
to the Brookings-bio-generator doc). Don't just start writing a
`crawlers/wechat.py` — think about the curation workflow, the
browser infrastructure, the refresh cadence, and the failure modes
first.

### 3. The CAC "draft vs interpretation" asymmetry is a subtle gap pattern

We crawled 3 expert interpretations of the chatbot measures (2025-12-27)
but not the document they interpret — and the slug IDs are consecutive:

```
MISSING: c_1768571207311996.htm   ← the draft measures
HAVE:    c_1768571208101359.htm   ← expert interp #1
HAVE:    c_1768571208306469.htm   ← expert interp #2
HAVE:    c_1768571208631968.htm   ← expert interp #3
```

The originals and the interpretations are published in the same
batch. Our crawler is pulling from an "interpretations index" and
missing the "drafts for public comment" index. This isn't a one-off
bug — it's a systematic pattern that probably repeats across many
CAC dates.

**When we fix it, we should audit:** for every 解读 row we have from
2024-2026, do we also have the original 征求意见稿? The mismatch count
will tell us how many drafts we're silently missing. If it's in the
dozens, it's a coverage issue. If it's in the hundreds, the audit
pattern itself is worth adding as a nightly sanity check.

More generally: **any time we have a "commentary on X" without "X,"
the corpus is analytically lopsided.** The fix isn't just to crawl
more — it's to build relational consistency checks between doc types.

### 4. The cybersecurity/standards layer is a coherent mini-corpus we're missing

NVDB + CNCERT + TC260 + NDA + CAICT + AIIA together form the Chinese
"AI safety / cybersecurity" ecosystem. These bodies cite each other
heavily — a TC260 draft practice guide references NVDB disclosures,
which reference CNCERT warnings, which cite MSS advisories, which
are interpreted by AIIA and CAICT. It's a dense discourse network
with its own vocabulary and internal logic.

Right now we have NDA in full, partial CAC, and **nothing else** from
this ecosystem. Adding NVDB + CNCERT + TC260 (each a ~200-line
crawler in the existing ministry pattern) would turn this from a
"partial corpus with holes" into a "comprehensive view of the
ecosystem." It's arguably a **higher-leverage expansion than adding
more provincial crawlers** — not because provinces don't matter, but
because the cybersecurity layer is internally coherent enough that
adding the missing nodes reveals relationships you literally cannot
see with partial coverage.

**Estimated effort:** ~1-3 days per crawler × 3 = 1 week. Output:
the entire AI-safety policy discourse becomes visible to our
citation graph and the network viz on `/network`.

---

## Recommended order of operations

For the next sitting on this backlog:

1. **Two one-off fetches first** (action plan step 1). CAC draft
   measures + NDA Liu Liehong speech. Validates the `_extract_body`
   functions of each crawler against the missing sections and
   produces immediate corpus value. ~30 min of work.

2. **Extend the CAC + NDA crawlers structurally** (action plan
   step 2). Find the CAC `征求意见稿` index; add the NDA
   `jld/*/llhldhd/` leader-activity section. Run the "do we have
   originals for every interpretation" consistency check as part
   of this. ~1 day.

3. **Decide on WeChat strategy** (highest-leverage structural
   decision). Don't start coding yet — write a design doc like the
   Brookings-bio one first. Options, costs, failure modes, seed
   account list.

4. **Build the 3 cybersecurity crawlers** (NVDB, CNCERT, TC260) in
   parallel with or after the WeChat design decision. They're the
   biggest topical win for AI safety / cybersecurity research and
   they're all standard HTML-scrape patterns we already know how
   to do.

5. **Permanent exclusions**: English media, arxiv, CCTV video. Leave
   alone unless someone explicitly re-scopes.

6. **Run one more link audit** against a different recent Chinese
   AI-governance piece before committing to all of the above — if
   the gap shape is different, reprioritize. If it's the same, we
   have confirmation that this is the real structural gap.

