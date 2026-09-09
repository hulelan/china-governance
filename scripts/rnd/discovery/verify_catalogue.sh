#!/bin/bash
# Byte-check a catalogue to-verify list (id<TAB>url) and classify each into a
# coverage_status. HTTP 200 is unreliable for CN gov: byte-check + follow redirects.
# Output: id<TAB>coverage_status<TAB>bytes<TAB>httpcode  (one line per input row).
# Usage: verify_catalogue.sh <to-verify.tsv>   (parallelize with xargs upstream)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
classify() {
  id="$1"; url="$2"
  tmp=$(mktemp /tmp/cat_XXXXXX.body)          # unique per worker (no $$ race across xargs)
  code=$(curl -sL --max-time 8 -A "$UA" -o "$tmp" -w '%{http_code}' "$url" 2>/dev/null)  # curl -w prints 000 on failure
  code="${code:0:3}"; [ -z "$code" ] && code="000"   # -L can emit a per-hop-concatenated code; keep the first
  bytes=$(wc -c < "$tmp" 2>/dev/null || echo 0); rm -f "$tmp"
  case "$code" in
    000) st=blackhole ;;
    404|410) st=no_portal ;;
    403|406|412) st=proxy_gated ;;
    418|521) st=anti_bot ;;
    200|301|302)
      if [ "$bytes" -lt 2000 ]; then st=stub_gated; else st=reachable_uncrawled; fi ;;
    *) st=other_$code ;;
  esac
  printf '%s\t%s\t%s\t%s\n' "$id" "$st" "$bytes" "$code"
}
export -f classify
export UA
# read id<TAB>url, run classify in parallel
awk -F'\t' 'NF>=2{print $1"\t"$2}' "$1" | \
  xargs -P 10 -d '\n' -I{} bash -c 'IFS=$'"'"'\t'"'"' read -r id url <<< "{}"; classify "$id" "$url"'
