#!/usr/bin/env bash
# Tear down the instance THIS run started. Never kill by process name.
# Removes scratch (fixture DB, pid, logs). Never removes VERIFY_EVIDENCE_DIR.
set -euo pipefail

HELPERS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HELPERS}/common.sh"
verify_cg_load_meta

pid=""
if [[ -f "${VERIFY_PID_FILE}" ]]; then
  pid="$(cat "${VERIFY_PID_FILE}" || true)"
fi

if [[ -n "${pid}" ]]; then
  if kill -0 "${pid}" 2>/dev/null; then
    kill -TERM "${pid}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.2
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  fi
fi

if [[ -n "${VERIFY_RUN_DIR}" && -d "${VERIFY_RUN_DIR}" ]]; then
  rm -rf "${VERIFY_RUN_DIR}"
fi

echo "cleanup: stopped pid=${pid:-none} removed ${VERIFY_RUN_DIR}"
echo "cleanup: evidence kept at ${VERIFY_EVIDENCE_DIR}"
if [[ -d "${VERIFY_EVIDENCE_DIR}" ]]; then
  ls -la "${VERIFY_EVIDENCE_DIR}"
else
  echo "cleanup WARN: evidence dir missing at ${VERIFY_EVIDENCE_DIR}" >&2
fi
