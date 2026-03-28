# Research Views — Roadmap

## What We Built (March 2026)

### Inbox / Calendar View (`/inbox`)
Date-grouped document feed showing what was published each day. Documents are
grouped by `date_written` into buckets (Today, Yesterday, and raw dates).

- Sidebar filters: site dropdown, admin level dropdown
- First 7 dates pre-loaded server-side; older dates lazy-loaded via
  `/api/v1/inbox?date=<timestamp>` on expand
- Alpine.js expand/collapse for each date group

### Date Range Filtering
Added `date_start` / `date_end` query params to three existing views:

| View | What changed |
|------|-------------|
| `/browse` | Date picker inputs in filter sidebar; date range takes precedence over year dropdown |
| `/search` | Date picker inputs below search box; pagination preserves date filters |
| `/network` | Date pickers in Alpine.js filter panel; network API filters by `date_written` range |

All date filtering uses `date_str_to_timestamp()` which converts `YYYY-MM-DD`
to Unix timestamp at midnight CST (UTC+8) — matching how `date_written` is
stored in the database.

### Doc-to-Network Entry Point (`/document/{id}`)
Mini D3.js force-directed graph on the document detail page showing the 1-hop
citation neighborhood:

- Center node (current document) highlighted with amber border
- Forward references: documents this one cites
- Reverse references: documents that cite this one
- Directed edges with arrow markers
- Click a neighbor node to navigate to that document
- Zoom and drag supported
- API: `/api/v1/documents/{id}/network`

### Service Layer Changes
- `web/services/documents.py`: `date_str_to_timestamp()`, date range params on
  `get_documents()` and `search_documents()`, new `get_citation_neighborhood()`
- `web/services/inbox.py`: new file with `get_inbox_dates()` and
  `get_documents_for_date()`

---

## Future Features (Not Yet Built)

### Topic Clusters in Network
Auto-detect policy topic clusters within the citation network graph.
Click a cluster to explore related documents. Could use community detection
algorithms (e.g. Louvain) on the citation graph, or keyword-based clustering
on document titles/bodies.

### AI-Powered Topic Classification
Use LLMs to classify documents into policy themes beyond what the source
metadata provides. Build a taxonomy of Chinese governance topics (e.g. AI
regulation, land use, fiscal policy, environmental protection) and tag
each document. Enable cross-topic analysis.

### Cross-City Comparison
Compare how different cities approach the same policy area. For example:
Shenzhen vs. Guangzhou vs. Shanghai on AI governance. Show side-by-side
timelines, document counts, and key policy differences. Requires expanding
the crawler to more cities first.

### Policy "Vibe" Analysis
Characterize each city's governance personality through the documents they
produce. One city might focus on AI applications while another emphasizes
regulation. Extract signal from document titles, categories, and body text
to build per-city profiles.

### Signal Extraction Pipeline
Systematically extract structured metadata from document body text:
- Referenced laws and regulations (already done via citation extraction)
- Monetary amounts and budgets mentioned
- Deadlines and implementation dates
- Responsible departments and contact information
- Policy targets and KPIs

### Geographic Expansion
Current coverage: 37+ sites spanning Guangdong province and central government.

**Already done:**
- 23 original Shenzhen sites (municipal government + departments + districts)
- 3 additional Shenzhen districts (Yantian, Longgang, Dapeng)
- Guangdong Province portal
- 16 other Guangdong cities added: Guangzhou, Zhuhai, Huizhou, Jiangmen,
  Zhongshan, Shantou, Shaoguan, Heyuan, Shanwei, Yangjiang, Zhanjiang,
  Chaozhou, Jieyang, Yunfu (Dongguan and Foshan configured but currently
  unreachable)
- Central government: NDRC, State Council, MOF, MEE

**Key finding:** gkmlpt is confirmed Guangdong-only. A probe of 28 other
provincial portals found zero that use gkmlpt. Other provinces will need
custom crawlers or a different scraping approach.

**Remaining expansion targets:**
- Other major provinces (Zhejiang, Jiangsu, Shanghai, Beijing) — requires
  building province-specific crawlers since gkmlpt does not apply
- National ministries beyond NDRC, State Council, MOF, MEE
- Estimated total: currently at ~5% of Chinese government web presence

### Full Government Mapping
Build a comprehensive directory of all Chinese government websites that
publish policy documents. Map the administrative hierarchy from central
government down to district level. The gkmlpt platform is now confirmed
as Guangdong-only (28 provinces probed, 0 matches), so province-by-province
crawler work is required outside Guangdong.

### Enhanced Network UX
- Search within network (highlight matching nodes)
- Time-lapse mode (animate network growth over time)
- Export subgraph as image or data
- Cluster coloring by topic
- Edge weight by citation frequency
