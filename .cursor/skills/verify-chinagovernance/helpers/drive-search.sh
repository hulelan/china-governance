#!/usr/bin/env bash
# Drive the Search feature the way a user does: GET /search form → submit q → open a hit.
# Captures action HTML and resulting state into VERIFY_EVIDENCE_DIR.
set -euo pipefail

HELPERS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HELPERS}/common.sh"
verify_cg_load_meta

fail() { echo "drive-search FAIL: $*" >&2; exit 1; }

[[ -n "${VERIFY_EVIDENCE_DIR:-}" ]] || fail "VERIFY_EVIDENCE_DIR unset"
mkdir -p "${VERIFY_EVIDENCE_DIR}"

Q="${VERIFY_SEARCH_Q:-人工智能}"
NEG="${VERIFY_SEARCH_NEG:-住房保障}"

# --- Action 1: open the search form (nav Catalog/Search user path) ---
code="$(curl -sS -o "${VERIFY_EVIDENCE_DIR}/search-empty.html" -w '%{http_code}' \
  --max-time 10 "${VERIFY_BASE_URL}/search")"
[[ "${code}" == "200" ]] || fail "GET /search HTTP ${code}"
grep -q 'form action="/search"' "${VERIFY_EVIDENCE_DIR}/search-empty.html" \
  || fail "empty search page missing form action=/search"
grep -q 'name="q"' "${VERIFY_EVIDENCE_DIR}/search-empty.html" \
  || fail "empty search page missing input name=q"
grep -q 'name="exclude_news"' "${VERIFY_EVIDENCE_DIR}/search-empty.html" \
  || fail "empty search page missing exclude_news checkbox"
if grep -q 'results for' "${VERIFY_EVIDENCE_DIR}/search-empty.html"; then
  fail "empty /search should not list results"
fi

# --- Action 2: submit the same GET form a user would ---
# Form is method=get action=/search; curl of /search?q= is the real user path.
code="$(curl -sS -o "${VERIFY_EVIDENCE_DIR}/search-hits.html" -w '%{http_code}' \
  --max-time 10 --get --data-urlencode "q=${Q}" "${VERIFY_BASE_URL}/search")"
[[ "${code}" == "200" ]] || fail "GET /search?q= HTTP ${code}"

hits_page="${VERIFY_EVIDENCE_DIR}/search-hits.html"
grep -q "results for \"${Q}\"" "${hits_page}" || fail "missing results-for line for ${Q}"
grep -q 'href="/document/1"' "${hits_page}" || fail "missing link to fixture doc 1"
grep -q '国务院关于深入实施' "${hits_page}" || fail "missing central AI title"
grep -q '广东省人民政府关于贯彻落实国务院人工智能' "${hits_page}" || fail "missing Guangdong AI title"
grep -q '深圳市推动人工智能高质量发展行动方案' "${hits_page}" || fail "missing Shenzhen AI title"
grep -q '新华时评：以人工智能赋能高质量发展' "${hits_page}" || fail "missing Xinhua AI title"
if grep -q "${NEG}" "${hits_page}"; then
  fail "housing negative-control title leaked into AI search results"
fi

# Count: fixture seeds 4 AI hits (ids 1–4). Parse the visible total.
python3 - "${hits_page}" "${Q}" <<'PY'
import re, sys
html, q = open(sys.argv[1], encoding="utf-8").read(), sys.argv[2]
m = re.search(r'([\d,]+) results for "' + re.escape(q) + r'"', html)
if not m:
    raise SystemExit("could not parse results count")
total = int(m.group(1).replace(",", ""))
if total != 4:
    raise SystemExit(f"expected 4 fixture hits for {q!r}, got {total}")
print(f"search hits total={total}")
PY

# --- Action 3: exclude news (same form, checkbox name=exclude_news value=1) ---
code="$(curl -sS -o "${VERIFY_EVIDENCE_DIR}/search-exclude-news.html" -w '%{http_code}' \
  --max-time 10 --get --data-urlencode "q=${Q}" --data-urlencode "exclude_news=1" \
  "${VERIFY_BASE_URL}/search")"
[[ "${code}" == "200" ]] || fail "GET /search?exclude_news=1 HTTP ${code}"
excl="${VERIFY_EVIDENCE_DIR}/search-exclude-news.html"
grep -q '新华时评' "${excl}" && fail "exclude_news still shows Xinhua hit"
grep -q 'href="/document/1"' "${excl}" || fail "exclude_news dropped the government hit"
python3 - "${excl}" "${Q}" <<'PY'
import re, sys
html, q = open(sys.argv[1], encoding="utf-8").read(), sys.argv[2]
m = re.search(r'([\d,]+) results for "' + re.escape(q) + r'"', html)
total = int(m.group(1).replace(",", "")) if m else -1
if total != 3:
    raise SystemExit(f"exclude_news expected 3 hits, got {total}")
print(f"exclude_news total={total}")
PY

# --- Resulting state: open the first catalog hit ---
code="$(curl -sS -o "${VERIFY_EVIDENCE_DIR}/document-1.html" -w '%{http_code}' \
  --max-time 10 "${VERIFY_BASE_URL}/document/1")"
[[ "${code}" == "200" ]] || fail "GET /document/1 HTTP ${code}"
grep -q "ACC. 1" "${VERIFY_EVIDENCE_DIR}/document-1.html" || fail "document page missing ACC. 1"
grep -q '国务院关于深入实施' "${VERIFY_EVIDENCE_DIR}/document-1.html" || fail "document page missing CN title"
grep -q 'id="doc-body"' "${VERIFY_EVIDENCE_DIR}/document-1.html" || fail "document page missing #doc-body"
grep -q "人工智能赋能千行百业" "${VERIFY_EVIDENCE_DIR}/document-1.html" || fail "document body text missing"

# Side channel (public JSON API, same query) — corroborates the HTML total.
code="$(curl -sS -o "${VERIFY_EVIDENCE_DIR}/api-search.json" -w '%{http_code}' \
  --max-time 10 --get --data-urlencode "q=${Q}" "${VERIFY_BASE_URL}/api/v1/search")"
[[ "${code}" == "200" ]] || fail "GET /api/v1/search HTTP ${code}"
python3 - "${VERIFY_EVIDENCE_DIR}/api-search.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
if int(data.get("total") or 0) != 4:
    raise SystemExit(f"api search total expected 4, got {data.get('total')}")
ids = {r["id"] for r in data.get("results") or []}
if ids != {1, 2, 3, 4}:
    raise SystemExit(f"api search ids expected {{1,2,3,4}}, got {ids}")
print("api search ids", sorted(ids))
PY

# Optional Chrome screenshot of the results page (headless; exits on its own).
if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
  chrome="$(command -v google-chrome-stable || command -v google-chrome)"
  "${chrome}" --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage \
    --window-size=1280,900 \
    --screenshot="${VERIFY_EVIDENCE_DIR}/search-hits.png" \
    "${VERIFY_BASE_URL}/search?q=${Q}" \
    >/dev/null 2>>"${VERIFY_EVIDENCE_DIR}/chrome.log" || true
  "${chrome}" --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage \
    --window-size=1280,900 \
    --screenshot="${VERIFY_EVIDENCE_DIR}/document-1.png" \
    "${VERIFY_BASE_URL}/document/1" \
    >/dev/null 2>>"${VERIFY_EVIDENCE_DIR}/chrome.log" || true
fi

cat > "${VERIFY_EVIDENCE_DIR}/drive-search.txt" <<EOF
feature: search
entry: GET ${VERIFY_BASE_URL}/search then GET /search?q=${Q}
action: submit catalog search form (method=get, input[name=q])
result: 4 hits for ${Q}; housing title absent; exclude_news drops Xinhua → 3
follow: GET /document/1 shows ACC. 1, CN title, #doc-body
api_corroboration: /api/v1/search total=4 ids=1,2,3,4 (fixture, not production corpus)
EOF

echo "DRIVE_OK search → ${VERIFY_EVIDENCE_DIR}"
