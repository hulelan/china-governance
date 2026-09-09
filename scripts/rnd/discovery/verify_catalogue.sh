#!/bin/bash
# Byte-check a catalogue to-verify list (id<TAB>url) and classify each into a
# coverage_status. HTTP 200 is unreliable for CN gov: byte-check + follow redirects.
# Output: id<TAB>coverage_status<TAB>bytes<TAB>httpcode  (one line per input row).
# Usage: verify_catalogue.sh <to-verify.tsv>   (parallelize with xargs upstream)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
classify() {
  id="$1"; url="$2"
  read -r code bytes < <(curl -sL --max-time 8 -A "$UA" -o /tmp/cat_$$.body -w '%{http_code} %{size_download}' "$url" 2>/dev/null || echo "000 0")
  bytes=$(wc -c < /tmp/cat_$$.body 2>/dev/null || echo 0); rm -f /tmp/cat_$$.body
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
