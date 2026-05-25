"""Tests for the SSH log parser module."""
import pytest
from app.services.parsers.ssh import parse_ssh_log


def test_failed_password(ssh_failed_password):
    result = parse_ssh_log(ssh_failed_password)
    assert result["log_type"] == "ssh"
    assert result["action"] == "failed"
    assert result["source_ip"] == "203.0.113.42"
    assert result["user"] == "root"
    assert result["source_port"] == 54321
    assert result["parsed_fields"]["event"] == "failed_auth"


def test_failed_invalid_user(ssh_failed_invalid_user):
    result = parse_ssh_log(ssh_failed_invalid_user)
    assert result["action"] == "failed"
    assert result["user"] == "deploy"
    assert result["source_ip"] == "198.51.100.7"


def test_accepted_publickey(ssh_accepted):
    result = parse_ssh_log(ssh_accepted)
    assert result["action"] == "success"
    assert result["user"] == "alice"
    assert result["source_ip"] == "10.0.0.5"
    assert result["parsed_fields"]["event"] == "accepted_auth"
    assert result["parsed_fields"]["auth_method"] == "publickey"


def test_invalid_user(ssh_invalid_user):
    result = parse_ssh_log(ssh_invalid_user)
    assert result["action"] == "failed"
    assert result["user"] == "testuser"
    assert result["source_ip"] == "198.51.100.99"
    assert result["parsed_fields"]["event"] == "invalid_user"


def test_max_auth_exceeded(ssh_max_auth):
    result = parse_ssh_log(ssh_max_auth)
    assert result["action"] == "failed"
    assert result["source_ip"] == "203.0.113.1"
    assert result["parsed_fields"]["event"] == "max_auth_exceeded"


def test_category_is_authentication(ssh_failed_password):
    result = parse_ssh_log(ssh_failed_password)
    assert result["category"] == "authentication"


def test_unknown_ssh_message():
    result = parse_ssh_log("sshd: server listening on 0.0.0.0 port 22")
    assert result["log_type"] == "ssh"
    assert result["parsed_fields"]["event"] == "ssh_generic"
    assert result.get("action") is None
