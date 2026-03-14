"""Heuristics for suspected app-controlled domain/IP ranking."""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from models.analysis_tables import CommonNetworkIndicatorTable


GENERIC_APP_TOKENS = {
    "android",
    "app",
    "apps",
    "client",
    "com",
    "global",
    "mobile",
    "release",
    "service",
    "system",
    "www",
}
SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "common_network_indicators.json"


@dataclass(frozen=True, slots=True)
class CommonNetworkIndicator:
    pattern: str
    match_type: str
    category: str | None
    vendor: str | None
    action: str
    description: str | None


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    include: bool
    relevance_score: int
    relevance_level: str
    reasons: list[str]
    is_common_infra: bool
    infra_category: str | None


def _normalize_token(token: str) -> str | None:
    value = re.sub(r"[^a-z0-9]", "", token.lower())
    if len(value) < 3 or value.isdigit() or value in GENERIC_APP_TOKENS:
        return None
    return value


def extract_app_tokens(app_name: str | None, package_name: str | None) -> set[str]:
    tokens: set[str] = set()
    for raw in [app_name or "", package_name or ""]:
        for part in re.split(r"[^a-zA-Z0-9]+", raw):
            normalized = _normalize_token(part)
            if normalized:
                tokens.add(normalized)
    return tokens


build_app_identity_tokens = extract_app_tokens


def _match_indicator(
    domain: str | None,
    ip: str | None,
    indicator: CommonNetworkIndicator,
) -> bool:
    pattern = (indicator.pattern or "").strip().lower()
    if not pattern:
        return False

    domain_value = (domain or "").strip().lower()
    ip_value = (ip or "").strip()
    match_type = indicator.match_type

    if match_type == "exact":
        return domain_value == pattern or ip_value == indicator.pattern
    if match_type == "suffix":
        if not domain_value:
            return False
        return domain_value == pattern or domain_value.endswith(f".{pattern}") or domain_value.endswith(pattern)
    if match_type == "contains":
        return bool(domain_value and pattern in domain_value)
    if match_type == "ip_cidr":
        if not ip_value:
            return False
        try:
            return ipaddress.ip_address(ip_value) in ipaddress.ip_network(indicator.pattern, strict=False)
        except Exception:
            return False
    return False


def load_indicator_rows(rows: Iterable[Any]) -> list[CommonNetworkIndicator]:
    indicators: list[CommonNetworkIndicator] = []
    for row in rows:
        pattern = str(getattr(row, "pattern", "") or "").strip()
        match_type = str(getattr(row, "match_type", "") or "").strip()
        action = str(getattr(row, "action", "") or "demote").strip() or "demote"
        if not pattern or not match_type:
            continue
        indicators.append(
            CommonNetworkIndicator(
                pattern=pattern,
                match_type=match_type,
                category=getattr(row, "category", None),
                vendor=getattr(row, "vendor", None),
                action=action,
                description=getattr(row, "description", None),
            )
        )
    return indicators


@lru_cache(maxsize=1)
def load_common_network_indicator_seed() -> list[CommonNetworkIndicator]:
    if not SEED_PATH.exists():
        return []
    try:
        rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    return load_indicator_rows(
        type("SeedRow", (), row)
        for row in rows
        if isinstance(row, dict)
    )


def load_common_network_indicators(db: Session | None = None) -> list[CommonNetworkIndicator]:
    seed_rows = load_common_network_indicator_seed()
    if db is None:
        return seed_rows
    try:
        bind = db.get_bind()
        if bind is None:
            return seed_rows
        inspector = inspect(bind)
        if "common_network_indicators" not in inspector.get_table_names():
            return seed_rows
        rows = db.query(CommonNetworkIndicatorTable).all()
        merged: dict[tuple[str, str, str], CommonNetworkIndicator] = {
            (row.pattern, row.match_type, row.action): row for row in seed_rows
        }
        for row in load_indicator_rows(rows):
            merged[(row.pattern, row.match_type, row.action)] = row
        return list(merged.values())
    except Exception:
        return seed_rows


def score_domain_candidate(
    item: dict[str, Any] | None = None,
    *,
    domain: str | None = None,
    ip: str | None = None,
    hit_count: int | None = None,
    source_types: Iterable[str] | None = None,
    app_tokens: set[str],
    confidence: str | None = None,
    indicators: Iterable[CommonNetworkIndicator],
    post_count: int | None = None,
) -> dict[str, Any]:
    item = item or {}
    domain = str(domain if domain is not None else item.get("domain") or "").strip().lower() or None
    ip = str(ip if ip is not None else item.get("ip") or "").strip() or None
    hit_count = int(hit_count if hit_count is not None else item.get("hit_count") or item.get("request_count") or 0)
    source_types = [
        str(value).lower()
        for value in (source_types if source_types is not None else item.get("source_types") or [])
        if value
    ]
    confidence = str(confidence if confidence is not None else item.get("confidence") or "").lower()

    score = 0
    reasons: list[str] = []
    is_common_infra = False
    infra_category: str | None = None

    if domain:
        matched_tokens = sorted(token for token in app_tokens if token in domain)
        if matched_tokens:
            score += 40
            reasons.append("命中应用标识词")
        if "." in domain:
            root_label = domain.split(".", 1)[0]
            if any(token in root_label for token in app_tokens):
                score += 10
                reasons.append("主机名前缀与应用标识相关")

    if hit_count > 0:
        score += min(hit_count, 10) * 2
        if hit_count >= 3:
            reasons.append("命中次数较高")

    unique_source_count = len(set(source_types))
    if unique_source_count >= 2:
        score += 10
        reasons.append("多来源交叉出现")
    elif unique_source_count == 1 and source_types:
        score += 3

    if confidence == "high":
        score += 10
    elif confidence == "medium":
        score += 6
    elif confidence == "observed":
        score += 4

    if int(post_count if post_count is not None else item.get("post_count") or 0) > 0:
        score += 8
        reasons.append("存在业务写操作")

    matched_indicators = [indicator for indicator in indicators if _match_indicator(domain, ip, indicator)]
    if matched_indicators:
        is_common_infra = True
        infra_category = matched_indicators[0].category
        if any(indicator.action == "exclude" for indicator in matched_indicators):
            return {
                "excluded": True,
                "relevance_score": 0,
                "relevance_level": "low",
                "reasons": ["命中系统或公共基础设施规则，已排除"],
                "is_common_infra": True,
                "infra_category": infra_category,
            }
        score -= 45
        reasons.append("命中公共基础设施规则，已降级")

    score = max(score, 0)
    if score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    include = score >= 15
    if not reasons:
        reasons.append("基于运行期观测保留")

    return {
        "excluded": not include,
        "relevance_score": score,
        "relevance_level": level,
        "reasons": reasons,
        "is_common_infra": is_common_infra,
        "infra_category": infra_category,
    }


def score_ip_candidate(
    item: dict[str, Any],
    *,
    indicators: Iterable[CommonNetworkIndicator],
    related_domain_rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    ip = str(item.get("ip") or "").strip() or None
    score = 0
    reasons: list[str] = []
    is_common_infra = False
    infra_category: str | None = None

    matched_indicators = [indicator for indicator in indicators if _match_indicator(None, ip, indicator)]
    if matched_indicators:
        is_common_infra = True
        infra_category = matched_indicators[0].category
        if any(indicator.action == "exclude" for indicator in matched_indicators):
            return {
                "excluded": True,
                "relevance_score": 0,
                "relevance_level": "low",
                "reasons": ["命中系统或公共基础设施规则，已排除"],
                "is_common_infra": True,
                "infra_category": infra_category,
            }
        score -= 30
        reasons.append("命中公共基础设施 IP 规则，已降级")

    domain_rows = [row for row in related_domain_rows if row.get("ip") == ip]
    if domain_rows:
        best = max(domain_rows, key=lambda row: int(row.get("relevance_score") or 0))
        score += int(best.get("relevance_score") or 0)
        if best.get("domain"):
            reasons.append(f"关联高置信域名 {best['domain']}")
        if best.get("is_common_infra"):
            is_common_infra = True
            infra_category = best.get("infra_category") or infra_category
    else:
        score += min(int(item.get("hit_count") or 0), 10) * 2
        reasons.append("基于独立 IP 观测保留")

    if int(item.get("hit_count") or 0) >= 3:
        score += 6
        reasons.append("命中次数较高")

    score = max(score, 0)
    if score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    return {
        "excluded": score < 15,
        "relevance_score": score,
        "relevance_level": level,
        "reasons": reasons or ["基于运行期观测保留"],
        "is_common_infra": is_common_infra,
        "infra_category": infra_category,
    }
