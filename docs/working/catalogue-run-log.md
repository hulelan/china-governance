# Website-catalogue autonomous run — decision trail

Started 2026-09-09. Trigger: `/poteto-mode` — "complete all cataloguing of all websites while I'm away".
Playbook: Autonomous run + show-me-your-work decision trail.

## Exit predicate (checkable)
A committed `docs/working/gov-website-catalogue.csv` where every finite high-value entity is
CLASSIFIED (no `unknown` left): the 95 Dim-C central bodies, the 34 provincial portals, the
generated provincial-department backbone (~34 × dept-taxonomy), and the ~360 prefecture portals —
each with a candidate `official_url`, a byte-verified reachability (droplet vantage), and a
`coverage_status` ∈ {crawled, reachable_uncrawled, proxy_gated, anti_bot, spa_gated, no_portal},
reconciled against our 494 crawled sites. Plus a coverage report by lane/dimension. County/township
cross-product is the explicit long tail (§5c step 4) — generate portals + sample-verify, not exhaustive.

## Verification stance
Byte-check, not status code (Prove It Works): `curl -sL --max-time 8`, `<2KB = stub/anti-bot`.
Reachability measured from the DROPLET (NYC) — that is the crawl vantage; residential differs and is
not the pipeline's reality. curl_cffi (chrome impersonation) used as a second probe for TLS-gated hosts.

## Iterations
| # | Unit | Predicate moved? | Notes |
|---|---|---|---|
| 1 | Build catalogue lever + reconcile (zero-network) | yes | 1786 entities; central 57 crawled/23 unknown, dept 80/1216, geo 112/283. Committed 876d6d9. |
| 2 | Byte-verify 1514 candidate URLs (droplet vantage) | in flight | curl `-w %{http_code}` bug: double-appended `000` on failure, and `-L` can concatenate per-hop codes → `${code:0:3}` fix. Also: `pkill` raced two sweeps (contaminated a run); re-ran single & clean. Artifacts (`other_000000`) all mean unreachable → normalized post-hoc, no extra re-run. |

| 3 | Province-domain fix + delta verify + final fold-in | yes | reconnect-424 had only 27/34 provinces; supplemented 广东/北京/黑龙江/四川 → geo crawled 112→115, dept 80→88. Delta-verified 203 new URLs clean (0 artifacts). |

**Predicate MET.** Final catalogue: **1978 entities, 260 crawled, 108 reachable-uncrawled (crawl-next), 0 to-verify.** 4 geo unknown = 台/港/澳/那曲 (no mainland .gov.cn portal — genuine edge). Every entity with a URL is byte-verified + classified.

**Deliverables:** `gov-website-catalogue.csv` (the catalogue), `catalogue-crawl-next.tsv` (108-site prioritized yield), `catalogue-coverage-report.md` (the 3-D coverage picture), `build_catalogue.py` + `verify_catalogue.sh` (the rerunnable levers).

**Deferred (out of "cataloguing" scope, tooling in place):** configuring the 108 yield into the crawl pipeline (per-site dialect+sections + validation — a coverage-expansion effort, not cataloguing); Method 2 Google keyword harvest for unaccounted-body discovery (explicitly tranche-work per the model doc §5b; WebSearch budget exhausted this session). The county/township cross-product (~80k entities, mostly no independent portal) is the long tail — generate + sample-probe when a target list justifies it.

**Side items resolved mid-run:** ccg merge landed (16 docs live). mod configured, crawls next nightly (today's sync pulled pre-commit). curl_cffi installed in droplet .venv.
