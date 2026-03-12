from modules.redroid_remote.traffic_parser import parse_zeek_outputs


CONN_LOG = """#separator \\x09
#set_separator	,
#empty_field	(empty)
#unset_field	-
#path	conn
#open	2026-03-12-00-00-00
1700000000.0	uid1	172.17.0.2	54321	1.1.1.1	443	tcp	http	0.4	123	456	SF	-	-	0	ShADadf	10	800	11	900	-
1700000005.0	uid2	172.17.0.2	54322	2.2.2.2	443	tcp	ssl	0.8	222	333	SF	-	-	0	ShADadf	12	900	13	1000	-
#close	2026-03-12-00-00-02
"""

DNS_LOG = """#separator \\x09
#set_separator	,
#empty_field	(empty)
#unset_field	-
#path	dns
#open	2026-03-12-00-00-00
1700000000.1	uid1	172.17.0.2	53000	1.1.1.1	53	udp	1234	example.com	1	A	0	NOERROR	F	F	F	F	1.1.1.1	60.0	F
1700000005.1	uid2	172.17.0.2	53001	2.2.2.2	53	udp	1235	api.example.com	1	A	0	NOERROR	F	F	F	F	2.2.2.2	60.0	F
#close	2026-03-12-00-00-02
"""

SSL_LOG = """#separator \\x09
#set_separator	,
#empty_field	(empty)
#unset_field	-
#path	ssl
#open	2026-03-12-00-00-00
1700000000.2	uid1	172.17.0.2	54321	1.1.1.1	443	TLSv13	TLS_AES_128_GCM_SHA256	example.com	F	-	-	-
1700000005.2	uid2	172.17.0.2	54322	2.2.2.2	443	TLSv13	TLS_AES_128_GCM_SHA256	api.example.com	F	-	-	-
#close	2026-03-12-00-00-02
"""

HTTP_LOG = """#separator \\x09
#set_separator	,
#empty_field	(empty)
#unset_field	-
#path	http
#open	2026-03-12-00-00-00
1700000000.3	uid1	172.17.0.2	54321	1.1.1.1	80	1	GET	example.com	/index.html	-	1.1	curl/8.0	-	-	200	OK	-	-	-	-	-	-	-
#close	2026-03-12-00-00-02
"""

TCPDUMP_LOG = """12:00:00.000001 IP 172.17.0.2.54321 > 10.16.150.4.3128: Flags [P.], seq 1:10, ack 1, win 512, length 9
CONNECT ztgja1.top:443 HTTP/1.1
Host: ztgja1.top:443
"""

TCPDUMP_DNS_AND_TCP_LOG = """13:46:44.042563 IP 172.17.0.2.24030 > 8.8.8.8.53: 16879+ A? connectivitycheck.gstatic.com. (47)
13:46:44.056732 IP 8.8.8.8.53 > 172.17.0.2.24030: 16879 1/0/0 A 220.181.174.162 (48)
13:46:44.061630 IP 172.17.0.2.57758 > 199.16.158.9.443: Flags [S], seq 1777165769, win 65535, length 0
13:46:47.040201 IP 172.17.0.2.61270 > 8.8.8.8.53: 30856+ A? play.googleapis.com. (37)
13:46:47.228679 IP 8.8.8.8.53 > 172.17.0.2.61270: 30856 4/0/0 A 216.239.36.223, A 216.239.32.223, A 216.239.34.223, A 216.239.38.223 (101)
"""


def test_parse_zeek_outputs_builds_observations_and_domain_stats():
    parsed = parse_zeek_outputs(
        conn_log=CONN_LOG,
        dns_log=DNS_LOG,
        ssl_log=SSL_LOG,
        http_log=HTTP_LOG,
    )

    observations = parsed["observations"]
    domains = parsed["domains"]

    assert len(observations) >= 2
    assert {item["source_type"] for item in observations} >= {"conn", "dns", "ssl", "http"}
    assert any(item["domain"] == "example.com" and item["ip"] == "1.1.1.1" for item in observations)
    assert any(item["domain"] == "api.example.com" and item["ip"] == "2.2.2.2" for item in observations)

    assert domains[0]["domain"] == "example.com"
    assert domains[0]["ip_count"] == 1
    assert domains[0]["hit_count"] >= 2
    assert set(domains[0]["source_types"]) >= {"dns", "ssl", "http"}
    assert any(item["domain"] == "api.example.com" and item["hit_count"] >= 2 for item in domains)


def test_parse_zeek_outputs_can_fallback_to_tcpdump_text(monkeypatch):
    monkeypatch.setattr(
        "modules.redroid_remote.traffic_parser._resolve_domain_ips",
        lambda domain: ["203.0.113.10"] if domain == "ztgja1.top" else [],
    )

    parsed = parse_zeek_outputs(tcpdump_log=TCPDUMP_LOG)

    assert any(
        item["domain"] == "ztgja1.top"
        and item["ip"] == "203.0.113.10"
        and item["source_type"] == "connect"
        for item in parsed["observations"]
    )
    assert any(item["domain"] == "ztgja1.top" and item["hit_count"] >= 1 for item in parsed["domains"])


def test_parse_zeek_outputs_extracts_dns_and_tcp_from_tcpdump_text():
    parsed = parse_zeek_outputs(tcpdump_log=TCPDUMP_DNS_AND_TCP_LOG)

    observations = parsed["observations"]
    domains = parsed["domains"]

    assert any(
        item["domain"] == "connectivitycheck.gstatic.com"
        and item["ip"] == "220.181.174.162"
        and item["source_type"] == "dns"
        for item in observations
    )
    assert any(
        item["domain"] == "play.googleapis.com"
        and item["ip"] == "216.239.36.223"
        and item["source_type"] == "dns"
        for item in observations
    )
    assert any(
        item["domain"] is None
        and item["ip"] == "199.16.158.9"
        and item["source_type"] == "tcp"
        for item in observations
    )
    connectivity_row = next(item for item in domains if item["domain"] == "connectivitycheck.gstatic.com")
    assert connectivity_row["hit_count"] >= 1
    assert connectivity_row["ip_count"] == 1
