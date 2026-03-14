from __future__ import annotations

from unittest.mock import Mock

def test_aliyun_ip_geo_client_normalizes_location_text():
    from modules.ip_geo.aliyun_client import normalize_aliyun_ip_location

    payload = {
        "province": "上海",
        "city": "上海",
        "isp": "电信",
        "country": "中国",
    }

    assert normalize_aliyun_ip_location(payload) == "中国 上海 电信"


def test_aliyun_ip_geo_client_accepts_nested_data_payload():
    from modules.ip_geo.aliyun_client import extract_location_payload

    response = {
        "showapi_res_body": {
            "country": "中国",
            "region": "广东",
            "city": "深圳",
            "isp": "联通",
        }
    }

    payload = extract_location_payload(response)

    assert payload["country"] == "中国"
    assert payload["region"] == "广东"


def test_aliyun_ip_geo_client_posts_json_with_nonce_and_timestamp(monkeypatch):
    from modules.ip_geo.aliyun_client import AliyunIpGeoClient

    fake_client = Mock()
    fake_response = Mock()
    fake_response.json.return_value = {"country": "中国", "province": "上海"}
    fake_response.raise_for_status.return_value = None
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=None)
    fake_client.post.return_value = fake_response

    monkeypatch.setattr("modules.ip_geo.aliyun_client.httpx.Client", Mock(return_value=fake_client))
    monkeypatch.setattr("modules.ip_geo.aliyun_client.uuid.uuid4", lambda: "demo-nonce")
    monkeypatch.setattr("modules.ip_geo.aliyun_client.time.time", lambda: 1773497498.428)

    client = AliyunIpGeoClient(base_url="http://10.16.135.135:9093/openapi/ip/location")
    location = client.lookup_ip("199.96.58.105")

    assert location == "中国 上海"
    _, kwargs = fake_client.post.call_args
    assert kwargs["json"] == {"ip": "199.96.58.105"}
    assert kwargs["headers"]["Nonce"] == "demo-nonce"
    assert kwargs["headers"]["Timestamp"] == "1773497498428"
    assert kwargs["headers"]["Content-Type"] == "application/json"
