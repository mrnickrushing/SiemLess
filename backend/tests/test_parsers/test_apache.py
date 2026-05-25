"""Tests for the Apache/Nginx log parser module."""
import pytest
from app.services.parsers.apache import parse_apache_log, parse_nginx_log


def test_200_is_allow(apache_200):
    result = parse_apache_log(apache_200)
    assert result["log_type"] == "apache"
    assert result["action"] == "allow"
    assert result["source_ip"] == "192.168.1.1"
    assert result["parsed_fields"]["status_code"] == 200
    assert result["severity"] == "low"


def test_401_is_deny_medium(apache_401):
    result = parse_apache_log(apache_401)
    assert result["action"] == "deny"
    assert result["parsed_fields"]["status_code"] == 401
    assert result["severity"] == "medium"
    assert result["user"] == "bob"


def test_403_is_deny_medium(apache_403):
    result = parse_apache_log(apache_403)
    assert result["action"] == "deny"
    assert result["parsed_fields"]["status_code"] == 403
    assert result["severity"] == "medium"


def test_500_is_medium(apache_500):
    result = parse_apache_log(apache_500)
    assert result["action"] == "deny"
    assert result["parsed_fields"]["status_code"] == 500
    assert result["severity"] == "medium"


def test_nginx_log_type(apache_200):
    result = parse_nginx_log(apache_200)
    assert result["log_type"] == "nginx"
    assert result["action"] == "allow"


def test_malformed_returns_generic():
    result = parse_apache_log("this is not an apache log line")
    assert result["log_type"] == "apache"
    assert result["message"] == "this is not an apache log line"
    assert "parsed_fields" not in result


def test_dash_user_is_none(apache_200):
    result = parse_apache_log(apache_200)
    assert result.get("user") is None
