# LLM Document Classification Pipeline

*Designed 2026-03-17, IMPLEMENTED 2026-03-24. Uses DeepSeek V3.2 API to enrich documents with English metadata. 110k+ docs classified (~$35 total). Script: `scripts/classify_documents.py`, sync: `scripts/sync_classifications.py`.*

## Goal

Add to every document: English title, English summary, category, topic tags, importance ranking. This lets analysts filter out ~35-40% noise (personnel notices, procurement, leader visits) and navigate the remaining 60k+ substantive documents by topic and importance.

## Approach: DeepSeek API

- **Model:** DeepSeek V3.2 (`deepseek-chat`), OpenAI-compatible API
- **Cost:** ~$34 one-time ($0.28/M input, $1.10/M output)
- **Speed:** 10-20 concurrent requests, ~2-4 hours total
- **Script:** Adapt existing `scripts/classify_documents.py` (currently Ollama-only)

### Why DeepSeek over local Qwen
- Local Qwen2.5:14b: 23s/doc = **28 days** for 103k docs
- DeepSeek API: ~$34, ~3 hours, better Chinese quality

---

## Schema: Columns on `documents` table

No separate table — 1:1 relationship, just add columns:

| Column | Type | Description |
|--------|------|-------------|
| `title_en` | TEXT | Already exists. English title translation |
| `summary_en` | TEXT | 1-2 sentence English summary |
| `category` | TEXT | One of 9 categories (see below) |
| `importance` | TEXT | high / medium / low |
| `policy_area` | TEXT | Chinese topic label (e.g., "人工智能") |
| `topics` | TEXT | JSON array of English topic tags |
| `classification_model` | TEXT | Which model classified it |
| `classified_at` | TEXT | ISO timestamp |

### Categories
- `major_policy`: Action plans, development plans, implementation opinions (行动方案, 发展规划, 实施意见)
- `regulation`: Laws and regulations (法规规章)
- `normative`: Management rules, implementation details (管理办法, 实施细则)
- `budget`: Fiscal budgets and final accounts (财政预决算)
- `personnel`: Appointment/removal notices (人事任免)
- `administrative`: Routine notices, meeting arrangements (会议通知, 工作安排)
- `report`: Work reports, statistics, briefings (工作报告, 统计数据)
- `subsidy`: Funding, subsidies, support policies (资金补贴, 扶持政策)
- `other`: Everything else

---

## Importance Rubric

This is the most critical field — it determines what analysts see first.

### HIGH — Flag for analyst attention
- New policy frameworks, action plans, development plans
  - "国务院办公厅关于上市公司独立董事制度改革的意见"
  - "深圳市人民政府办公厅关于印发深圳市扶持个体工商户高质量发展若干措施的通知"
- Major regulatory changes (provincial+ level 实施意见)
  - "关于加快发展我省服务业的实施意见"
- Large funding allocations, subsidy programs, government guidance funds
- Industry standards with broad economic impact
- State Council opinions, central ministry directives

### MEDIUM — Useful context
- Implementation notices relaying higher-level policy (转发...的通知)
  - "汕尾市人民政府转发广东省人民政府关于印发...实施意见的通知"
- District/department regulatory details (管理办法, 实施细则)
  - "深圳市行政决策责任追究办法"
- Budget/fiscal reports
  - "2022年度深圳市人民政府办公厅部门决算"
- Normative documents with limited scope
- Spatial planning approvals (规划批复)

### LOW — Routine/procedural, minimal analytical value
- Personnel appointments/removals
  - "揭阳市人民政府关于陈洁珊同志任职的通知"
- Meeting notices, work conferences
  - "市安委办召开全市安全生产治本攻坚三年行动信息系统业务培训工作会议"
- Procurement/bidding notices
  - "深圳市人力资源和社会保障局内部招标结果公示"
- News about leader activities
  - "温湛滨调研新冠疫苗接种工作"
- Public notices (license transfers, traffic diversions)
  - "深圳市出租汽车营运牌照转让登记公告"

### Expected distribution
- ~35-40% LOW (based on CMS categories: 工作动态 17.9k, 政务动态 10.9k, 招标采购 2.6k, 人事信息 957, etc.)
- ~40-45% MEDIUM (通知公告 13.9k, 其他文件 10.9k, 财政预决算 3.3k, 规范性文件 8.9k)
- ~10-15% HIGH (政策文件 1k, key 规范性文件, major reforms, State Council opinions)

---

## Prompt

```
You are classifying Chinese government documents for a Western analyst research database.
Given the document below, output a JSON object with these fields:

- title_en: English translation of the title (concise, formal government style)
- summary_en: 1-2 sentence English summary of what this document does or requires
- category: one of [major_policy, regulation, normative, budget, personnel, administrative, report, subsidy, other]
- topics: array of 1-3 English topic tags (e.g. "artificial intelligence", "housing", "environmental protection")
- importance: one of [high, medium, low] — see detailed rubric below
- policy_area: short Chinese topic label (e.g. "人工智能", "住房保障", "环境保护")

## Importance rubric:

HIGH — Documents a Western policy analyst would flag as significant:
  - New policy frameworks, action plans, development plans
  - Major regulatory changes (provincial+ level)
  - Large funding allocations, subsidy programs
  - Industry standards with broad economic impact
  - State Council opinions or central ministry directives

MEDIUM — Useful context but not headline-worthy:
  - Implementation notices relaying higher-level policy
  - District/department regulatory details
  - Budget and fiscal reports
  - Normative documents with limited scope
  - Spatial planning approvals

LOW — Routine or procedural:
  - Personnel appointments/removals
  - Meeting notices, work conferences
  - Procurement/bidding notices
  - News about leader activities
  - Public notices (license transfers, traffic diversions, name lists)

Document title: {title}
Document number: {doc_number}
Publisher: {publisher}
CMS category (if available): {classify_main_name}
Body excerpt (Chinese): {body_excerpt}

Output ONLY valid JSON, no explanation.
```

Prompt is in English (DeepSeek handles mixed EN/CN well). Body excerpt stays Chinese (first 1500 chars). `classify_main_name` is included as context for the ~83k gkmlpt docs that have it.

---

## Implementation steps

1. **Add DeepSeek backend** to `scripts/classify_documents.py`
   - Use `openai` Python SDK with `base_url="https://api.deepseek.com/v1"`
   - Auth via `DEEPSEEK_API_KEY` env var
   - Add `--backend deepseek|ollama` flag
2. **Expand prompt and output fields** (title_en, summary_en, topics added)
3. **Add async batching** — 10-20 concurrent requests via `concurrent.futures`
4. **Add new columns** to SQLite schema (ALTER TABLE) and Postgres schema in `sqlite_to_postgres.py`
5. **Run classification**: dry-run → single site → full run
6. **Sync to Postgres** via `--drop` migration

### Run commands
```bash
export DEEPSEEK_API_KEY="sk-..."

# Test
python3 scripts/classify_documents.py --backend deepseek --dry-run --limit 10

# Validate on one site
python3 scripts/classify_documents.py --backend deepseek --site sz --limit 100

# Full run (resumable)
python3 scripts/classify_documents.py --backend deepseek

# Sync to production
DATABASE_URL="postgresql://..." python3 scripts/sqlite_to_postgres.py --drop
```

---

## Web app integration (follow-up)

After classification:
- Browse page: filter by category, importance
- Document detail: show English title, summary, topics, importance badge
- Search: return English titles alongside Chinese
- API: include classification fields in JSON responses
