# gkmlpt Platform Survey: Expansion Feasibility

*Conducted 2026-02-22. Probed Chinese government websites to determine which use the gkmlpt (政府信息公开目录管理平台) platform.*

## Key Finding

**gkmlpt is a Guangdong provincial system**, not national. All confirmed instances are part of the Guangdong digital government ecosystem (`cloud.gd.gov.cn`). They share JavaScript/CSS assets, use `search.gd.gov.cn` for search and `statistics.gd.gov.cn` for analytics. SID numbering reflects Guangdong administrative codes (provincial site = `2`, city-level = 6-digit codes).

## Confirmed gkmlpt Sites

These sites return HTTP 200 at `/gkmlpt/index` with `window._CONFIG` containing `SID` and `TREE`:

| City | Domain | SID | Notes |
|------|--------|-----|-------|
| **Guangdong Province** (广东省) | `www.gd.gov.cn` | `2` | Provincial government |
| **Shenzhen** (深圳) | `www.sz.gov.cn` | varies | 20 sites already crawled (45,130 docs) |
| **Guangzhou** (广州) | `www.gz.gov.cn` | `200001` | Provincial capital, largest Guangdong city |
| **Zhuhai** (珠海) | `www.zhuhai.gov.cn` | `756001` | Special Economic Zone |
| **Huizhou** (惠州) | `www.huizhou.gov.cn` | `752001` | |
| **Jiangmen** (江门) | `www.jiangmen.gov.cn` | `750001` | |

## Unreachable (Likely gkmlpt)

These Guangdong cities timed out or refused connections from our network. Given they're in the same province, they likely use gkmlpt too:

| City | Domain | Result |
|------|--------|--------|
| **Dongguan** (东莞) | `www.dongguan.gov.cn` | Timeout |
| **Zhongshan** (中山) | `www.zhongshan.gov.cn` | Timeout |
| **Foshan** (佛山) | `www.foshan.gov.cn` | Connection refused |

## Not gkmlpt

These major cities and the central government returned 404 at `/gkmlpt/index`:

| Site | Domain | Status |
|------|--------|--------|
| **Beijing** (北京) | `www.beijing.gov.cn` | 404 |
| **Shanghai** (上海) | `www.shanghai.gov.cn` | 404 |
| **Hangzhou** (杭州) | `www.hangzhou.gov.cn` | 403 |
| **Wuhan** (武汉) | `www.wuhan.gov.cn` | 404 |
| **Nanjing** (南京) | `www.nanjing.gov.cn` | 404 |
| **State Council** (国务院) | `www.gov.cn` | 404 |

Each of these uses a different CMS and would require its own crawler adapter.

---

## Expansion Tiers

### Tier 1: Other Guangdong gkmlpt cities (zero code changes)

Just add entries to the `SITES` dict in `crawler.py`. The crawler, database, web app, and analysis tools all work as-is.

**Immediate targets:**
- Guangzhou (`www.gz.gov.cn`, SID `200001`) — provincial capital, likely the largest single source
- Guangdong Province (`www.gd.gov.cn`, SID `2`) — provincial-level directives, critical for vertical analysis
- Zhuhai, Huizhou, Jiangmen — confirmed working

Each city also has departmental and district sub-sites (like Shenzhen's 20), discoverable by scanning subdomains for `/gkmlpt/index`. Guangzhou alone could have 30+ sub-sites.

**What this gives you:** The full central→provincial→municipal→district chain within Guangdong. Guangdong has 21 prefecture-level cities and 127 million people — China's richest and most economically significant province. This is already a unique dataset nobody else has.

### Tier 2: Non-Guangdong provinces (new crawler adapter per platform)

Each province runs its own CMS. Requires:
1. Reverse-engineer the listing API (like we did for gkmlpt — inspect Vue.js bundles, find endpoints)
2. Write a new `discover_site()` + `crawl_category()` + `extract_body_text()` for that platform
3. Map their metadata fields to our schema

**Estimated effort:** 1-2 days per new platform, assuming the site is accessible from outside China.

The database schema and web app are already generic — they accept documents from any source. The `site_key` and `admin_level` fields handle multi-province data without changes.

### Tier 3: Central government (gov.cn) — different system entirely

The State Council's website uses a custom CMS. Different URL structure, different API (if any — may require HTML scraping), different metadata fields. Would need its own dedicated crawler.

However, central-level documents are already partially available through other projects (China Horizons covers State Council 2018-2025). The unique value of this project is the **sub-national** data that nobody else collects.

---

## Strategic Recommendation

**Expand within Guangdong before going to other provinces.** Reasons:

1. **Zero code changes** — just add SITES entries
2. **Completes the vertical chain** — central (via citations) → Guangdong provincial → municipal → district
3. **Largest possible dataset per unit of effort** — potentially 200+ sites across 21 cities
4. **Unique value** — nobody else (China Horizons, DigiChina, etc.) covers sub-provincial data systematically
5. **Proves the "experimentation under hierarchy" thesis** — Guangdong cities implement provincial directives differently, and the data to show this would be in hand

After Guangdong is comprehensive, expanding to a second province (e.g., Zhejiang with Hangzhou, or Sichuan with Chengdu) would demonstrate cross-provincial comparison capability, which is the killer feature for Direction 2 (the "vertical-to-horizontal translator").

---

## Technical Notes

- All confirmed gkmlpt sites use **HTTP only** (HTTPS fails or redirects poorly). Same as Shenzhen.
- The API pattern is identical across all sites: `/gkmlpt/api/all/{category_id}?page={n}&sid={sid}`
- Category trees vary by site but the structure is the same JSON format.
- Document IDs appear to be globally unique across the gkmlpt system (no collisions observed across Shenzhen's 20 sites).
- Rate limiting has not been an issue at 0.5s delays, but Guangzhou (much larger site) may require slower crawling.
