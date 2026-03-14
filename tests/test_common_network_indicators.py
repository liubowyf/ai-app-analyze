from __future__ import annotations

import json
from pathlib import Path

from modules.domain_intelligence.relevance import load_common_network_indicator_seed


def test_common_network_indicator_seed_contains_expected_suffix_rules():
    rows = load_common_network_indicator_seed()

    assert rows
    assert any(row.pattern == "googleapis.com" and row.match_type == "suffix" for row in rows)
    assert any(row.pattern == "play.googleapis.com" and row.action == "demote" for row in rows)
    assert any(row.pattern == "openinstall.com" and row.action == "demote" for row in rows)
    assert any(row.pattern == "umeng.com" and row.action == "demote" for row in rows)
    assert any(row.pattern == "appsflyer.com" and row.action == "demote" for row in rows)
    assert any(row.pattern == "onelink.me" and row.action == "demote" for row in rows)
    assert any(row.pattern == "app-measurement.com" and row.action == "demote" for row in rows)
    assert any(row.pattern == "branch.io" and row.action == "demote" for row in rows)
    assert any(row.pattern == "doubleclick.net" and row.action == "demote" for row in rows)
    assert any(row.pattern == "sdk-analytics.example" and row.action == "demote" for row in rows)


def test_common_network_indicator_seed_file_is_valid_json():
    catalog_path = (
        Path(__file__).resolve().parents[1] / "data" / "common_network_indicators.json"
    )

    rows = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert isinstance(rows, list)
    assert all(isinstance(row, dict) for row in rows)
