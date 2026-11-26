#!/bin/bash
# Copy the corpus to a USB disk, as a second copy beside DO Spaces. Run on the MAC.
#
#   ./scripts/usb_backup.sh /Volumes/<USB>              # databases + droplet raw_html
#   ./scripts/usb_backup.sh /Volumes/<USB> --with-mac-raw   # also the old Desktop raw_html
#
# What lands on the disk (re-running only fetches what changed):
#   cg-backup/db/documents-YYYYMMDD.db.gz   newest nightly Spaces backup (~6 GB); last 2 kept
#   cg-backup/db/officials-YYYYMMDD.db.gz
#   cg-backup/raw_html/droplet/             the droplet's saved pages (~12 GB), incremental rsync
#   cg-backup/raw_html/mac-desktop/         the ~144k pre-June pages that exist ONLY on this Mac
#   cg-backup/MANIFEST.txt                  date, file sizes, sha256, page counts
#
# The databases come from Spaces, not from the live file, because the nightly backup is
# already a consistent VACUUM INTO snapshot; copying the live WAL database would not be.
# The Spaces secret stays on the droplet: scripts/spaces_presign.py hands out 6-hour URLs.
#
# Disk: exFAT or APFS. NOT FAT32, which cannot hold a file over 4 GB (documents is ~6 GB).
set -euo pipefail

DROPLET=root@104.236.88.45
REPO=/root/china-governance
MAC_RAW="$HOME/Desktop/claude_code/china-governance/raw_html"

DEST="${1:-}"
WITH_MAC_RAW=0
[ "${2:-}" = "--with-mac-raw" ] && WITH_MAC_RAW=1
if [ -z "$DEST" ] || [ ! -d "$DEST" ]; then
  echo "usage: $0 /Volumes/<USB> [--with-mac-raw]   (the disk must be mounted)" >&2
  exit 2
fi

FS=$(diskutil info "$DEST" 2>/dev/null | awk -F: '/File System Personality/ {gsub(/^ +/,"",$2); print $2}')
echo "Disk: $DEST  filesystem: ${FS:-unknown}"
case "$FS" in
  *FAT32*|"MS-DOS FAT32") echo "REFUSING: FAT32 cannot store files over 4 GB. Reformat as exFAT or APFS." >&2; exit 2;;
esac

ROOT="$DEST/cg-backup"
mkdir -p "$ROOT/db" "$ROOT/raw_html/droplet"

# ---- 1. databases, from the newest nightly backup in Spaces ----
echo "== Databases"
LIST=$(ssh -o ConnectTimeout=15 "$DROPLET" \
  "cd $REPO && set -a && . ./.env && set +a && .venv/bin/python3 scripts/spaces_presign.py" < /dev/null)
while IFS=$'\t' read -r NAME SIZE URL; do
  [ -z "$NAME" ] && continue
  OUT="$ROOT/db/$NAME"
  if [ -f "$OUT" ] && [ "$(stat -f %z "$OUT")" = "$SIZE" ]; then
    echo "   $NAME already on disk"
  else
    echo "   downloading $NAME ($((SIZE / 1000000)) MB)"
    curl -fL --retry 5 -C - -o "$OUT.part" "$URL"
    mv "$OUT.part" "$OUT"
  fi
  echo "   checking $NAME"
  gzip -t "$OUT"
  # keep the newest two of each database
  STEM="${NAME%%-*}"
  ls -1 "$ROOT/db/$STEM"-*.db.gz | sort -r | tail -n +3 | while read -r OLD; do
    echo "   removing older $(basename "$OLD")"; rm -f "$OLD"
  done
done <<< "$LIST"

# ---- 2. the droplet's raw_html ----
# -rt, not -a: exFAT has no Unix owners or permissions. --modify-window=2 because exFAT
# stores times at 2-second precision, which would otherwise re-copy every file each run.
echo "== raw_html from the droplet"
rsync -rt --modify-window=2 --stats "$DROPLET:$REPO/raw_html/" "$ROOT/raw_html/droplet/" \
  | grep -E "Number of files|transferred|Total transferred" || true

# ---- 3. the Mac-only pages (optional: iCloud has to download them first, slow) ----
if [ "$WITH_MAC_RAW" = 1 ]; then
  echo "== raw_html from the old Desktop checkout (iCloud downloads each file as it copies)"
  mkdir -p "$ROOT/raw_html/mac-desktop"
  rsync -rt --modify-window=2 --stats "$MAC_RAW/" "$ROOT/raw_html/mac-desktop/" \
    | grep -E "Number of files|transferred|Total transferred" || true
fi

# ---- 4. manifest ----
echo "== Manifest"
{
  echo "China governance corpus, USB copy"
  echo "written: $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo
  for F in "$ROOT"/db/*.db.gz; do
    echo "$(basename "$F")  $(stat -f %z "$F") bytes  sha256 $(shasum -a 256 "$F" | cut -d' ' -f1)"
  done
  echo
  for D in "$ROOT"/raw_html/*/; do
    echo "raw_html/$(basename "$D"): $(find "$D" -type f | wc -l | tr -d ' ') files"
  done
  echo
  echo "Restore: gunzip documents-YYYYMMDD.db.gz  -> a plain SQLite file."
} > "$ROOT/MANIFEST.txt"
cat "$ROOT/MANIFEST.txt"
echo "Done. Eject the disk before unplugging it."
