"""Tests for the CEF log parser module."""
import pytest
from app.services.parsers.cef import parse_cef


def test_standard_cef(cef_standard):
    result = parse_cef(cef_standard)
    assert result["log_type"] == "firewall"
    assert result["source_ip"] == "203.0.113.1"
    assert result["destination_ip"] == "10.0.0.1"
    assert result["source_port"] == 12345
    assert result["destination_port"] == 443
    assert result["action"] == "block"
    # severity 7 → high
    assert result["severity"] == "high"


def test_low_severity(cef_low_severity):
    result = parse_cef(cef_low_severity)
    # severity 2 → low
    assert result["severity"] == "low"


def test_no_extension(cef_no_extension):
    result = parse_cef(cef_no_extension)
    assert result["log_type"] == "firewall"
    assert result["source_ip"] is None
    assert result["destination_ip"] is None


def test_malformed_cef():
    result = parse_cef("this is not cef at all")
    assert result["log_type"] == "generic"
    assert result["message"] == "this is not cef at all"
