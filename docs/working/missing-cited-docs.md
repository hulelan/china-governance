# Missing cited documents — crawl wishlist (snapshot 2026-07-05)

Documents that our corpus **cites but doesn't contain** — i.e. rows in the
`citations` table with `target_id IS NULL`. Ranked by how often they're cited, this
is a data-driven priority list for crawl expansion: the most-referenced documents
we're missing.

Regenerate anytime with the SQL at the bottom (run against `documents.db`).

## Scale of the gap

| Citation type | Total | Resolved (we have it) | **Dangling (missing)** |
|---|---|---|---|
| formal (文号) | 69,471 | 13,450 | **56,021** (81%) |
| named (《》)   | 167,826 | 67,367 | **100,459** (60%) |
| llm           | 15,109 | 8,541 | **6,568** (43%) |

~163k dangling references overall. Note the *resolved* rate is the more honest
"how connected is our corpus" metric — formal refs resolve only 19% of the time,
so most 文号 citations point outside what we hold.

## Missing formal (文号) docs, by issuing agency

| Agency | Distinct missing docs | Total refs to them |
|---|---|---|
| State Council (国发/国办) | 1,563 | **5,550** ← highest leverage (few docs, many refs) |
| Guangdong (粤) | 4,459 | 7,149 |
| Shenzhen (深) | 2,998 | 4,747 |
| Suzhou/Jiangsu (苏) | 3,362 | 4,256 |
| MOF (财) | 1,058 | 1,793 |
| MIIT (工信部) | 56 | 170 |
| other | 26,433 | 32,356 |

**Takeaway:** the ~1,563 missing State Council docs are the best ROI — a small set
cited 5,550 times. Guangdong provincial planning/land regs are the biggest *thematic*
gap (they underpin the whole Shenzhen/GD municipal corpus).

## Top named-title (《》) gaps — the readable wishlist

Most-cited policy titles we don't have (count × title):

- 957 × 广东省城乡规划条例  (GD Urban-Rural Planning Regulation)
- 915 × 城市、镇控制性详细规划编制审批办法
- 513 × 惠州市加强建设项目征地拆迁管理规定
- 371 × 建设用地容积率管理办法
- 340 × 广东省控制性详细规划管理条例
- **313 × 粤港澳大湾区发展规划纲要  (Greater Bay Area Development Plan — major central doc)**
- 287 × 广东省自然资源厅…加强和改进控制性详细规划管理…指导意见
- 268 × 广东省征地补偿保护标准
- 246 × 深圳市科技计划项目管理办法
- 224 × 广东省事业单位公开招聘人员体检实施细则（试行）
- 206 × 关于进一步优化新冠肺炎疫情防控措施…的通知
- 191 × 中山市人民政府办公室…加强城市总体规划实施管理的通知
- 165 × 深圳市财政局政府采购供应商信用信息管理办法
- 165 × 新型冠状病毒肺炎防控方案（第九版）
- 98  × 国家中长期科学和技术发展规划纲要（2006-2020年）

Dominant themes: **Guangdong urban planning & land management** (控制性详细规划,
征地拆迁, 城乡规划), COVID-era health directives, and a few flagship central plans.

## Top formal (文号) gaps

- 240 × 粤自然资发〔2021〕3号   ·  188 × 中府办〔2013〕41号  ·  170 × 粤国土资利用发〔2011〕21号
- 138 × 粤国土资发〔2006〕149号 ·  126 × 苏住建规〔2011〕4号   ·  107 × 苏住建规〔2012〕8号
- 104 × 深财规〔2023〕3号       ·  100 × 粤国土资规字〔2016〕1号 ·  78 × 财库〔2022〕4号
- 78  × 工信部联企业〔2011〕300号 ·  47 × 国发〔2004〕20号     ·  45 × 国发〔2010〕33号
- (see full query for the long tail — ~40k distinct)

> Data-quality note: some formal `target_ref`s carry extraction noise (leading
> "按照…" / "根据…" prefixes merged into the 文号 by the greedy regex), so the same
> doc can appear twice (e.g. "苏住建规〔2011〕4号" vs "按照…苏住建规〔2011〕4号").
> Worth a cleanup pass on `REF_PATTERN` / the `target_ref` normalization.

## Knowledge-management options (pick one)

1. **This doc** — a regenerable markdown snapshot (simplest; you're reading it).
2. **A live `/gaps` page on the site** ⭐ recommended — the data already lives in the
   `citations` table (`target_id IS NULL`, grouped by `target_ref`). A page could rank
   the most-cited missing docs live, always current, and double as the crawl backlog.
   Turns an invisible gap into a visible feature.
3. **Feed the top missing 文号 into targeted crawling** — resolve high-value gaps
   (State Council first) by fetching those specific documents.

## Regenerate

```sql
-- resolved vs dangling by type
SELECT citation_type, COUNT(*) total,
       SUM(target_id IS NOT NULL) resolved,
       SUM(target_id IS NULL) dangling
FROM citations GROUP BY citation_type;

-- top missing named titles
SELECT COUNT(*) c, target_ref FROM citations
WHERE target_id IS NULL AND citation_type='named' AND LENGTH(target_ref) BETWEEN 8 AND 40
GROUP BY target_ref ORDER BY c DESC LIMIT 50;

-- top missing formal 文号
SELECT COUNT(*) c, target_ref FROM citations
WHERE target_id IS NULL AND citation_type='formal'
GROUP BY target_ref ORDER BY c DESC LIMIT 50;
```
