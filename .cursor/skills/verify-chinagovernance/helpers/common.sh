# Shared env for verify-chinagovernance helpers. Source this; do not execute.
# shellcheck shell=bash

_VERIFY_SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_VERIFY_REPO_ROOT="$(cd "${_VERIFY_SKILL_DIR}/../../.." && pwd)"

export VERIFY_REPO_ROOT="${VERIFY_REPO_ROOT:-$_VERIFY_REPO_ROOT}"
export VERIFY_SKILL_DIR="${VERIFY_SKILL_DIR:-$_VERIFY_SKILL_DIR}"

# Isolated from the documented `uvicorn ... --port 8001` shared instance.
export VERIFY_PORT="${VERIFY_PORT:-18001}"
export VERIFY_HOST="${VERIFY_HOST:-127.0.0.1}"

if [[ -z "${VERIFY_RUN_ID:-}" ]]; then
  VERIFY_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  export VERIFY_RUN_ID
fi

# Scratch (fixture DB, pid, log). Cleanup deletes this directory.
export VERIFY_RUN_DIR="${VERIFY_RUN_DIR:-/tmp/verify-chinagovernance-${VERIFY_RUN_ID}}"

# Evidence survives cleanup. Named location for proof artifacts.
export VERIFY_EVIDENCE_DIR="${VERIFY_EVIDENCE_DIR:-${VERIFY_SKILL_DIR}/evidence/${VERIFY_RUN_ID}}"

export SQLITE_PATH="${SQLITE_PATH:-${VERIFY_RUN_DIR}/fixture.db}"
export VERIFY_BASE_URL="${VERIFY_BASE_URL:-http://${VERIFY_HOST}:${VERIFY_PORT}}"
export VERIFY_PID_FILE="${VERIFY_PID_FILE:-${VERIFY_RUN_DIR}/uvicorn.pid}"
export VERIFY_LOG_FILE="${VERIFY_LOG_FILE:-${VERIFY_RUN_DIR}/uvicorn.log}"
export VERIFY_META_FILE="${VERIFY_META_FILE:-${VERIFY_RUN_DIR}/meta.env}"

verify_cg_require_repo() {
  if [[ ! -f "${VERIFY_REPO_ROOT}/web/app.py" ]]; then
    echo "verify-chinagovernance: web/app.py not found under ${VERIFY_REPO_ROOT}" >&2
    return 1
  fi
}

verify_cg_load_meta() {
  if [[ -f "${VERIFY_META_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${VERIFY_META_FILE}"
  fi
}
