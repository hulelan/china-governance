# Investment & Economic Data Expansion

*Created 2026-03-24. Expand corpus beyond policy documents to include investment intelligence, economic statistics, and promotional content from government portals.*

## Motivation

The current corpus covers **regulatory/policy documents** from gkmlpt platforms and ministry sites. But government portals also publish investment-relevant content outside the policy CMS:

- **Investment news** (投资动态): FDI trends, project announcements, business environment updates
- **Economic statistics** (统计数据): GDP, trade, industrial output, employment data
- **Investment guides** (投资指南): Sector policies, incentive programs, special economic zone rules
- **Business environment** (营商环境): Regulatory reform, approval process improvements

Example: [sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/](https://www.sz.gov.cn/cn/zjsz/fwts_1_3/tzdt_1/) — Shenzhen's investment news section, separate from the gkmlpt policy platform.

## Target Sources

### Shenzhen (sz.gov.cn)
| Section | URL Pattern | Content |
|---------|-------------|---------|
| 投资动态 (Investment News) | `/cn/zjsz/fwts_1_3/tzdt_1/` | FDI news, project signings, investment events |
| 统计数据 (Statistics) | `/cn/zjsz/fwts_1_3/tjsj/` | Economic data releases |
| 投资指南 (Investment Guide) | `/cn/zjsz/fwts_1_3/tzzn/` | Sector guides, incentive summaries |
| 营商环境 (Business Env) | `/cn/zjsz/yshj/` | Regulatory reform updates |

### Other Cities (if similar sections exist)
- Guangzhou, Zhuhai, Dongguan — likely have similar investment portals
- Provincial level (gd.gov.cn) — Guangdong investment promotion content

### National
- MOFCOM (商务部) — national FDI statistics, trade data
- NBS (国家统计局) — GDP, CPI, industrial production

## Technical Approach

These pages are NOT on the gkmlpt platform — they use different CMS structures. Each source needs:

1. **Probe the page structure** — fetch HTML, identify list/pagination patterns
2. **Write a custom crawler** — similar to `crawlers/mof.py` pattern
3. **Store in documents.db** — same schema, new `site_key` (e.g., `sz_invest`)
4. **Classify with DeepSeek** — will get tagged as `report` or `other` with investment-related topics

### Key differences from gkmlpt crawling:
- No standard API — must scrape HTML directly
- Pagination varies by site (some use `?page=2`, some use `/page/2/`)
- Content is more news/editorial than formal policy — mostly LOW importance but HIGH value for investment intelligence
- May include embedded data tables, charts, PDFs

## Suggested site_keys

| site_key | Source | Content Type |
|----------|--------|-------------|
| `sz_invest` | Shenzhen investment portal | Investment news, guides |
| `sz_stats` | Shenzhen statistics bureau | Economic data |
| `gd_invest` | Guangdong investment portal | Provincial investment news |
| `mofcom` | Ministry of Commerce | National FDI, trade |
| `nbs` | National Bureau of Statistics | Macro data releases |

## Priority

**Tier 1 (do first):** Shenzhen investment portal — we know the URL structure, it's the deepest city in our corpus

**Tier 2:** Guangdong provincial investment content, other major cities

**Tier 3:** MOFCOM, NBS — national-level economic data

## Open Questions

- Should investment/news content be in the same `documents` table, or a separate table with different schema?
- How to handle data tables embedded in pages — extract as structured data or just raw text?
- Frequency: these are news articles, so new ones appear daily. Should we set up recurring crawls?
