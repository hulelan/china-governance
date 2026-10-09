#!/usr/bin/env bash
# The owed write sequence, in dependency order, for the window after a long
# classification drain releases the sync lock.
#
# WHY A SCRIPT: the order is not arbitrary and each step's reason is a dependency,
# not a preference (docs/working/write-window-plan.md):
#   * the body-ledger seed must precede any crawl, or the first crawl pays the
#     fetches the ledger exists to stop;
#   * the Wuxi merge must precede build_doc_identity, or merged rows get no
#     identity row;
#   * the trim must precede the BM25 rebuild, so the index is rebuilt once;
#   * build_site_stats must precede build_tracker_rollup, because it writes
#     doc_len, which the rollup reads.
# Composing that live, at the end of a long session, is how an order gets dropped.
#
# SAFETY
#   * refuses to start while the sync lock is held (a second writer against
#     documents.db fails with "database is locked" AFTER paying for fetches --
#     CLAUDE.md, SQLite concurrency);
#   * takes the SAME lock itself, so tomorrow's cron skips rather than collides;
#   * `set -euo pipefail` plus a per-step wrapper that stops the chain on the
#     first failure, because a `for` loop exiting 0 over nine crashed sites is a
#     mistake this project has already made;
#   * --dry-run prints the plan and touches nothing.
#
# Usage:  ./scripts/run_write_window.sh --dry-run
#         ./scripts/run_write_window.sh            # the real thing
set -euo pipefail

LOCK=/tmp/china-governance-daily-sync.lock.d
ROOT=/root/china-governance
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

cd "$ROOT"
LOG="logs/write-window-$(date -u +%Y%m%d-%H%M).log"
say() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$LOG"; }

if [ "$DRY" = 0 ]; then
  if ! mkdir "$LOCK" 2>/dev/null; then
    say "REFUSING: $LOCK is held — the nightly or a drain is still running."
    say "          A second writer would fail on its UPDATE after paying for fetches."
    exit 1
  fi
  trap 'rmdir "$LOCK" 2>/dev/null || true; say "lock released"' EXIT
  say "lock taken: $LOCK"
fi

step() {                       # step "label" cmd...
  local label="$1"; shift
  say "--> $label"
  if [ "$DRY" = 1 ]; then printf '      would run: %s\n' "$*"; return 0; fi
  local t0=$SECONDS
  if ! "$@" >>"$LOG" 2>&1; then
    say "FAILED after $((SECONDS-t0))s: $label"
    say "       the chain stops here ON PURPOSE: every later step depends on this one."
    exit 1
  fi
  say "    ok ($((SECONDS-t0))s)"
}

say "write window starting (dry-run=$DRY). Plan: docs/working/write-window-plan.md"
step "git pull (the droplet is behind; nothing below exists without this)" \
     git pull --ff-only
step "body ledger: schema"            python3 scripts/body_ledger.py --init-schema
step "body ledger: seed (no network)" python3 scripts/body_ledger.py --seed
step "body ledger: stats"             python3 scripts/body_ledger.py --stats
step "PBC crawl (31 -> ~541, oldest 1993-01-14)" python3 -m crawlers.pbc
step "body-tail trim (WITH re-extraction: --no-reextract leaves title-only bodies)" \
     python3 scripts/trim_body_tails.py --apply
step "identity"   python3 scripts/build_doc_identity.py --write --force
step "succession" python3 scripts/build_instrument_succession.py --write --force
step "citations"  python3 scripts/rnd/citations/extract_citations.py
step "site stats (also writes doc_len, which the rollup reads)" \
     python3 scripts/build_site_stats.py
step "diffusion"  python3 scripts/rnd/analysis/build_diffusion_events.py --write
step "tracker"    python3 scripts/build_tracker_rollup.py
step "BM25 (once, after the trim)" python3 scripts/build_search_index_seg.py
step "validate (expect 15/15)" python3 scripts/validate_cascades.py

say "DONE. Now check the seven pre-registered predictions in"
say "      docs/working/prereg-next-rebuild.md — and remember that P1+P6+P7 remove"
say "      ~5,156 edges while P4 adds some, so the NET resolution number is not"
say "      interpretable. Check each fix by its own named test."
