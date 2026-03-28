# Тесты детектора угроз: SSH brute-force, веб-атаки и сканирование портов
import pytest
from security.detector import Detector, detect_port_scan, detect_ssh_bruteforce, detect_web_attack
from config import load_config

@pytest.fixture
def detector(test_config_path):
    config = load_config(test_config_path)
    return Detector(config.security)

def test_ssh_brute_force_below_threshold(detector):
    results = []
    for i in range(2):
        result = detector.check_log({
            "source": "auth",
            "line": f"Failed password for root from 10.0.0.1 port 22 ssh2",
            "file": "/var/log/auth.log"
        })
        if result:
            results.append(result)
    assert len(results) == 0

def test_ssh_brute_force_above_threshold(detector):
    results = []
    for i in range(3):  # threshold is 3 in test config
        result = detector.check_log({
            "source": "auth",
            "line": "Failed password for root from 10.0.0.1 port 22 ssh2",
            "file": "/var/log/auth.log"
        })
        if result:
            results.append(result)
    assert len(results) == 1
    assert results[0]["type"] == "ssh_brute_force"
    assert results[0]["severity"] == "high"
    assert results[0]["source_ip"] == "10.0.0.1"

def test_ssh_different_ips_no_trigger(detector):
    results = []
    for i in range(5):
        result = detector.check_log({
            "source": "auth",
            "line": f"Failed password for root from 10.0.0.{i} port 22 ssh2",
            "file": "/var/log/auth.log"
        })
        if result:
            results.append(result)
    assert len(results) == 0

def test_sqli_detection(detector):
    result = detector.check_log({
        "source": "nginx",
        "line": '10.0.0.5 - - "GET /page?id=1 OR 1=1-- HTTP/1.1" 200',
        "file": "/var/log/nginx/access.log"
    })
    assert result is not None
    assert result["type"] == "sqli"

def test_xss_detection(detector):
    result = detector.check_log({
        "source": "nginx",
        "line": '10.0.0.5 - - "GET /search?q=<script>alert(1)</script> HTTP/1.1" 200',
        "file": "/var/log/nginx/access.log"
    })
    assert result is not None
    assert result["type"] == "xss"

def test_path_traversal_detection(detector):
    result = detector.check_log({
        "source": "nginx",
        "line": '10.0.0.5 - - "GET /../../etc/passwd HTTP/1.1" 200',
        "file": "/var/log/nginx/access.log"
    })
    assert result is not None
    assert result["type"] == "path_traversal"

def test_normal_log_no_detection(detector):
    result = detector.check_log({
        "source": "auth",
        "line": "Accepted publickey for user from 10.0.0.1 port 22 ssh2",
        "file": "/var/log/auth.log"
    })
    assert result is None


def test_port_scan_detection_from_firewall_logs(detector):
    result = None
    for port in (22, 80, 443, 8080):
        result = detector.check_log({
            "source": "firewall",
            "line": (
                "kernel: [UFW BLOCK] IN=eth0 OUT= MAC=aa SRC=10.0.0.8 DST=10.0.0.2 "
                f"LEN=60 TOS=0x00 PREC=0x00 TTL=54 ID=1 DF PROTO=TCP SPT=40000 DPT={port} WINDOW=1024"
            ),
            "file": "/var/log/ufw.log",
        })
    assert result is not None
    assert result["type"] == "port_scan"
    assert result["source_ip"] == "10.0.0.8"


def test_syslog_firewall_marker_can_trigger_port_scan(detector):
    result = None
    for port in (111, 135, 139, 445):
        result = detector.check_log({
            "source": "syslog",
            "line": (
                "kernel: [123.456] IN=eth0 OUT= MAC=aa SRC=10.0.0.11 DST=10.0.0.2 "
                f"PROTO=TCP SPT=50000 DPT={port}"
            ),
            "file": "/var/log/kern.log",
        })
    assert result is not None
    assert result["type"] == "port_scan"


def test_detect_ssh_bruteforce_as_pure_function():
    ssh_attempts: dict[str, list[int]] = {}
    result = None
    for ts in (100, 110, 120):
        result = detect_ssh_bruteforce(
            "Failed password for root from 10.0.0.9 port 22 ssh2",
            ssh_attempts=ssh_attempts,
            threshold=3,
            window=60,
            now=ts,
        )
    assert result is not None
    assert result["type"] == "ssh_brute_force"
    assert result["source_ip"] == "10.0.0.9"


def test_detect_web_attack_as_pure_function():
    result = detect_web_attack(
        '10.0.0.5 - - "GET /../../etc/passwd HTTP/1.1" 200',
        enabled=True,
    )
    assert result is not None
    assert result["type"] == "path_traversal"


def test_detect_port_scan_as_pure_function():
    scan_attempts: dict[str, list[tuple[int, int]]] = {}
    result = None
    for ts, port in ((100, 22), (110, 80), (120, 443), (130, 8080)):
        result = detect_port_scan(
            f"kernel: [UFW BLOCK] IN=eth0 SRC=10.0.0.12 DST=10.0.0.2 PROTO=TCP SPT=41000 DPT={port}",
            scan_attempts=scan_attempts,
            enabled=True,
            threshold=4,
            window=120,
            now=ts,
        )
    assert result is not None
    assert result["type"] == "port_scan"
    assert result["source_ip"] == "10.0.0.12"


def test_detect_port_scan_with_nftables_style_line():
    scan_attempts: dict[str, list[tuple[int, int]]] = {}
    result = None
    for ts, port in ((100, 22), (110, 80), (120, 443), (130, 8080)):
        result = detect_port_scan(
            f"nftables: IN=eth0 OUT= SRC=10.0.0.13 DST=10.0.0.2 PROTO=TCP DSTPORT={port}",
            scan_attempts=scan_attempts,
            enabled=True,
            threshold=4,
            window=120,
            now=ts,
        )
    assert result is not None
    assert result["type"] == "port_scan"


def test_detect_port_scan_with_iptables_log_prefix():
    scan_attempts: dict[str, list[tuple[int, int]]] = {}
    result = None
    for ts, port in ((100, 21), (110, 23), (120, 25), (130, 53)):
        result = detect_port_scan(
            f"iptables: from 10.0.0.14 proto tcp to port {port}",
            scan_attempts=scan_attempts,
            enabled=True,
            threshold=4,
            window=120,
            now=ts,
        )
    assert result is not None
    assert result["type"] == "port_scan"


def test_detect_port_scan_with_nullius_logging_prefix():
    scan_attempts: dict[str, list[tuple[int, int]]] = {}
    result = None
    for ts, port in ((100, 22), (110, 80), (120, 443), (130, 8080)):
        result = detect_port_scan(
            f"kernel: [100.000] NULLIUS_PORTSCAN IN=eth0 OUT= SRC=10.0.0.15 DST=10.0.0.2 PROTO=TCP SPT=51000 DPT={port}",
            scan_attempts=scan_attempts,
            enabled=True,
            threshold=4,
            window=120,
            now=ts,
        )
    assert result is not None
    assert result["type"] == "port_scan"
    assert result["source_ip"] == "10.0.0.15"
