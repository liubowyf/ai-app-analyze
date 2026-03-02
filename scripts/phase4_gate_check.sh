#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=. ./venv/bin/python scripts/phase4_gate_check.py "$@"
