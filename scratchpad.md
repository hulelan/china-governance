# Scratchpad & Log

Working log of everything attempted, results, and decisions made.

---

## Session Log

### 2026-02-14 — Project Setup

- Initialized git repo, pushed to `https://github.com/hulelan/china-governance.git`
- Read `conversation.md` and `spec.md` — prior research from an earlier session
- Synthesized execution plan into `plan.md`

#### Key context inherited from prior session (conversation.md):
- SSL/HTTPS fails across all Shenzhen gov sites (BAD_ECPOINT) — HTTP works
- gkmlpt platform is the primary crawl target — standardized across departments/districts
- gkmlpt index pages are Vue.js SPAs (no data in HTML), content pages are server-rendered
- Metadata table has 8 standardized fields across all gkmlpt sites
- ~48 Shenzhen gov sites identified (~17 confirmed, ~20 inferred)
- gkmlpt confirmed as Guangdong province-wide standard (also on Guangzhou Conghua district)
- Existing related projects: UCSD China Policy Navigator, Cambridge missingness paper, CAPC-CG corpus

#### What hasn't been tried yet:
- [ ] Playwright API discovery on gkmlpt index pages
- [ ] Verifying inferred subdomains
- [ ] Fetching main portal mpost_ pages
- [ ] Sampling attachment prevalence
- [ ] Any actual crawling code
- [ ] Any LLM prompt design
- [ ] Database schema design

---

## Experiments & Results

*(Will be populated as we work through Goal 1 and beyond)*

### Template for logging experiments:

```
#### [DATE] — [EXPERIMENT NAME]
**What:** [What we tried]
**Why:** [What question this answers]
**How:** [Command/script/approach used]
**Result:** [What happened]
**Conclusion:** [What we decided based on this]
**Next:** [What this unblocks or what to try next]
```

---

## Open Questions

1. What is the gkmlpt JSON API endpoint structure? (Goal 1, Task 1 — GATING)
2. Full verified subdomain list? (Goal 1, Task 2)
3. Does main portal metadata match gkmlpt format? (Goal 1, Task 3)
4. What % of documents are PDF/DOC attachments? (Goal 1, Task 4)
5. Rate limiting behavior? (empirical — test during Goal 2)
6. 文号 format patterns for cross-referencing? (test during Goal 3)
7. LLM cost estimate at MVP scale? (test during Goal 5)

---

## Resolved Questions

*(Moved here from Open Questions as they get answered)*

- **SSL access:** HTTP works, HTTPS fails. Use HTTP. (from prior session)
- **JS rendering for content pages:** Not needed — server-rendered HTML. (from prior session)
- **Legal risk:** Minimal — public disclosure mandate, polite crawling. (from prior session)
- **gkmlpt scope:** Province-wide Guangdong standard, not Shenzhen-specific. (from prior session)

---

## Useful References

- Example gkmlpt content page: `http://www.szpsq.gov.cn/gkmlpt/content/9/9103/post_9103540.html`
- Example gkmlpt index page: `http://www.szpsq.gov.cn/psozhzx/gkmlpt/index`
- Example main portal content: `https://www.sz.gov.cn/cn/xxgk/zfxxgj/sldzc/szfld/lwp/jqhd/content/mpost_12193340.html`
- UCSD Navigator: `https://portals.igcc.sdsc.edu`
- Shenzhen Open Data: `https://opendata.sz.gov.cn`
