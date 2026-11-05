# The source fill: financial press + a URL ingest

**Date:** 2026-11-05. **Vantage:** the droplet's NYC datacenter IP (104.236.88.45).
**Artifacts:** `crawlers/finmedia.py`, `scripts/ingest_urls.py`,
`tests/test_finmedia_extract.py` (26 cases), `tests/test_ingest_urls.py` (26 cases),
two new `data/source_ontology.yaml` leaves.

## Why

On 2026-10-30 a query for the 中国高科 corporate-governance case
(《"中国高科"间接控股公司迁址未了局：行政立案与刑事立案下的两地博弈》) returned **zero**, and the
cause was established as a **source** gap rather than a query bug: the corpus carried 15
`admin_level='media'` sites and **none** of them were financial press. No 财新, no 经济观察报, no
第一财经, no 界面; 澎湃 was a single stub row.

The research consequence is not about one article. **Government sites publish the instrument;
they do not publish the enforcement, the dispute, or the firm-side reaction.** That
implementation layer is where the political-economy replications need evidence, and it was
absent by construction. The 2026-10-25 row this work recovered makes the point concretely —
湖南省网信办集中约谈某文化传媒公司等4家大模型运营单位 — an 约谈 of four large-model operators
over 算法备案 and 数据安全 failures, which no government portal published.

## What is reachable, measured

HTTP 200 is unreliable, so every row below is byte-checked on a real **article** page, not a
homepage, and the body column is CJK characters of extracted prose.

| tier | site | key | article body | date source | verdict |
|---|---|---|---|---|---|
| 1 | 中国经济网 / 经济日报 | `ce` | 1,345–1,636 | URL `tYYYYMMDD` + `meta publishdate` | clean |
| 1 | 经济参考报 (新华社) | `jjckb` | 1,877–2,514 | URL `/YYYYMMDD/` + `meta publishdate` | clean |
| 1 | 第一财经 | `yicai` | 878–2,378 | JS `['actime','ISO']` | clean |
| 2 | 界面新闻 | `jiemian` | 2,129–9,969 | **none server-rendered** | body clean, date missing |
| 2 | 经济观察报 | `eeo` | 1,379–3,028 | URL `/YYYY/MMDD/` | clean |
| 2 | 钛媒体 | `tmtpost` | 2,636–6,203 | `class="time">YYYY.MM.DD` @ ~byte 82k | clean |
| 2 | 虎嗅网 | `huxiu` | 669–6,606 | `article:published_time` @ >20k | clean, occasional TLS timeout |
| 3 | 财新 | `caixin` | **484–658** | URL `/YYYY-MM-DD/` | **PAYWALLED — lede only** |

**Not configured, with the reason:**

| site | status |
|---|---|
| 澎湃 `thepaper.cn` | HTTP **403** from the droplet (WAF geo-block) |
| 财联社 `cls.cn` | SPA; its JSON API requires a request signature (`errno 10012 签名错误`) |
| **中国信通院 `caict.ac.cn`** | HTTP **412** (WAF). **This matters**: CAICT published 《智能体发展自律公约》, so that document can only arrive via media coverage |
| 证券时报 `stcn.com` | TCP blackhole (`000`) |
| `nytimes.com` / `reuters.com` / `investing.com` | 403 / 401 / 403 — hard blocks, not fixable from this vantage |

**财新 is metadata-plus-lede, not a body.** Its article `<p>` content measures 8 paragraphs /
484–658 CJK across three samples — the teaser, not the article. Its rows therefore carry
`relation='body=paywall_teaser'`, because a 600-character lede is real signal and passing it off
as a body would silently corrupt every length-, coverage- and body-keyed measure downstream.

**界面 has no server-rendered date, and this is now PROVEN rather than inferred.** Older articles
(7-digit ids) carry a Unix timestamp in `<span class="date">`; current ones (8-digit) carry
nothing. The page's own JS object literal reads **`publish_time: ''`** — the field exists and is
empty in the delivered source — and the only 10-digit numbers in the document are `data-id`
attributes on nav elements, *identical across different articles* (1641195066, 1796714275), so
they are element ids and not timestamps. Mobile and desktop bodies are byte-identical in CJK
count (2678 = 2678), so there is no second host to try either. The date is fetched client-side
and there is nothing to parse.

Its rows therefore store an **empty** `date_published`, which `doc_identity.date_quality` flags
as `missing`. **Deliberately not inferred from the crawl day** — that is precisely the
`crawl_stamped` failure CLAUDE.md devotes a section to. The measured cost: the first run stored
**98 jiemian rows, all 98 undated**, so at a nightly cadence this accumulates.

**The one legitimate route, not yet built.** The listing page carries the publisher's **own** date
label beside each headline (times like `08:25` for same-day items). Capturing that label *at
discovery* is materially different from crawl-stamping: it records the site's stated date rather
than assuming our fetch day. It needs the listing's semantics for older items established first
(does a section page show a full date, or only a time?), which is why it is written down here
instead of guessed at. Until then jiemian is a high-quality-body, no-date source — fine for text
analysis, unusable in the tracker.

## Four extraction defects, all found by measuring rather than reviewing

Running `scripts/ingest_urls.py` against 62 real brief URLs failed on **15**. The pattern was
one mistake wearing four hats: **every threshold in the extractor counted CJK characters**, so a
rule validated on Chinese pages returned nothing at all on anything else.

1. **`extract_title` required ≥4 CJK**, so no English page could *ever* produce a title. Business
   Recorder fetched at 277 KB with a perfectly usable `<title>` and returned `""`. Five rows lost
   to this alone.
2. **`extract_body` gated paragraphs on CJK count alone.** Business Recorder has 15 `<p>` of ~250
   English characters, Zhong Lun 170 of up to 1,260; both extracted to **zero**.
3. **Some pages carry no prose in `<p>` at all** — `npc.gov.cn` has 2 paragraphs and
   `nda.gov.cn` 1, while their flattened text holds **1,531** and **777** CJK in long lines. A
   long-line fallback now runs when the `<p>` pass comes back thin.
4. **`base._decode` hardcoded `raw.decode("utf-8", errors="replace")`** and never consulted the
   page's declared charset, so every GBK-served page became U+FFFD mojibake.
   `hn.chinanews.com.cn` gave 2,538 characters of which **10** were CJK, title included.

Result: **15 failures → 5**, and all 5 survivors are hard WAF/paywall blocks.

### The decode bug deserves its own note

This is the failure class CLAUDE.md already records for the 725 `mofcom` rows, arriving by a
different route. There the corruption was at the source (an ASCII `?` served by the listing
endpoint) and our decoding was explicitly cleared; **here our decoding was the cause.** The
consequence is identical and worth restating because it is easy to under-rate: a mojibake title
is invisible to **both** FTS indexes, can never be a citation target, and can never match a
`title_reissue` diffusion edge. **A corpus can hold a document and still not have it.**

`_decode_text` is deliberately conservative, because all 48 crawlers share it: utf-8 is tried
**first** and its result kept unless replacement characters exceed a stray-byte rate
(`max(8, len//2000)`); only then is the declared charset, then gb18030, then big5 consulted, and
an alternative is accepted **only if it strictly reduces** the replacement count. A test pins
the safety property directly — *a page that decoded cleanly before decodes identically now*.

### And fixing the fallback introduced a bug the tests caught first

The long-line fallback initially reused `_flat`, which **deletes** tags. That is correct inside
one paragraph and wrong across a document: `首页 更多 分享到：` ran together with the first real
paragraph as a **single line**, so no length filter could separate them and nav text would have
landed in bodies corpus-wide. `_lines` flattens a document with every tag becoming a break;
`_flat` keeps its single-element contract. Caught by
`test_short_nav_paragraphs_are_dropped` before it shipped.

## `scripts/ingest_urls.py` — the lever

Briefs cite documents by URL. This takes the list and resolves, fetches, extracts and stores each
one with its provenance (`relation='ingest=url_list;tag=<tag>'`). The next brief is one command.

**Host resolution is an explicit table, not a match.** A fuzzy `root in base_url` lookup resolved
`www.gov.cn` to site keys `szpsq`, `sz` and `stic`, because "gov.cn" is a substring of
"szpsq.sz.gov.cn" — this project's most frequent bug shape, a lookup returning a clean answer for
the wrong reason. `HOSTS` maps an exact netloc to an exact `site_key`; an unmapped host is a
**loud refusal naming it**, and `--allow-new` is the explicit opt-in.

**URL date patterns are anchored to known path shapes.** An unanchored date regex matches a CDN
upload path before a publication date — measured, it read `2024-05-20` off tmtpost's image URL
and `2016-07-20` off huxiu's, i.e. a date years wrong on a current article. A wrong date is worse
than a missing one, because `date_quality` can flag the missing one and nothing flags the wrong
one. `tests/test_ingest_urls.py` pins 16 real brief URLs **and** the negative cases.

## Result of the first run

62 URLs from the 21 Oct – 4 Nov briefs: **50 stored, 7 already held, 5 blocked.** Corpus
377,895 → **377,945**, across 29 sites and 3 admin levels (central 10, media 14, foreign 5).

Only **7 of 62** were already held, and the misses are informative:
`www.news.cn` contributed **0 of 6** despite the corpus holding **6,080** documents from that
host — so the Xinhua crawler is missing a whole path family, which is now a tracked question.

Documents recovered that the corpus did not have:

- **《携手构建全球开放人工智能行动倡议》** (`wic`, 2026-11-02) — previously **0 titles / 0 bodies**.
  Note it is the WIC committee's *announcement*: it describes the 18 行动倡议 across four themes
  but does not enumerate them, so the full 18-point text is still outstanding.
- **中办、国办《关于推动科技创新和产业创新深度融合的意见》 full text** (`guandian`, 4,549 chars)
- **《产业基础能力提升"十五五"规划》** — the 8-ministry notice (`miit`)
- **中央网信委《国家信息化"十五五"规划》** (`yicai`)
- **国务院办公厅《关于适应人工智能技术发展助力构建就业友好型发展方式的意见》** (`people`)
- **二十届五中全会公报** (`xinhua`, 4,728 CJK)
- **国务院国资委 国家数据集团有限公司 组建公告** (`sasac`) + 丁薛祥's attendance (`xinhua`)
- **李强's WIC keynote from `mfa`** — the authoritative central copy. The corpus previously held
  it only via `jcgov`, a **Shanxi prefecture-city portal**, i.e. a mirror rather than the source.
- **湖南省网信办 约谈 4 家大模型运营单位** (`chinanews_hn`) — recovered *only* because of the
  decode fix. Note 约谈 is 2 characters and not a jieba token, so it is invisible to **both** FTS
  indexes and findable only by `LIKE`; CLAUDE.md records that blind spot.
- **Business Recorder's RMB fixing series** (5 rows, 4,261–4,908 chars) — the FX evidence the
  briefs cite, previously all lost to the English-title bug.

## Ontology

The validator **failed** on the 16 new site keys, which is the guardrail working: media is
explicit-only so that "exclude news" can never silently swallow a government site. Two leaves
were added — `media_financial` (ownership deliberately **not** encoded: it spans central Party
papers, state-group titles and private ones, and mixing ownership into a type tree would make one
leaf mean two things at once) and `media_foreign` (under `media` so "exclude news" catches them,
but its own leaf, because folding them into `media_commercial` would repeat one level out the
error that read 47 of 105 documents as sub-national diffusion when 44 were media).

`VALIDATION: PASS`, and **"Other / Unclassified" went 26 → 0** — every site key in the corpus
now resolves to a leaf.

## Did the fill buy the layer it was meant to? A named test, measured — and it SPLIT

The justification written into this work was "government sites publish the instrument; they do not
publish the enforcement, the dispute, or the firm-side reaction." Tested directly against the 793
financial-press rows and 317,301 government rows (counted by `LIKE`, which has no length floor —
约谈 and 立案 are 2 characters and invisible to both FTS indexes):

| term | financial press | government | ratio |
|---|---|---|---|
| 索赔 (damages claim) | 1.0% | 0.2% | **5.65x** |
| 立案调查 (case opened / investigation) | 0.8% | 0.2% | **3.24x** |
| 起诉 (sue) | 1.4% | 0.9% | 1.55x |
| 维权 (rights defence) | 1.5% | 1.3% | 1.14x |
| 行政处罚 (administrative penalty) | 1.1% | 3.9% | **0.29x** |
| 整改 (rectification) | 1.4% | 8.0% | **0.17x** |
| 约谈 (summoned for talks) | 0.1% | 1.4% | **0.09x** |
| 行政立案 / 刑事立案 / 败诉 | ~0 | ~0 | — |

**The original claim was too strong and is corrected here.** Government portals carry
*administrative* enforcement vocabulary far MORE than the financial press does — 整改 at 8.0%,
行政处罚 at 3.9%, 约谈 at 1.4% — which in hindsight is obvious, because a 行政处罚决定书 or a
整改通知 **is** a government document. The defensible version of the claim is narrower: what the
financial press adds is **investor-side and private-law conflict** — damages claims, securities
investigations, litigation — which no government portal publishes, and which is exactly what the
中国高科 case (行政立案与刑事立案下的两地博弈) is made of.

**And the test is underpowered**, which has to be said plainly: at n=793 a 1.0% rate is about 8
documents, so the ratios above are directional, not estimates. Re-run it after tier 2 and a
backfill take the financial tier past a few thousand rows. The two terms that would settle it —
行政立案 and 刑事立案 — are at ~0 on BOTH sides, so this corpus cannot yet speak to the specific
vocabulary of the case that started the whole exercise.

## huxiu needs curl_cffi FIRST, measured on the tier-2 run

`huxiu` is not "occasionally" slow, which is how the first run described it. Measured on the
2026-11-05 tier-2 crawl: **every** article times out on urllib **twice** (`The read operation
timed out`, two retries) and then succeeds through the `curl_cffi` fallback — `curl_cffi fallback
OK (102055B)`, `(120102B)`. The cost is ~**2.5 minutes per article**, so 72 discovered URLs take
roughly 3 hours, against 58 tmtpost articles in 4 minutes and 76 eeo in 3.

**The consequence for the nightly is that huxiu can never catch up.** Under the 600s
`run_crawler_t` cap it will fetch about four articles a night, so it accrues a permanent backlog.
This is not a reason to raise the cap — Phase 1 is already 240-271 min for ~250 documents — it is
a reason to stop paying for two doomed urllib attempts. `base.fetch` already has the curl_cffi
path (it defeats fingerprint WAFs that reject urllib's ClientHello, which is evidently what huxiu
runs); what is missing is a way for a site to say "go there first". A per-site
`impersonate_first` hint in the registry, honoured by a thin wrapper around `fetch`, would cut
huxiu to roughly one third of its current cost without touching any other crawler's path.

Note this is the same economics as the PDF `_is_timeout` fix (CLAUDE.md, `2653392`): there, two
30-second attempts per dead row made retiring one host cost eight minutes, and the fix was to
stop making the second attempt when the first failure could not be the one the fallback exists
for. Here the fallback is the one that WORKS and the first attempt is the doomed one, so the
asymmetry runs the other way — but it is the same question, *which attempt is paying for itself*.

## Still outstanding

1. **《智能体发展自律公约》 is still 0 titles.** The corpus holds only coverage — `guancha`
   `900206803` and `yicai` — because CAICT is 412-blocked. Needs a non-datacenter vantage, or a
   mirror on a reachable host.
2. **The full 18-point 倡议 text**, as above.
3. **WAICO's 38-country figure.** The 3 Nov NDRC presser is now held via `chinanews`
   (中国国家发改委：正推动世界人工智能合作组织实体化运行进程); 华春莹's 2 Nov NPCSC ratification
   motion returned nothing and is not held.
4. **`www.news.cn`: 0 of 6 held against 6,080 in corpus** — a missing path family in
   `crawlers/xinhua.py`.
5. **界面 dates** — needs the client-side payload or an API.
6. **`zhonglun`'s title** is the site's generic `<title>` ("The official website of Zhong Lun Law
   Firm"); needs `og:title`/`h1` preference for that host.
7. **财新 beyond the lede** would need a subscription; out of scope.
