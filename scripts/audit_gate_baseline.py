"""Audit scheduling gate baseline freeze artifacts for release governance."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KEY_SCRIPTS = [
    REPO_ROOT / "scripts" / "ci_gate_entry.sh",
    REPO_ROOT / "scripts" / "phase4_gate_check.py",
    REPO_ROOT / "scripts" / "phase5_stability_check.py",
    REPO_ROOT / "scripts" / "daily_gate_healthcheck.py",
]
DOC_MATRIX_FILES = [
    REPO_ROOT / "docs" / "TESTING_GUIDE.md",
    REPO_ROOT / "docs" / "OPERATIONS.md",
]


def _collect_test_count() -> tuple[int | None, str]:
    cmd = ["./venv/bin/pytest", "--collect-only", "-q"]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "."},
        check=False,
    )

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = re.search(r"(\d+)\s+tests\s+collected", output)
    count = int(match.group(1)) if match else None
    if proc.returncode != 0:
        return None, f"pytest_collect_failed:rc={proc.returncode}"
    if count is None:
        return None, "pytest_collect_parse_failed"
    return count, "ok"


def _script_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def _doc_has_matrix(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(token in text for token in ("continue", "hold", "rollback_now"))


def run_audit() -> tuple[int, dict[str, object]]:
    collect_count, collect_status = _collect_test_count()

    scripts_report = [
        {
            "path": str(path.relative_to(REPO_ROOT)),
            "exists": _script_exists(path),
        }
        for path in KEY_SCRIPTS
    ]
    missing_scripts = [item["path"] for item in scripts_report if not item["exists"]]

    docs_report = [
        {
            "path": str(path.relative_to(REPO_ROOT)),
            "has_disposition_matrix": _doc_has_matrix(path),
        }
        for path in DOC_MATRIX_FILES
    ]
    docs_missing_matrix = [item["path"] for item in docs_report if not item["has_disposition_matrix"]]

    issues: list[str] = []
    if collect_status != "ok":
        issues.append(collect_status)
    if missing_scripts:
        issues.append(f"missing_scripts:{','.join(missing_scripts)}")
    if docs_missing_matrix:
        issues.append(f"missing_matrix:{','.join(docs_missing_matrix)}")

    report = {
        "baseline_test_count": collect_count,
        "collect_status": collect_status,
        "scripts": scripts_report,
        "docs": docs_report,
        "audit_passed": len(issues) == 0,
        "issues": issues,
    }

    return (0 if not issues else 1), report


def main() -> int:
    code, report = run_audit()
    print(f"audit_passed={str(report['audit_passed']).lower()}")
    print(f"baseline_test_count={report['baseline_test_count']}")
    if report["issues"]:
        print(f"issues={';'.join(report['issues'])}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
