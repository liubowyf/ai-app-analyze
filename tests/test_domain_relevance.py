from __future__ import annotations

from modules.domain_intelligence.relevance import (
    build_app_identity_tokens,
    load_common_network_indicator_seed,
    score_domain_candidate,
)


def test_score_domain_candidate_marks_app_related_domain_high_confidence():
    result = score_domain_candidate(
        {
            "domain": "api.alpha-wallet.example",
            "ip": "1.1.1.1",
            "hit_count": 7,
            "source_types": ["dns", "ssl", "http"],
            "confidence": "high",
        },
        app_tokens=build_app_identity_tokens("Alpha Wallet", "com.demo.alpha.wallet"),
        indicators=load_common_network_indicator_seed(),
    )

    assert result["excluded"] is False
    assert result["relevance_level"] == "high"
    assert any("应用标识词" in reason for reason in result["reasons"])


def test_score_domain_candidate_demotes_common_sdk_domain():
    result = score_domain_candidate(
        {
            "domain": "sdk-analytics.example",
            "ip": "3.3.3.3",
            "hit_count": 9,
            "source_types": ["dns", "ssl", "http"],
            "confidence": "high",
        },
        app_tokens=build_app_identity_tokens("Alpha Wallet", "com.demo.alpha.wallet"),
        indicators=load_common_network_indicator_seed(),
    )

    assert result["is_common_infra"] is True
    assert result["excluded"] is True
    assert any("已降级" in reason for reason in result["reasons"])


def test_score_domain_candidate_demotes_openinstall_domain():
    result = score_domain_candidate(
        {
            "domain": "stat2-zdd4r1.openinstall.com",
            "ip": "123.56.28.231",
            "hit_count": 14,
            "source_types": ["dns", "ssl"],
            "confidence": "observed",
        },
        app_tokens=build_app_identity_tokens("陌生应用", "com.demo.random"),
        indicators=load_common_network_indicator_seed(),
    )

    assert result["is_common_infra"] is True
    assert result["excluded"] is True
    assert result["relevance_level"] == "low"
    assert any("已降级" in reason for reason in result["reasons"])


def test_score_domain_candidate_excludes_android_system_domain():
    result = score_domain_candidate(
        {
            "domain": "connectivitycheck.gstatic.com",
            "ip": "142.250.1.1",
            "hit_count": 2,
            "source_types": ["dns"],
            "confidence": "medium",
        },
        app_tokens=build_app_identity_tokens("Alpha Wallet", "com.demo.alpha.wallet"),
        indicators=load_common_network_indicator_seed(),
    )

    assert result["is_common_infra"] is True
    assert result["excluded"] is True
    assert any("排除" in reason for reason in result["reasons"])


def test_score_domain_candidate_demotes_umeng_domain():
    result = score_domain_candidate(
        {
            "domain": "errnewlog.umeng.com",
            "ip": "42.120.44.11",
            "hit_count": 5,
            "source_types": ["dns", "http"],
            "confidence": "observed",
        },
        app_tokens=build_app_identity_tokens("陌生应用", "com.demo.random"),
        indicators=load_common_network_indicator_seed(),
    )

    assert result["is_common_infra"] is True
    assert result["excluded"] is True
    assert result["infra_category"] in {"analytics", "sdk", "crash"}
