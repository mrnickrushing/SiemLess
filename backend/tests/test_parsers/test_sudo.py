"""Tests for the sudo log parser module."""
import pytest
from app.services.parsers.sudo import parse_sudo_log


def test_root_escalation(sudo_root):
    result = parse_sudo_log(sudo_root)
    assert result["log_type"] == "sudo"
    assert result["user"] == "alice"
    assert result["severity"] == "high"
    assert result["action"] == "success"
    assert result["parsed_fields"]["run_as"] == "root"
    assert result["parsed_fields"]["event"] == "privilege_escalation"
    assert "/bin/bash" in result["parsed_fields"]["command"]


def test_non_root(sudo_non_root):
    result = parse_sudo_log(sudo_non_root)
    assert result["user"] == "bob"
    assert result["severity"] == "medium"
    assert result["parsed_fields"]["run_as"] == "www-data"
    assert result["parsed_fields"]["event"] == "sudo_command"


def test_malformed_returns_partial():
    result = parse_sudo_log("this is not a sudo log")
    assert result["log_type"] == "sudo"
    assert result["category"] == "system"
