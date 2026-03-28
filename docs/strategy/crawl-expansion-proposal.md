# Crawl Expansion Proposal: AI, Technology & the Political-Economic Complex

**Goal:** Build a corpus that captures how China's governance system is navigating AI and technological revolution — from top-level directives to local implementation, from state policy to private sector response, from industrial ambition to social consequences.

## Current Corpus Snapshot (March 2026)

| Layer | Docs | Coverage |
|-------|------|----------|
| Central government (State Council, NDRC, MOF, MEE) | 4,104 | Good for general policy; weak on AI-specific |
| Provincial (Guangdong, Beijing, Shanghai, Jiangsu) | 12,821 | Good |
| Municipal (Shenzhen + 16 Guangdong cities) | 37,787 | Deep |
| District/Department (Shenzhen) | 57,141 | Deep |
| Media (LatePost via 163.com) | 85 | Nascent |
| **Total** | **111,938** | |

**Topic counts in existing corpus:**
- AI/人工智能: 236 docs
- Pensions/养老: 696 docs
- Robotics/机器人: 141 docs
- Data/数据: 1,852 docs
- Semiconductors/芯片+半导体: 56 docs

The corpus is deep on Guangdong/Shenzhen administrative documents but thin on:
1. **Central AI-specific policy** (MIIT, CAC, MOST are missing)
2. **Industry/startup news** (only 85 LatePost articles)
3. **Social policy commentary** (think tanks, academic policy analysis)
4. **Other tech-forward provinces** (Zhejiang, Anhui/Hefei conspicuously absent)

---

## Proposed Expansion: Three Tiers

### Tier 1: High Priority — Fill Critical Gaps

These are the most important missing pieces for understanding the AI governance landscape.

#### 1A. Ministry of Industry and Information Technology (MIIT / 工信部)
**Why:** MIIT is the primary regulator for AI industry, semiconductors, robotics, and digital infrastructure. Without it, we're missing the most important central ministry for tech policy.
- URL: `www.miit.gov.cn`
- Sections: policy documents (政策文件), industry guidance (产业指导), standards (标准)
- Expected: 500-2,000 docs
- Difficulty: Medium (standard government site, likely server-rendered)

#### 1B. Cyberspace Administration of China (CAC / 国家互联网信息办公室)
**Why:** CAC regulates AI models, algorithmic recommendations, deepfakes, and data governance. Issued the landmark "Interim Measures for Generative AI" and subsequent regulations.
- URL: `www.cac.gov.cn`
- Sections: policies (政策法规), announcements (通知公告)
- Expected: 300-800 docs
- Difficulty: Low-Medium

#### 1C. Ministry of Science and Technology (MOST / 科技部)
**Why:** MOST drives AI R&D policy, national labs, talent programs, and the "New Generation AI Development Plan."
- URL: `www.most.gov.cn`
- Sections: policy documents, S&T plans
- Expected: 500-1,500 docs
- Difficulty: Medium

#### 1D. 36Kr (36氪)
**Why:** China's leading tech/startup media. Covers AI funding rounds, product launches, company strategies, and industry analysis. Complements LatePost's deeper-dive journalism with broader daily coverage.
- URL: `36kr.com`
- Sections: AI/tech articles
- Difficulty: Medium-High (likely JS-rendered listing, but articles may have og: tags)
- Note: Consider their RSS feed or API if available

### Tier 2: Important — Broaden Geographic & Thematic Coverage

#### 2A. Zhejiang Province (浙江省)
**Why:** Home to Alibaba, Hangzhou's AI cluster, and aggressive "Digital Zhejiang" policies. One of the most tech-forward provincial governments.
- URL: `www.zj.gov.cn`
- Expected: 2,000-5,000 docs
- Difficulty: Medium (may use different CMS than Guangdong's gkmlpt)

#### 2B. Anhui Province / Hefei (安徽省 / 合肥市)
**Why:** Hefei is emerging as China's AI hardware capital (iFlytek, NIO). Provincial government has made massive AI bets with public capital.
- URLs: `www.ah.gov.cn`, `www.hefei.gov.cn`
- Expected: 1,000-3,000 docs each
- Difficulty: Medium

#### 2C. Caixin (财新)
**Why:** China's most rigorous financial/economic journalism. Covers the intersection of policy, markets, and technology with depth unmatched by other outlets.
- URL: `www.caixin.com`
- Difficulty: **High** — behind paywall. May only be able to crawl free headlines/summaries.
- Alternative: Crawl the free Caixin Global (english.caixin.com) for English-language coverage.

#### 2D. Phoenix News Commentary (凤凰网评论 / 风声)
**Why:** Policy commentary by researchers and intellectuals — the analytical layer between raw government documents and news reporting. Covers social policy (pensions, rural development) that intersects with the tech transformation story. This is where the ifeng.com rural pensions article lives.
- URL: `news.ifeng.com` (风声 column specifically)
- Difficulty: Medium (server-rendered article pages)

#### 2E. National People's Congress / NPCSC (全国人大)
**Why:** Legislative body that passes the actual laws (vs. State Council regulations). Key for AI governance: the upcoming AI Law, Data Security Law amendments, PIPL enforcement.
- URL: `www.npc.gov.cn`
- Expected: 500-1,000 legislative docs
- Difficulty: Low-Medium

### Tier 3: Nice to Have — Specialized Sources

#### 3A. China Academy of Information and Communications Technology (CAICT / 信通院)
**Why:** MIIT's think tank. Publishes influential white papers on AI, 5G, cloud computing, data governance.
- URL: `www.caict.ac.cn`
- Difficulty: Medium (reports often behind registration; titles/abstracts may be accessible)

#### 3B. State-owned Assets Supervision and Administration Commission (SASAC / 国资委)
**Why:** Governs SOEs' AI investments and digital transformation mandates. SOEs are major AI adopters.
- URL: `www.sasac.gov.cn`
- Expected: 500-1,000 docs
- Difficulty: Low-Medium

#### 3C. Development Research Center of the State Council (DRC / 国务院发展研究中心)
**Why:** The State Council's own policy think tank. Research that directly informs top-level decisions.
- URL: `www.drc.gov.cn`
- Expected: 300-800 docs
- Difficulty: Low-Medium

#### 3D. Yicai / CBN (第一财经)
**Why:** Financial news with strong tech coverage. More market-oriented than Caixin, more accessible.
- URL: `www.yicai.com`
- Difficulty: Medium

---

## Recommended Implementation Order

**Phase 1 (immediate):** MIIT, CAC, MOST — three missing central ministries essential for AI governance coverage. Standard government sites; use existing `mee.py` / `mof.py` patterns.

**Phase 2 (next sprint):** 36Kr, Phoenix/风声 — media sources for the private sector and intellectual commentary layers. Build on the LatePost crawler pattern.

**Phase 3 (following):** Zhejiang, Anhui/Hefei — geographic expansion to other major AI provinces. Assess whether their sites use gkmlpt or need custom crawlers.

**Phase 4 (as needed):** NPC, CAICT, SASAC, DRC — specialized sources for legislative, think tank, and SOE perspectives.

---

## Architecture Considerations

### Source Type Separation
The `admin_level` field in the `sites` table already supports separation:
- `central`, `provincial`, `municipal`, `district`, `department` — government documents
- `media` — news articles (LatePost, and future media sources)
- Consider adding: `think_tank` for CAICT/DRC, `legislative` for NPC

### Linking Media to Policy
The eventual goal is cross-referencing: when LatePost writes about 国发〔2025〕11号 (the AI+ action plan), that article should link to the actual document in the corpus. Two approaches:
1. **Citation extraction** — run the existing `REF_PATTERN` regex on media articles to find document number references
2. **Semantic linking** — use embeddings or keyword overlap to suggest related government documents for each media article

### Volume Management
Current corpus: ~112k docs, ~1GB SQLite. Adding the proposed sources could reach 150-200k. SQLite handles this fine; Postgres production sync will take longer but remains viable.

---

## The Bigger Picture

The corpus should capture five dimensions of how China navigates the AI revolution:

1. **What the state directs** — official policy documents, laws, regulations, plans (government crawlers)
2. **What the state implements** — budget allocations, project approvals, personnel appointments (already strong in Shenzhen)
3. **What industry builds** — startup activity, investment, product launches, corporate strategy (media crawlers)
4. **What intellectuals argue** — policy commentary, think tank reports, academic analysis (Phoenix/风声, CAICT, DRC)
5. **What happens to people** — social consequences: rural pensions, labor displacement, inequality, the gap between industrial ambition and lived reality (commentary + social policy docs)

The AI revolution is not just a technology story. It's a governance story: how does a system that actively directs industrial policy, manages social stability, and competes geopolitically handle a transformation that affects all three simultaneously? The corpus should reflect all these tensions.
