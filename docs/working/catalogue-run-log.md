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
| 1 | Build catalogue lever + reconcile (zero-network) | pending | |
