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
| 23 | Xinhua Jan 24 report | https://www.news.cn/20260124/3f1f3cead780463b9f8119285fe6fb4f/c.html | MISS (2,551 xinhua docs but none from that date) | **Lost to retention.** This is the same Jan-to-April retention pattern we discovered for xinhua's `general` section (articles get deleted after ~6 weeks). The article is now behind Xinhua's rolling window. Future Jan articles WILL be captured because we added the `general` section 2026-04-07 — but this specific Jan 24 doc is unrecoverable without Wayback. Add to Wayback backfill scope. |
| 24 | CAC draft chatbot measures (CN) | https://www.cac.gov.cn/2025-12/27/c_1768571207311996.htm | MISS (754 CAC docs including 3 *expert interpretations* of this exact draft from the same day) | **One-off fetch + structural fix.** The URL is live, verified 24,712 bytes, title `国家互联网信息办公室关于《人工智能拟人化互动服务管理暂行办法（征求意见稿）》公开征求意见的通知`. We crawled 3 `专家解读` (expert interpretation) pieces from 2025-12-27 but missed the original draft they all interpret — consecutive slug IDs (`...207311996` vs `...208...`). Our CAC crawler has a systematic asymmetry: captures interpretations but skips the `征求意见稿` original drafts they're about. Can ingest this one URL immediately; structural fix is to audit what CAC section contains the drafts and add it. |
| 25 | CAC draft chatbot measures (EN translation) | https://www.chinalawtranslate.com/en/chatbot-measures-draft/ | MISS (0 docs from host) | **Out of scope** — English translation site, third-party legal translations. Not our corpus remit. If we want the English version of the CAC draft, better to commission a translation ourselves. |

---

## Root-cause summary

### Category A: One-off fetch — 2 URLs (items #15, #24)
Both are from hosts we already crawl (NDA, CAC), just from sections our
crawlers don't hit. We can ingest each with a ~10-line script that uses
the existing `_extract_body` functions.

- **CAC draft chatbot measures** — also surfaces that our CAC crawler
  misses `征求意见稿` original drafts while capturing the 解读 that
  interpret them. Structural fix = one backlog item.
- **NDA Liu Liehong speech** — also surfaces that we don't crawl
  any ministry's `jld/*/llhldhd/` (leader activity) section.

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

### Category E: Lost to retention — 1 URL (item #23)
The Xinhua Jan 24 article was deleted from the origin before we added
the `general` section. Unrecoverable without Wayback. Add to the
Wayback backfill scope for `news.cn/{YYYYMMDD}/{uuid}/c.html` URL
pattern.

---

## Action plan (work through in order)

1. **Today (immediate)**: Ingest CAC draft measures (#24) and NDA Liu
   Liehong speech (#15) as one-off fetches into documents.db. Rsync.
2. **This week**: Investigate which CAC section holds `征求意见稿`
   original drafts. Extend the CAC crawler to cover it. Also extend
   NDA crawler to include `jld/*/llhldhd/` (leader activities) for
   Liu Liehong and any other bureau leaders.
3. **Next 1-2 weeks**: Build `crawlers/nvdb.py`, `crawlers/cncert.py`,
   `crawlers/tc260.py`. Each is ~200 lines, similar to existing
   ministry crawlers.
4. **Medium-term**: Design a WeChat strategy. Start with manual
   curation of 5-10 priority public accounts.
5. **Eventually**: Xinhua Wayback backfill would recover item #23
   (tracked in existing Wayback backlog).
6. **Out of scope permanently**: English media, arxiv, CCTV video
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
