"""Tests for the search query parser, security helpers, and rate limiter."""
import time
import pytest

from app.routers.search import (
    _T,
    _tokenize,
    _Parser,
    _build_search_clause,
    _escape_ilike,
    _redact,
    _check_rate_limit,
    _rate_attempts,
)
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenizer:
    def test_single_term(self):
        tokens = _tokenize("failed")
        assert tokens[0] == (_T.TERM, "failed")
        assert tokens[-1][0] == _T.EOF

    def test_and_keyword(self):
        tokens = _tokenize("a AND b")
        types = [t[0] for t in tokens]
        assert types == [_T.TERM, _T.AND, _T.TERM, _T.EOF]

    def test_or_keyword(self):
        tokens = _tokenize("a OR b")
        types = [t[0] for t in tokens]
        assert types == [_T.TERM, _T.OR, _T.TERM, _T.EOF]

    def test_not_keyword(self):
        tokens = _tokenize("NOT low")
        types = [t[0] for t in tokens]
        assert types == [_T.NOT, _T.TERM, _T.EOF]

    def test_keywords_are_case_insensitive(self):
        tokens = _tokenize("a and b or c not d")
        types = [t[0] for t in tokens]
        assert types == [_T.TERM, _T.AND, _T.TERM, _T.OR, _T.TERM, _T.NOT, _T.TERM, _T.EOF]

    def test_parentheses(self):
        tokens = _tokenize("(a OR b)")
        types = [t[0] for t in tokens]
        assert types == [_T.LPAREN, _T.TERM, _T.OR, _T.TERM, _T.RPAREN, _T.EOF]

    def test_quoted_term_with_spaces(self):
        tokens = _tokenize('"web server"')
        assert tokens[0] == (_T.TERM, "web server")

    def test_field_colon_value(self):
        tokens = _tokenize("severity:high")
        assert tokens[0] == (_T.TERM, "severity:high")

    def test_whitespace_stripped(self):
        tokens = _tokenize("  a   b  ")
        types = [t[0] for t in tokens]
        assert types == [_T.TERM, _T.TERM, _T.EOF]


# ---------------------------------------------------------------------------
# Parser — AST shape
# ---------------------------------------------------------------------------

class TestParser:
    def _parse(self, q: str) -> tuple:
        return _Parser(_tokenize(q)).parse()

    def test_single_term(self):
        ast = self._parse("ssh")
        assert ast == ("TERM", "ssh")

    def test_explicit_and(self):
        ast = self._parse("a AND b")
        assert ast == ("AND", ("TERM", "a"), ("TERM", "b"))

    def test_explicit_or(self):
        ast = self._parse("a OR b")
        assert ast == ("OR", ("TERM", "a"), ("TERM", "b"))

    def test_not(self):
        ast = self._parse("NOT a")
        assert ast == ("NOT", ("TERM", "a"))

    def test_implicit_and(self):
        # Two adjacent terms → AND
        ast = self._parse("failed ssh")
        assert ast == ("AND", ("TERM", "failed"), ("TERM", "ssh"))

    def test_and_binds_tighter_than_or(self):
        # "A AND B OR C" should be "(A AND B) OR C"
        ast = self._parse("A AND B OR C")
        assert ast[0] == "OR"
        assert ast[1] == ("AND", ("TERM", "A"), ("TERM", "B"))
        assert ast[2] == ("TERM", "C")

    def test_not_binds_tightest(self):
        # "NOT A AND B" should be "(NOT A) AND B"
        ast = self._parse("NOT A AND B")
        assert ast[0] == "AND"
        assert ast[1] == ("NOT", ("TERM", "A"))
        assert ast[2] == ("TERM", "B")

    def test_parentheses_override_precedence(self):
        # "A AND (B OR C)"
        ast = self._parse("A AND (B OR C)")
        assert ast[0] == "AND"
        assert ast[1] == ("TERM", "A")
        assert ast[2] == ("OR", ("TERM", "B"), ("TERM", "C"))

    def test_three_way_or(self):
        ast = self._parse("a OR b OR c")
        # Left-associative: ((a OR b) OR c)
        assert ast[0] == "OR"
        assert ast[1] == ("OR", ("TERM", "a"), ("TERM", "b"))
        assert ast[2] == ("TERM", "c")

    def test_mixed_precedence_complex(self):
        # severity:high AND (source_ip:10.0.0.1 OR source_ip:192.168.1.1)
        ast = self._parse("severity:high AND (source_ip:10.0.0.1 OR source_ip:192.168.1.1)")
        assert ast[0] == "AND"
        assert ast[1] == ("TERM", "severity:high")
        inner = ast[2]
        assert inner[0] == "OR"

    def test_parse_error_unmatched_paren(self):
        with pytest.raises(ValueError):
            self._parse("(a AND b")

    def test_parse_error_trailing_token(self):
        with pytest.raises(ValueError):
            self._parse("a b ) c")


# ---------------------------------------------------------------------------
# _build_search_clause validation
# ---------------------------------------------------------------------------

class TestBuildSearchClause:
    def test_valid_query_returns_clause_and_terms(self):
        clause, terms = _build_search_clause("severity:high")
        assert clause is not None
        assert "high" in terms

    def test_query_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            _build_search_clause("a" * 501)

    def test_too_many_tokens(self):
        query = " ".join([f"term{i}" for i in range(21)])
        with pytest.raises(ValueError, match="Too many"):
            _build_search_clause(query)

    def test_empty_query_no_terms(self):
        with pytest.raises(ValueError, match="No search terms"):
            _build_search_clause("AND OR")

    def test_field_filter_matched(self):
        clause, terms = _build_search_clause("source_ip:10.0.0.1")
        assert "10.0.0.1" in terms

    def test_unknown_field_falls_through_to_fulltext(self):
        # 'foobar' is not in FIELD_MAP → treated as full-text term
        clause, terms = _build_search_clause("foobar:value")
        assert "foobar:value" in terms

    def test_boolean_combination(self):
        clause, terms = _build_search_clause("severity:high AND user:admin")
        assert "high" in terms
        assert "admin" in terms


# ---------------------------------------------------------------------------
# ILIKE wildcard escaping
# ---------------------------------------------------------------------------

class TestEscapeIlike:
    def test_percent_escaped(self):
        assert _escape_ilike("100%") == "100\\%"

    def test_underscore_escaped(self):
        assert _escape_ilike("user_name") == "user\\_name"

    def test_backslash_escaped_first(self):
        assert _escape_ilike("a\\b") == "a\\\\b"

    def test_no_special_chars(self):
        assert _escape_ilike("normal") == "normal"

    def test_combined(self):
        result = _escape_ilike("100%_test")
        assert result == "100\\%\\_test"


# ---------------------------------------------------------------------------
# Sensitive field redaction
# ---------------------------------------------------------------------------

class TestRedact:
    def test_redacts_password_equals(self):
        result = _redact("auth password=hunter2 failed")
        assert "hunter2" not in result
        assert "[REDACTED]" in result

    def test_redacts_password_colon(self):
        result = _redact("password: secret123")
        assert "secret123" not in result

    def test_redacts_token(self):
        result = _redact("token=abc123def")
        assert "abc123def" not in result
        assert "[REDACTED]" in result

    def test_redacts_authorization_bearer(self):
        result = _redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "[REDACTED]" in result

    def test_redacts_api_key(self):
        result = _redact("api_key=sk-1234567890abcdef")
        assert "sk-1234567890abcdef" not in result

    def test_redacts_secret(self):
        result = _redact("secret=mysecretvalue")
        assert "mysecretvalue" not in result

    def test_no_redaction_needed(self):
        text = "Failed login from 10.0.0.1 user=alice"
        assert _redact(text) == text

    def test_none_input(self):
        assert _redact(None) is None

    def test_empty_string(self):
        assert _redact("") == ""

    def test_case_insensitive_redaction(self):
        result = _redact("PASSWORD=MyPass123")
        assert "MyPass123" not in result


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimit:
    def setup_method(self):
        # Clear all state between tests
        _rate_attempts.clear()

    def test_first_request_allowed(self):
        _check_rate_limit("testuser")  # should not raise

    def test_up_to_limit_allowed(self):
        now = time.monotonic()
        _rate_attempts["u2"] = [now] * 59
        _check_rate_limit("u2")  # 60th request — should not raise

    def test_over_limit_raises_429(self):
        now = time.monotonic()
        _rate_attempts["u3"] = [now] * 60
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit("u3")
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    def test_old_attempts_are_evicted(self):
        old = time.monotonic() - 61  # outside 60s window
        _rate_attempts["u4"] = [old] * 60
        _check_rate_limit("u4")  # old attempts evicted — should not raise

    def test_different_users_have_separate_limits(self):
        now = time.monotonic()
        _rate_attempts["heavy_user"] = [now] * 60
        # A different user is unaffected
        _check_rate_limit("fresh_user")  # should not raise

    def test_retry_after_header_value(self):
        now = time.monotonic()
        _rate_attempts["u5"] = [now] * 60
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit("u5")
        assert exc_info.value.headers["Retry-After"] == "60"
