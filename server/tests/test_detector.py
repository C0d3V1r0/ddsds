# - Тесты детектора угроз: SSH brute-force, веб-атаки
import pytest
from security.detector import Detector
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
