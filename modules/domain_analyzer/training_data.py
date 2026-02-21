"""Training data generation for domain classification."""
import random
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class TrainingDataGenerator:
    """Generate labeled training data for domain classification."""

    # Example domains for each category
    MASTER_DOMAINS = [
        "api.example.com", "gateway.service.com", "backend.app.com",
        "server1.prod.net", "main.api.io", "core.service.org",
        "master.backend.com", "primary.api.net", "central.server.io",
        "control.service.com"
    ]

    CDN_DOMAINS = [
        "cdn.example.com", "static.cdn.net", "assets.cloudfront.net",
        "media.akamai.com", "cdn123.fastly.net", "cache.cloudflare.com",
        "img.cdn.com", "static.cloudflare.net", "delivery.cloudfront.net",
        "edge.akamai.net"
    ]

    TRACKER_DOMAINS = [
        "analytics.google.com", "track.example.com", "pixel.facebook.com",
        "stats.service.com", "telemetry.app.com", "metrics.system.com",
        "tracker.analytics.com", "beacon.ads.com", "collect.tracker.io",
        "insights.analytics.net"
    ]

    NORMAL_DOMAINS = [
        "www.example.com", "blog.service.com", "docs.app.com",
        "help.support.com", "info.site.com", "about.company.com",
        "news.portal.com", "forum.community.com", "shop.store.com",
        "contact.business.com"
    ]

    def generate_training_data(self, n_samples: int = 100) -> List[Dict]:
        """
        Generate labeled training data.

        Args:
            n_samples: Number of samples to generate

        Returns:
            List of dicts with 'domain' and 'label' keys
        """
        data = []

        # Generate variations of known domains
        categories = [
            (self.MASTER_DOMAINS, 'master'),
            (self.CDN_DOMAINS, 'cdn'),
            (self.TRACKER_DOMAINS, 'tracker'),
            (self.NORMAL_DOMAINS, 'normal'),
        ]

        samples_per_category = n_samples // len(categories)

        for domains, label in categories:
            for _ in range(samples_per_category):
                base_domain = random.choice(domains)
                variation = self._create_variation(base_domain)
                data.append({
                    'domain': variation,
                    'label': label
                })

        # Shuffle the data
        random.shuffle(data)

        return data

    def _create_variation(self, domain: str) -> str:
        """Create a variation of a domain."""
        variations = [
            domain,
            domain.replace('.com', '.net'),
            domain.replace('.com', '.io'),
            domain.replace('1', '2'),
            domain.replace('api', 'api2'),
            domain.replace('www', 'www2'),
            f"sub.{domain}",
            domain.replace('example', 'sample'),
        ]
        return random.choice(variations)
