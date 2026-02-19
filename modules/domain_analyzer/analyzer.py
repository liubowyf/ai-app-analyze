"""Master Domain Analyzer for identifying primary control servers."""
import logging
import re
import math
from typing import List, Dict, Optional
from dataclasses import dataclass
from collections import Counter

from modules.traffic_monitor import NetworkRequest

logger = logging.getLogger(__name__)


@dataclass
class DomainScore:
    """Domain scoring result."""
    domain: str
    score: float
    request_count: int
    post_count: int
    has_sensitive_data: bool
    is_private_ip: bool
    reasons: List[str]


@dataclass
class MasterDomain:
    """Identified master domain."""
    domain: str
    ip: Optional[str]
    score: float
    confidence: str  # high, medium, low
    evidence: List[str]
    sample_requests: List[Dict]


class MasterDomainAnalyzer:
    """Analyze network requests to identify master control domains."""

    # Known CDN patterns
    CDN_PATTERNS = [
        r'\.cdn\.',
        r'\.cloudfront\.net$',
        r'\.akamai\.',
        r'\.akamaized\.net$',
        r'\.fastly\.net$',
        r'cdn\.',
        r'-cdn\.',
        r'\.cloudflare\.com$',
    ]

    # Known ad/tracking domains
    AD_DOMAINS = [
        r'\.googlesyndication\.com$',
        r'\.doubleclick\.net$',
        r'\.googleadservices\.com$',
        r'\.facebook\.com/tr$',
        r'\.umeng\.com$',
        r'\.data\.cn$',
    ]

    # Known analytics domains
    ANALYTICS_DOMAINS = [
        r'\.google-analytics\.com$',
        r'\.googletagmanager\.com$',
        r'\.mixpanel\.com$',
        r'\.amplitude\.com$',
        r'\.sensorsdata\.cn$',
    ]

    # Sensitive data patterns in requests
    SENSITIVE_PATTERNS = [
        r'user_id',
        r'userid',
        r'device_id',
        r'deviceid',
        r'imei',
        r'mac',
        r'token',
        r'auth',
        r'password',
        r'phone',
        r'email',
        r'location',
        r'latitude',
        r'longitude',
    ]

    def __init__(self):
        """Initialize analyzer."""
        self.cdn_regex = [re.compile(p, re.IGNORECASE) for p in self.CDN_PATTERNS]
        self.ad_regex = [re.compile(p, re.IGNORECASE) for p in self.AD_DOMAINS]
        self.analytics_regex = [re.compile(p, re.IGNORECASE) for p in self.ANALYTICS_DOMAINS]
        self.sensitive_regex = [re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATTERNS]

    def is_cdn_domain(self, domain: str) -> bool:
        """Check if domain is a CDN."""
        for pattern in self.cdn_regex:
            if pattern.search(domain):
                return True
        return False

    def is_ad_domain(self, domain: str) -> bool:
        """Check if domain is ad/tracking."""
        for pattern in self.ad_regex:
            if pattern.search(domain):
                return True
        return False

    def is_analytics_domain(self, domain: str) -> bool:
        """Check if domain is analytics service."""
        for pattern in self.analytics_regex:
            if pattern.search(domain):
                return True
        return False

    def is_whitelisted(self, domain: str) -> bool:
        """Check if domain is in whitelist (CDN/AD/Analytics)."""
        return (
            self.is_cdn_domain(domain) or
            self.is_ad_domain(domain) or
            self.is_analytics_domain(domain)
        )

    def is_private_ip(self, ip: str) -> bool:
        """Check if IP is private/internal."""
        if not ip:
            return False
        private_patterns = [
            r'^10\.',
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',
            r'^192\.168\.',
            r'^127\.',
            r'^169\.254\.',
        ]
        for pattern in private_patterns:
            if re.match(pattern, ip):
                return True
        return False

    def contains_sensitive_data(self, request: NetworkRequest) -> bool:
        """Check if request contains sensitive data."""
        # Check request body
        if request.request_body:
            for pattern in self.sensitive_regex:
                if pattern.search(request.request_body):
                    return True

        # Check URL
        for pattern in self.sensitive_regex:
            if pattern.search(request.url):
                return True

        # Check headers
        for header, value in request.request_headers.items():
            for pattern in self.sensitive_regex:
                if pattern.search(header) or pattern.search(str(value)):
                    return True

        return False

    def calculate_domain_score(self, domain: str, requests: List[NetworkRequest]) -> DomainScore:
        """
        Calculate business importance score for a domain.

        Scoring factors:
        - POST/PUT requests: +20 each
        - Contains sensitive data: +30
        - Non-standard port: +10
        - Private IP: +50
        - Request frequency: +log(count) * 2
        - Non-HTTPS: +15
        """
        domain_requests = [r for r in requests if r.host == domain]

        if not domain_requests:
            return DomainScore(domain, 0, 0, 0, False, False, [])

        score = 0
        reasons = []
        post_count = 0
        has_sensitive = False
        is_private = False

        # Count POST/PUT requests
        for req in domain_requests:
            if req.method in ["POST", "PUT"]:
                score += 20
                post_count += 1

        if post_count > 0:
            reasons.append(f"{post_count} data submission requests")

        # Check for sensitive data
        for req in domain_requests:
            if self.contains_sensitive_data(req):
                score += 30
                has_sensitive = True
                reasons.append("Contains sensitive user data")
                break

        # Check for non-standard ports
        for req in domain_requests:
            if req.port not in [80, 443]:
                score += 10
                reasons.append(f"Uses non-standard port {req.port}")
                break

        # Check for private IP
        for req in domain_requests:
            if req.ip and self.is_private_ip(req.ip):
                score += 50
                is_private = True
                reasons.append("Uses private/internal IP")
                break

        # Check for non-HTTPS
        for req in domain_requests:
            if req.scheme != "https":
                score += 15
                reasons.append("Uses non-encrypted connection")
                break

        # Request frequency (logarithmic)
        freq_score = math.log(len(domain_requests) + 1) * 2
        score += freq_score

        return DomainScore(
            domain=domain,
            score=score,
            request_count=len(domain_requests),
            post_count=post_count,
            has_sensitive_data=has_sensitive,
            is_private_ip=is_private,
            reasons=reasons
        )

    def analyze(self, network_requests: List[NetworkRequest]) -> List[MasterDomain]:
        """
        Analyze network requests to identify master control domains.

        Args:
            network_requests: List of captured network requests

        Returns:
            List of identified master domains (top 5)
        """
        logger.info(f"Analyzing {len(network_requests)} network requests")

        # Get unique domains
        domains = list(set(r.host for r in network_requests))
        logger.info(f"Found {len(domains)} unique domains")

        # Filter whitelisted domains
        business_domains = [d for d in domains if not self.is_whitelisted(d)]
        logger.info(f"Business domains after filtering: {len(business_domains)}")

        # Score each domain
        domain_scores = []
        for domain in business_domains:
            score = self.calculate_domain_score(domain, network_requests)
            domain_scores.append(score)

        # Sort by score
        domain_scores.sort(key=lambda x: x.score, reverse=True)

        # Take top 5
        master_domains = []
        for ds in domain_scores[:5]:
            # Get sample requests
            sample_requests = [
                {
                    "url": r.url,
                    "method": r.method,
                    "response_code": r.response_code,
                }
                for r in network_requests
                if r.host == ds.domain
            ][:3]

            # Determine confidence
            if ds.score >= 50:
                confidence = "high"
            elif ds.score >= 20:
                confidence = "medium"
            else:
                confidence = "low"

            # Get IP
            ip = None
            for r in network_requests:
                if r.host == ds.domain and r.ip:
                    ip = r.ip
                    break

            master_domains.append(MasterDomain(
                domain=ds.domain,
                ip=ip,
                score=ds.score,
                confidence=confidence,
                evidence=ds.reasons,
                sample_requests=sample_requests
            ))

        logger.info(f"Identified {len(master_domains)} master domains")
        return master_domains

    def generate_domain_report(self, master_domains: List[MasterDomain]) -> Dict:
        """Generate domain analysis report data."""
        return {
            "master_domains": [
                {
                    "domain": md.domain,
                    "ip": md.ip,
                    "score": md.score,
                    "confidence": md.confidence,
                    "evidence": md.evidence,
                    "sample_requests": md.sample_requests,
                }
                for md in master_domains
            ],
            "summary": {
                "total_master_domains": len(master_domains),
                "high_confidence": len([md for md in master_domains if md.confidence == "high"]),
                "medium_confidence": len([md for md in master_domains if md.confidence == "medium"]),
                "low_confidence": len([md for md in master_domains if md.confidence == "low"]),
            }
        }
