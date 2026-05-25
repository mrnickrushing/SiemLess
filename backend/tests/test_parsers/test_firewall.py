"""Tests for the iptables/firewall log parser module."""
import pytest
from app.services.parsers.firewall import parse_iptables_log


def test_drop_action(iptables_drop):
    result = parse_iptables_log(iptables_drop)
    assert result["log_type"] == "firewall"
    assert result["action"] == "deny"
    assert result["source_ip"] == "203.0.113.5"
    assert result["destination_ip"] == "10.0.0.1"
    assert result["source_port"] == 45678
    assert result["destination_port"] == 22
    assert result["category"] == "network"


def test_accept_action(iptables_accept):
    result = parse_iptables_log(iptables_accept)
    assert result["action"] == "allow"
    assert result["source_ip"] == "10.0.0.5"


def test_no_ports(iptables_no_ports):
    result = parse_iptables_log(iptables_no_ports)
    assert result["source_port"] is None
    assert result["destination_port"] is None
    assert result["source_ip"] == "1.2.3.4"
    assert result["destination_ip"] == "5.6.7.8"


def test_parsed_fields_present(iptables_drop):
    result = parse_iptables_log(iptables_drop)
    pf = result["parsed_fields"]
    assert "protocol" in pf
    assert "in_iface" in pf
