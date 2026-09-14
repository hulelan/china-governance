# Section-level coverage — what to crawl, what's empty, what needs a new scraper

Supplements the source-level coverage (`coverage.csv`, `gov-website-catalogue.csv`,
`source-access-map.md`) with a level DOWN: which document SECTIONS (`/yaowen/`, `/zwgk/`,
`/zxgk/`…) within each crawled host we cover vs. miss. Built 2026-09-14.

## How it's built (two levers, in `scripts/rnd/discovery/`)
1. `find_missing_sections.py` — per host, diff the path-prefixes we've stored docs from
   against the prefixes the site links from its homepage. Flags doc-ish sections we hold ~0.
2. `section_coverage.py` — the CONFIRMATION probe. For each flagged section it fetches the
   page (descending hub→list, e.g. `/yaowen/`→`/yaowen/liebiao/`), runs `govcms._list_articles`,
   and checks whether those article URLs are ALREADY in our DB (by URL, any prefix). This
   collapses the false positives (list-section URL ≠ article URL, the gkmlpt cluster).

Data: `section-coverage.csv` (site_key, section, arts_found, held_pct, raw_status, bucket,
decision, sample_url). Reachability is from the DROPLET (the crawl vantage).

## The buckets (219 candidate sections across 299 sites)

| decision | n | meaning | action |
|---|---|---|---|
| **crawl_now** | 88 | reachable, lists articles, <50% held, host body-extraction is healthy | add the section to the crawler + crawl |
| **defer_body_fix** | 25 | crawl_now BUT the host is a low-body crawler (GD depts, miit…) | fix body extraction FIRST, then crawl (else more shells) |
| **build_scraper** | 28 | section reachable + a real page, but NO known dialect matches (JS/unknown) | needs a new dialect or a bespoke crawler |
| **sweep_unreliable** | 74 | droplet can't reach it (DNS/WAF/dead homepage) OR only a stub returned | can't assess from the droplet — residential/proxy needed, or genuinely dead |
| **have** | 4 | false positive the probe caught (we already hold ≥50%) | none |

### crawl_now — the ready queue (top by yield)
`cppcc /zxgk/` (政协公开, 111 arts, we hold 7%), `gddrc /zwgk5590/` (97), `fj_jtyst /fzgkj/` (70),
`gov /yaowen/` + `/lianbo/` (the AI Action Plan section), `fj_czt`/`fj_wjw`/`fj_jtyst /jggk/`,
`shb_edu`/`shb_yjj` sections, plus many GD-city dept-dynamics sections (lower research value).
Mechanism: for hosts already in `govcms.SITES`, append the section to their `sections`; for
others (cppcc, gov) add a `govcms` config using the matching dialect. `held_pct` is real (URL
membership), so these are genuine document gaps, not storage-prefix artifacts.

### sweep_unreliable — "the sweep did not work on these" (documented, not gaps)
27 hosts the droplet couldn't resolve/reach at all (`HOMEPAGE_UNREACHABLE` — the gkmlpt GD-city
cluster: zhongshan, zhuhai, jieyang…, which are datacenter-IP-blocked from NYC) + 47 sections that
returned a stub or dead. These need a residential/proxy vantage to assess. The tool CANNOT judge
them; do not read their absence as "covered" or "missing." See `source-access-map.md` for the
datacenter-IP-block tier.

## Verified gaps (investigated separately — `verified-gaps-investigation.md`)

Three high-value AI-governance primary texts a spot-check surfaced, and their fixes:

| gap | status | fix | done? |
|---|---|---|---|
| SPC 《涉人工智能纠纷案件的意见》 (ipc_court) | 387/389 body-less | RE-EXTRACT from saved HTML (patched `_extract_article`) | **DONE — 242 recovered incl. the opinion (10,560 chars) + its 理解与适用** |
| GD dept subdomains 0% body (~3,600 docs) | body never extracted (wrong container) + raw HTML not saved | add `article-content` container to `gkmlpt.extract_body_text` + **RE-CRAWL** bodies | queued |
| 中国网信杂志 署名文章 (e.g. AI safety essay) | not crawled | magazine = WeChat mini-program (Tier E, NEW SOURCE); + cheap add of un-crawled `cac.py` channels (高端观察 gdgz) for open-web essays | queued |
| gov.cn `/yaowen/` (AI Action Plan) + 中国网信 | section/source not crawled | crawl `/yaowen/liebiao/` via govcms content_N dialect; cac channel add | queued (in crawl_now) |

## The three gap TYPES (the mental model)
1. **Missing section** — the doc's folder isn't crawled (gov.cn `/yaowen/`). Found by this tool.
2. **Missing source** — the whole outlet isn't crawled (中国网信杂志). Found by `gov-website-catalogue.csv`.
3. **Hollow crawl** — we have the title + URL but no body (ipc_court, GD depts, miit). Found by the
   body-coverage audit (`SELECT site_key, 100.0*SUM(body_text_cn!='')/COUNT(*) FROM documents GROUP BY 1`).
