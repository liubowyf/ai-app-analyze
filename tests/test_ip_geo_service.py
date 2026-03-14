from __future__ import annotations


class _FakeClient:
    def __init__(self):
        self.ips: list[str] = []

    def lookup_ip(self, ip: str) -> str | None:
        self.ips.append(ip)
        if ip == "8.8.8.8":
            return "美国 加利福尼亚"
        if ip == "1.1.1.1":
            return "澳大利亚"
        raise RuntimeError("boom")


def test_resolve_ip_locations_skips_private_and_invalid_ips():
    from modules.ip_geo.service import resolve_ip_locations_with_client

    client = _FakeClient()

    result = resolve_ip_locations_with_client(
        ["8.8.8.8", "192.168.1.2", "not-an-ip", "1.1.1.1"],
        client=client,
        max_concurrency=3,
    )

    assert result == {
        "8.8.8.8": "美国 加利福尼亚",
        "1.1.1.1": "澳大利亚",
    }
    assert client.ips == ["8.8.8.8", "1.1.1.1"]


def test_resolve_ip_locations_clamps_max_concurrency_to_30():
    from modules.ip_geo.service import clamp_ip_geo_concurrency

    assert clamp_ip_geo_concurrency(0) == 1
    assert clamp_ip_geo_concurrency(8) == 8
    assert clamp_ip_geo_concurrency(31) == 30


def test_resolve_ip_locations_ignores_lookup_failures():
    from modules.ip_geo.service import resolve_ip_locations_with_client

    class _FailingClient(_FakeClient):
        def lookup_ip(self, ip: str) -> str | None:
            if ip == "9.9.9.9":
                raise RuntimeError("down")
            return super().lookup_ip(ip)

    result = resolve_ip_locations_with_client(
        ["9.9.9.9", "8.8.8.8"],
        client=_FailingClient(),
        max_concurrency=2,
    )

    assert result == {"8.8.8.8": "美国 加利福尼亚"}
