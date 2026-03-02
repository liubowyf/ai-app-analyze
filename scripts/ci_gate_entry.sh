#!/usr/bin/env bash
set -euo pipefail

# Unified local/CI gate entrypoint: gate must emit final_action/final_reason.
tmp_output="$(mktemp)"
trap 'rm -f "${tmp_output}"' EXIT

if [[ -n "${CI_GATE_COMMAND:-}" ]]; then
  gate_cmd=(zsh -lc "${CI_GATE_COMMAND}")
else
  gate_cmd=(bash scripts/phase4_gate_check.sh "$@")
fi

set +e
"${gate_cmd[@]}" 2>&1 | tee "${tmp_output}"
gate_rc=${PIPESTATUS[0]}
set -e

if ! grep -q '^final_action=' "${tmp_output}"; then
  echo "final_action=missing" >&2
  exit 1
fi

if ! grep -q '^final_reason=' "${tmp_output}"; then
  echo "final_reason=missing" >&2
  exit 1
fi

exit "${gate_rc}"
