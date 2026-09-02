#!/usr/bin/env bash
# Launch an isolated chinagovernance uvicorn against a fixture SQLite.
# Never points SQLITE_PATH at production documents.db.
set -euo pipefail

HELPERS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HELPERS}/common.sh"
verify_cg_require_repo

mkdir -p "${VERIFY_RUN_DIR}" "${VERIFY_EVIDENCE_DIR}"

if [[ -f "${VERIFY_PID_FILE}" ]]; then
  old_pid="$(cat "${VERIFY_PID_FILE}")"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    echo "verify-chinagovernance: already running pid ${old_pid} (run ${VERIFY_RUN_ID})" >&2
    echo "${VERIFY_BASE_URL}"
    exit 0
  fi
fi

if ss -ltn 2>/dev/null | grep -qE "[:.]${VERIFY_PORT}[[:space:]]"; then
  echo "verify-chinagovernance: port ${VERIFY_PORT} already in use; pick VERIFY_PORT and retry" >&2
  exit 1
fi

python3 "${HELPERS}/seed_fixture.py" --out "${SQLITE_PATH}"

# Refuse to attach to a production-shaped path.
case "${SQLITE_PATH}" in
  *documents.db)
    echo "verify-chinagovernance: SQLITE_PATH must not be documents.db" >&2
    exit 1
    ;;
esac

cd "${VERIFY_REPO_ROOT}"
# --reload forks a watcher; kill-by-pid would miss the child. Stay single-process.
python3 -m uvicorn web.app:app \
  --host "${VERIFY_HOST}" \
  --port "${VERIFY_PORT}" \
  >"${VERIFY_LOG_FILE}" 2>&1 &
uv_pid=$!
echo "${uv_pid}" > "${VERIFY_PID_FILE}"

ready=0
for _ in $(seq 1 40); do
  if ! kill -0 "${uv_pid}" 2>/dev/null; then
    echo "verify-chinagovernance: uvicorn exited during boot" >&2
    tail -n 40 "${VERIFY_LOG_FILE}" >&2 || true
    exit 1
  fi
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "${VERIFY_BASE_URL}/api/v1/stats" 2>/dev/null || true)"
  if [[ "${code}" == "200" ]]; then
    ready=1
    break
  fi
  sleep 0.25
done

if [[ "${ready}" != "1" ]]; then
  echo "verify-chinagovernance: timed out waiting for ${VERIFY_BASE_URL}/api/v1/stats" >&2
  tail -n 40 "${VERIFY_LOG_FILE}" >&2 || true
  kill "${uv_pid}" 2>/dev/null || true
  exit 1
fi

cat > "${VERIFY_META_FILE}" <<EOF
export VERIFY_RUN_ID='${VERIFY_RUN_ID}'
export VERIFY_RUN_DIR='${VERIFY_RUN_DIR}'
export VERIFY_EVIDENCE_DIR='${VERIFY_EVIDENCE_DIR}'
export VERIFY_PORT='${VERIFY_PORT}'
export VERIFY_HOST='${VERIFY_HOST}'
export VERIFY_BASE_URL='${VERIFY_BASE_URL}'
export SQLITE_PATH='${SQLITE_PATH}'
export VERIFY_PID_FILE='${VERIFY_PID_FILE}'
export VERIFY_UVICORN_PID='${uv_pid}'
EOF

{
  echo "launched pid=${uv_pid} url=${VERIFY_BASE_URL} sqlite=${SQLITE_PATH} evidence=${VERIFY_EVIDENCE_DIR}"
  echo "ready: GET ${VERIFY_BASE_URL}/api/v1/stats -> 200"
} | tee "${VERIFY_EVIDENCE_DIR}/launch.txt"

echo "${VERIFY_BASE_URL}"
