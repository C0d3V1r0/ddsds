# server/tests/test_responder.py
import pytest
from security.responder import Responder

@pytest.fixture
def responder():
    return Responder(auto_block=True)

def test_low_severity_logs_only(responder):
    action = responder.decide({"severity": "low", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"

def test_medium_severity_logs(responder):
    action = responder.decide({"severity": "medium", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"

def test_high_severity_blocks(responder):
    action = responder.decide({"severity": "high", "source_ip": "10.0.0.1", "type": "ssh_brute_force"})
    assert action["action"] == "block"
    assert action["ip"] == "10.0.0.1"

def test_critical_severity_blocks(responder):
    action = responder.decide({"severity": "critical", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "block"
    assert action["highlight"] is True

def test_high_severity_no_block_when_disabled(responder):
    r = Responder(auto_block=False)
    action = r.decide({"severity": "high", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"

def test_no_block_without_ip(responder):
    action = responder.decide({"severity": "high", "source_ip": "", "type": "test"})
    assert action["action"] == "log"
