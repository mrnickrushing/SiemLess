"""Tests for the Windows event log parser module."""
import pytest
from app.services.parsers.windows import parse_windows_event


def test_4625_logon_failure(windows_4625):
    result = parse_windows_event(windows_4625)
    assert result["log_type"] == "windows"
    assert result["action"] == "failed"
    assert result["severity"] == "medium"
    assert result["parsed_fields"]["event"] == "logon_failure"


def test_4624_logon_success(windows_4624):
    result = parse_windows_event(windows_4624)
    assert result["action"] == "success"
    assert result["parsed_fields"]["event"] == "logon_success"


def test_4720_account_created(windows_4720):
    result = parse_windows_event(windows_4720)
    assert result["severity"] == "high"
    assert result["parsed_fields"]["event"] == "user_account_created"
    assert result["category"] == "system"


def test_4732_group_member_added(windows_4732):
    result = parse_windows_event(windows_4732)
    assert result["severity"] == "high"
    assert result["parsed_fields"]["event"] == "group_member_added"


def test_generic_windows_event():
    result = parse_windows_event("Some unrecognised windows log message")
    assert result["log_type"] == "windows"
    assert result["parsed_fields"]["event"] == "windows_generic"
