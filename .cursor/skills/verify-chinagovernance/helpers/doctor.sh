#!/usr/bin/env bash
# Read-only health check: is THIS run's instance worth driving?
set -euo pipefail

HELPERS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HELPERS}/common.sh"
verify_cg_load_meta

fail() { echo "doctor FAIL: $*" >&2; exit 1; }
ok() { echo "doctor ok: $*"; }

[[ -f "${VERIFY_PID_FILE}" ]] || fail "no pid file at ${VERIFY_PID_FILE} (launch first)"
pid="$(cat "${VERIFY_PID_FILE}")"
[[ -n "${pid}" ]] || fail "empty pid file"
kill -0 "${pid}" 2>/dev/null || fail "pid ${pid} is not running"

cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
[[ "${cmdline}" == *uvicorn* ]] || fail "pid ${pid} cmdline is not uvicorn: ${cmdline}"
[[ "${cmdline}" == *"${VERIFY_PORT}"* ]] || fail "pid ${pid} not bound to port ${VERIFY_PORT}: ${cmdline}"

# Confirm the port is owned by this pid (not a leftover shared instance).
SS_BIN="$(command -v ss 2>/dev/null || true)"
[[ -z "${SS_BIN}" && -x /usr/sbin/ss ]] && SS_BIN=/usr/sbin/ss
if [[ -n "${SS_BIN}" ]]; then
  owners="$("${SS_BIN}" -ltnp 2>/dev/null | grep -E "[:.]${VERIFY_PORT}[[:space:]]" || true)"
  [[ -n "${owners}" ]] || fail "nothing listening on port ${VERIFY_PORT}"
  if [[ "${owners}" == *pid=* ]]; then
    [[ "${owners}" == *pid="${pid}"* ]] || fail "port ${VERIFY_PORT} not owned by pid ${pid}: ${owners}"
  fi
fi

# SQLITE_PATH in the process environment must be our fixture, never documents.db.
proc_env="$(tr '\0' '\n' < "/proc/${pid}/environ" 2>/dev/null || true)"
proc_sqlite="$(printf '%s\n' "${proc_env}" | awk -F= '/^SQLITE_PATH=/{print $2; exit}')"
[[ -n "${proc_sqlite}" ]] || fail "uvicorn pid ${pid} has no SQLITE_PATH in environ"
[[ "${proc_sqlite}" != *documents.db ]] || fail "SQLITE_PATH points at documents.db — refuse to drive"
[[ -f "${proc_sqlite}" ]] || fail "SQLITE_PATH file missing: ${proc_sqlite}"

marker="$(sqlite3 "${proc_sqlite}" "SELECT value FROM _verify_scaffold WHERE key='kind';" 2>/dev/null || true)"
[[ "${marker}" == "VERIFICATION_SCAFFOLDING_NOT_PRODUCTION" ]] || fail "fixture marker missing on ${proc_sqlite}"

stats_body="$(mktemp)"
code="$(curl -sS -o "${stats_body}" -w '%{http_code}' --max-time 5 "${VERIFY_BASE_URL}/api/v1/stats" || true)"
[[ "${code}" == "200" ]] || fail "/api/v1/stats HTTP ${code}"
python3 - "${stats_body}" <<'PY'
import json, sys
p = sys.argv[1]
data = json.load(open(p, encoding="utf-8"))
for k in ("total", "site_count", "with_body"):
    if k not in data:
        raise SystemExit(f"stats missing {k}: {data!r}")
if int(data["total"]) < 1:
    raise SystemExit(f"stats.total is {data['total']}; homepage would divide by zero")
print(f"stats total={data['total']} sites={data['site_count']} with_body={data['with_body']}")
PY

home_code="$(curl -sS -o /tmp/verify-cg-home.html -w '%{http_code}' --max-time 5 "${VERIFY_BASE_URL}/" || true)"
[[ "${home_code}" == "200" ]] || fail "GET / HTTP ${home_code}"
grep -q "中国政策档案" /tmp/verify-cg-home.html || fail "homepage missing masthead 中国政策档案"
grep -q "HOLDINGS" /tmp/verify-cg-home.html || fail "homepage missing HOLDINGS stat"

ok "pid ${pid} on ${VERIFY_BASE_URL} fixture=${proc_sqlite}"
ok "app answering / and /api/v1/stats"
echo "DOCTOR_OK ${VERIFY_BASE_URL}"
