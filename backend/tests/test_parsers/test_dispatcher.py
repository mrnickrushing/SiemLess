"""Tests for the LogParser dispatcher: format detection and normalize()."""
import pytest
from datetime import datetime, timezone
from app.services.parsers.dispatcher import LogParser


@pytest.fixture
def parser():
    return LogParser()


def test_detect_json(parser, json_basic):
    assert parser.detect_format(json_basic) == "json"


def test_detect_cef(parser, cef_standard):
    assert parser.detect_format(cef_standard) == "cef"


def test_detect_plain(parser):
    assert parser.detect_format("hello world") == "plain"


def test_parse_json_roundtrip(parser, json_basic):
    parsed = parser.parse(json_basic, log_source="api")
    assert parsed["log_source"] == "api"
    assert parsed["raw_log"] == json_basic
    assert parsed["source_ip"] == "1.2.3.4"


def test_parse_cef_roundtrip(parser, cef_standard):
    parsed = parser.parse(cef_standard, log_source="syslog")
    assert parsed["log_type"] == "firewall"
    assert parsed["raw_log"] == cef_standard


def test_classify_severity_critical(parser):
    parsed = {"message": "ransomware detected on host", "log_type": "generic"}
    assert parser.classify_severity(parsed) == "critical"


def test_classify_severity_ssh_failed(parser, ssh_failed_password):
    from app.services.parsers.ssh import parse_ssh_log
    parsed = parse_ssh_log(ssh_failed_password)
    assert parser.classify_severity(parsed) == "medium"


def test_extract_tags_has_src_ip(parser):
    parsed = {"log_type": "ssh", "action": "failed", "source_ip": "1.2.3.4",
              "parsed_fields": {"event": "failed_auth"}, "severity": "medium"}
    tags = parser.extract_tags(parsed)
    assert "ssh" in tags
    assert "failed" in tags
    assert "has_src_ip" in tags


def test_normalize_returns_schema(parser, json_basic):
    parsed = parser.parse(json_basic)
    event = parser.normalize(parsed)
    assert event.log_source == "api"
    assert isinstance(event.timestamp, datetime)
    assert event.source_ip == "1.2.3.4"


def test_normalize_fallback_timestamp(parser):
    parsed = {"log_type": "generic", "message": "no timestamp here", "log_source": "api"}
    event = parser.normalize(parsed)
    assert isinstance(event.timestamp, datetime)
    assert event.timestamp.tzinfo is not None
