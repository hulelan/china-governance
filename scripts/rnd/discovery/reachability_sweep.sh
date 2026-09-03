#!/bin/bash
# Reachability sweep for CN government source portals.
# Keeps docs/working/source-access-map.md refreshable. RUN ON THE DROPLET (the NYC
# datacenter IP is the vantage whose reachability we care about):
#   ssh root@104.236.88.45 'bash - ' < scripts/rnd/discovery/reachability_sweep.sh <list
# or copy it over and: bash reachability_sweep.sh <list-file>
#
# Each input line: tier|name|url   (lines starting with # or blank are skipped)
#
# WHY THIS EXISTS: HTTP status is unreliable for CN gov sites — many return 200 with a
# ~160-byte redirect stub or a ~1KB anti-bot shell. So we ALSO measure content bytes
# (after following redirects) and probe a policy section (/zwgk/). See the "Method"
# section of docs/working/source-access-map.md.
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
MINBYTES=2000   # after redirect-follow, < this = stub/anti-bot/dead, not real content

probe() {
  IFS='|' read -r tier name url <<<"$1"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 -A "$UA" "$url/" 2>/dev/null)
  bytes=$(curl -sL --max-time 15 -A "$UA" "$url/" 2>/dev/null | wc -c)
  sec=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 -A "$UA" "$url/zwgk/" 2>/dev/null)
  case "$code" in
    000)          v="BLACKHOLE (proxy-gated)";;
    403|406|412)  v="WAF$code (proxy-gated)";;
    521|522|523)  v="ANTI-BOT/origin($code)";;
    200|301|302)  if [ "${bytes:-0}" -lt "$MINBYTES" ]; then
                    v="STUB ${bytes}b (not real: anti-bot/dead redirect)";
                  else v="REACHABLE ${bytes}b"; fi;;
    *)            v="other($code)";;
  esac
  printf "%-12s %-26s %-32s %-42s [sec=%s]\n" "$tier" "$name" "$url" "$v" "$sec"
}
export -f probe; export UA MINBYTES
grep -vE '^\s*(#|$)' "${1:-/dev/stdin}" | xargs -d '\n' -P 12 -I{} bash -c 'probe "{}"' | sort
