# QA: the nightly classifier's silent one-third failure rate

Date: 2026-10-07. Read-only diagnosis. No writes to `documents.db`, no code changed.
The nightly `daily_sync.sh` was mid-Phase-2 throughout (lock held, classifier
running); every DB access below used `file:documents.db?mode=ro` under `nice -n 19`.

**Verdict (measured).** The failures are not a document property and not rate
limiting. `deepseek-v4-flash` is a reasoning model and the request sets
`max_tokens=2000`. Reasoning tokens are billed against that same budget, so on a
large fraction of documents the model spends the entire 2,000 tokens thinking and
returns `finish_reason="length"` with **zero content**. `classify_deepseek` treats
empty content as "likely content filter. Skip silently." and returns `None`.

---

## 1. What increments `err`, and what is logged

`scripts/classify_documents.py`. The counter is literally "the classify function
returned a falsy value":

```python
result = future.result()
if result:
    save_result(conn, doc["id"], result, args.model)
    success += 1
else:
    errors += 1          # line 418 — no reason captured, no log line
```

`classify_deepseek` returns `None` on five distinct paths, and **three of them
print nothing at all**:

| path | line | logged? |
|---|---|---|
| `raw` is empty after `.strip()` | 155 | **silent** (comment: "likely content filter. Skip silently.") |
| `"Content Exists Risk" in err_str` | 166 | **silent** |
| `_parse_response` cannot salvage JSON | 234 | **silent** (returns `None`, caller cannot distinguish) |
| any other exception | 168 | `[warn] DeepSeek error for doc N:` |
| 3 rate-limit retries exhausted | 170 | `[fail] doc N: exhausted retries` |

**Measured:** across all twelve `logs/daily-2026100*-0600.log` and the September
runs on the droplet, `grep -hoE "\[(warn|fail|rate-limit)\]"` returns **zero
lines**. Every one of the thousands of failures took a silent path. The `err`
column in the progress line is the only surviving evidence.

**What happens to the document afterwards:** nothing. `save_result` is the only
writer and it is skipped, so `classified_at` stays `''`. The next night's query
(`WHERE classified_at IS NULL OR classified_at = ''`) picks the document up again.
There is no attempt counter, no failure-reason column and no dead-letter table.
A document that fails is retried every night forever at full API cost.

---

## 2. The premise's "jump between 10-01 and 10-03" is an artifact

The 10-01 and 10-07 rows in the brief are mid-run *progress* lines, not finals.
Taking the `Done:` line from every daily log on the droplet:

```sql
-- not SQL; the droplet equivalent
-- grep -h "^Done: .*classified" logs/daily-2026*-0600.log
```

| run | classified / pool | errors | err rate |
|---|---|---|---|
| mid-Sep (9 consecutive runs) | 725–1,178 of 991–1,593 | 196–415 | **24–27%** |
| 10-01 | 2,699 / 3,030 | 331 | 10.9% |
| 10-02 | 1,023 / 1,388 | 365 | 26.3% |
| 10-03 | 416 / 662 | 246 | 37.2% |
| 10-04 | 311 / 488 | 177 | 36.3% |
| 10-05 | 277 / 424 | 147 | 34.7% |
| 10-06 | 237 / 361 | 124 | 34.3% |
| 10-07 (mid-run) | 992 / 2,669 | 208 | 17.3% |

**Inferred:** nothing changed in early October. The rate has sat in a noisy
20–37% band since at least mid-September. The migration that introduced the
reasoning model (`267e5b2`, `max_tokens` 500 → 2000, `deepseek-chat` retired)
landed **2026-07-25**, so the condition is three months old. The apparent jump is
small-pool noise: the error rate is higher when the pool is mostly *carried-over
prior failures* (10-03 to 10-06 pools are ~40% retries) and lower when a big
crawl floods the pool with fresh documents (10-01, 10-07).

---

## 3. Document properties do not discriminate (prime suspect eliminated)

Context-length overflow is impossible by construction. `_build_prompt` line 204:

```python
body_excerpt = doc["body_text_cn"][:1500] if doc["body_text_cn"] else "(无正文)"
```

The body is hard-truncated to 1,500 characters, so the prompt is a near-constant
~4.3–5.3 KB regardless of document size. Measured prompt tokens across the probe:
**1,226–1,922**, a 1.6x spread on a 128k-token context.

Cohorts, read-only. "Failed a prior night" = still unclassified and crawled before
today, i.e. it was in last night's pool and lost:

```sql
SELECT COUNT(*), CAST(AVG(LENGTH(body_text_cn)) AS INT), MAX(LENGTH(body_text_cn))
FROM documents
WHERE (classified_at IS NULL OR classified_at = '')
  AND substr(crawl_timestamp,1,10) < date('now');     -- failures

SELECT COUNT(*), CAST(AVG(LENGTH(body_text_cn)) AS INT), MAX(LENGTH(body_text_cn))
FROM documents WHERE classified_at >= date('now','-3 day');   -- successes
```

| cohort | n | empty body | avg body chars | max | >20k chars |
|---|---|---|---|---|---|
| failed a prior night | 111 | 0 | **1,723** | 6,944 | 0 |
| classified in last 3 days | 1,630 | 115 | **1,745** | 25,228 | 1 |

Body length is identical to within 1.3%. The single longest document in the corpus
cohort (25,228 chars) **succeeded**. There is no length signal.

Site distribution is equally flat — the 111 failures are spread across ~70 sites
at 2–7 each (`isc` 7, `cass` 6, `shb_tjj` 6, `csrc` 5, `miit` 5), and the sites
with the most *successes* (`guancha` 116, `jcgov` 110) also appear in the failure
list. No site, genre or script concentration.

The decisive negative result is the **churn**: ~200 documents fail every night, so
~6,000 failures have accumulated over the past month, yet only **111** are still
unclassified and only **50** are older than a week:

```sql
SELECT COUNT(*) FROM documents
WHERE (classified_at IS NULL OR classified_at = '')
  AND substr(crawl_timestamp,1,10) < date('now','-7 day');   -- 50
```

A document that fails tonight usually succeeds on a later night with the same
prompt. That rules out every document property and points at a **stochastic,
per-request** cause.

---

## 4. Live probe: the mechanism, measured

Bounded probe, concurrency 1, 20 documents, `max_retries=0`, **no DB writes**
(a standalone script in `/tmp`, since `--dry-run` only changes the *save* path and
would not have exposed `usage`). Stratified: 10 that failed a prior night, 10 that
were classified successfully within the last 2 days (control). Key: droplet `.env`.

| cohort | n | `finish_reason="length"`, 0 content | `Content Exists Risk` 400 | parseable JSON |
|---|---|---|---|---|
| failed a prior night | 10 | 9 | 1 | **0** |
| classified OK recently | 10 | 9 (1 with truncated content) | 0 | **1** |

Representative response (truncated; the pattern is identical for all 19):

```json
{"id": 900132341, "prompt_chars": 4287,
 "exception": "BadRequestError",
 "msg": "Error code: 400 - {'error': {'message': 'Content Exists Risk ...'}}"}

{"id": 900135414, "prompt_chars": 5290, "finish_reason": "length",
 "content_len": 0, "prompt_tokens": 1679,
 "completion_tokens": 2000, "reasoning_tokens": 2000, "head": ""}
```

**`reasoning_tokens == completion_tokens == 2000` on every "length" response.**
The entire output budget went to reasoning; zero tokens were left for the JSON.
The one success used `completion_tokens: 1354, reasoning_tokens: 1156` — it had
198 tokens of headroom. The budget is marginal, which is exactly why the same
document fails one night and succeeds the next.

Note the control cohort failed too (9/10). These documents *are* classified in the
DB, so they succeeded on an earlier attempt. That is direct evidence the outcome is
a coin flip on reasoning length, not a property of the text.

The probe's own failure rate (19/20) is worse than the nightly's ~20–35%. Not
explained; the probe ran alongside the live classifier, and reasoning length may
drift with server load. It does not change the mechanism, only its severity at
that moment. The probe was not rate-limited: no 429s, no empty-with-`finish_reason=stop`.

### Confirmation: the same documents succeed with headroom

Eight of the nine "length" failures, re-sent with `max_tokens=8000`, everything
else identical:

| documents | finish_reason | parseable JSON | reasoning tokens |
|---|---|---|---|
| 8 / 8 | `stop` | **8 / 8** | 2,804 – 7,133 (mean 4,395) |

**Measured: 100% recovery.** One document needed 7,133 reasoning tokens, so 8,000
is itself marginal for the tail.

### The cheap lever does not work

`reasoning_effort` is accepted by `deepseek-v4-flash` but does not reliably bound
reasoning. Three documents, `max_tokens=8000`:

| doc | `effort="low"` reasoning | `effort="minimal"` reasoning |
|---|---|---|
| 900132342 | 3,894 | 3,619 |
| 900135414 | 1,535 | 3,072 |
| 900137599 | 2,772 | **4,781** |

`minimal` produced *more* reasoning than `low` on two of three. n=3 and noisy, but
there is no usable signal. Do not rely on it to cap spend.

---

## 5. Recommended fix (not implemented)

In priority order.

**(a) Raise `max_tokens` from 2,000 to 12,000** (line 149). Measured tail need is
7,133 reasoning + ~700 content tokens; 12,000 gives ~1.5x headroom on the worst
observed case. This is the whole fix for the ~98% of failures that are budget
exhaustion. Do **not** truncate bodies further and do **not** chunk — the input is
already capped at 1,500 chars and is not the problem.

Cost. `max_tokens` is a ceiling, not a spend floor: the ~70% of documents that
already finish under 2,000 tokens are unaffected. Only the failing ~25% change,
from 2,000 wasted output tokens to ~4,400 productive ones.

| | per doc | per night (~200 failures) | per year |
|---|---|---|---|
| today (wasted) | 2,000 out @ $1.10/M = **$0.0022** | $0.44 | ~$160, buys nothing |
| after fix | ~4,400 out + 1,600 in = **$0.0053** | $1.06 | ~$385, buys classifications |
| **delta** | **+$0.0031** | **+$0.62** | **+$225** |

**(b) Retry once on `finish_reason == "length"`** with a doubled budget, instead
of returning `None`. Cheaper than (a) alone if the budget is kept low, and it is
the correct belt-and-braces for whatever the next model's reasoning length is.

**(c) Record the reason so this is never silent again.** Add a
`classification_error TEXT DEFAULT ''` column (or a small `classification_failures`
side table) and write `length_exhausted` / `content_risk` / `unparseable_json` /
`api_error` on the failure paths, plus an attempt counter. Then promote the three
silent `return None` paths to `print(f"  [skip] doc {id}: <reason>")` so the
nightly log carries a histogram. Zero API cost.

**(d) Stop retrying content-filter rejections forever.** `Content Exists Risk` is a
hard, deterministic 400 (1 of 20 probed documents). Those documents can never
succeed and should be marked terminal rather than re-sent nightly. With (c) in
place this is a one-line guard.

**What it recovers.** `1,864` documents are unclassified right now (0.58% of
323,775), of which the mid-run pool is the bulk; `111` have already lost at least
one night and `50` have been stuck over a week. One backfill pass at the raised
budget costs **~$11** and should clear essentially all of them (8/8 in the probe).
The larger ongoing win is not the backlog, which self-heals by retry, but
eliminating **~200 wasted API calls per night (~6,000/month)** and the multi-day
classification lag they impose on new documents.

```sql
-- the backlog this recovers
SELECT COUNT(*) FROM documents WHERE classified_at IS NULL OR classified_at = '';
```

**Concurrency is not implicated.** No 429s, no empty-with-`stop` responses, and the
probe at concurrency 1 failed at the same mechanism. Leave the cap at 2; the
project's "silent empties above concurrency 2" lesson is real but is a *different*
failure (empty with `finish_reason="stop"`), not this one.
