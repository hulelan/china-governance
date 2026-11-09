#!/bin/bash
# SessionEnd hook: distil new transcripts into PROPOSALS, never into memory/.
# Applying stays a reviewed, manual step (organize.py, then dream.py --apply-plan).
#
# Returns immediately: the work runs detached, so closing a session never waits
# on it. Guards, each for a failure we would otherwise only see in the bill:
#   DREAM_CHILD   dream.py's own `claude -p` analyzers end sessions too; without
#                 this a dream would trigger a dream.
#   lock dir      two sessions closing together must not run two passes.
#   --limit       caps one pass at ~20 transcripts (~$0.60 at the first run's rate).
#   audit         a leak in the export stops the pass before any model reads it.
set -u
[ -n "${DREAM_CHILD:-}" ] && exit 0
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
SLUG="$(echo "$REPO" | sed 's#[/_.]#-#g')"
WORK="$HOME/.claude/projects/$SLUG/dream"
LOCK="$WORK/.lock.d"
mkdir -p "$WORK"
mkdir "$LOCK" 2>/dev/null || exit 0

nohup env DREAM_CHILD=1 bash -c '
  trap "rmdir \"$1\"" EXIT
  cd "$2" || exit 1
  echo "=== $(date -u +%FT%TZ) session-end dream"
  python3 -u scripts/rnd/dream/export_transcripts.py --out "$3/transcripts" &&
  python3 -u scripts/rnd/dream/export_transcripts.py --audit "$3/transcripts" &&
  { python3 -u scripts/rnd/dream/verify_memory.py --out "$3/staleness.md" --quiet
    true; } &&   # exits 1 on any stale claim; that report is analyzer INPUT, not a gate
  python3 -u scripts/rnd/dream/dream.py --work "$3" --staleness "$3/staleness.md" \
      --analyze-only --limit 20
  echo "=== exit $?"
' _ "$LOCK" "$REPO" "$WORK" >> "$WORK/session_end.log" 2>&1 < /dev/null &
exit 0
