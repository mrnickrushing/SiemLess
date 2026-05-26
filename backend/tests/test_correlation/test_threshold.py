"""Tests for the correlation engine sliding-window threshold logic."""
import asyncio
import time
from unittest.mock import MagicMock

import pytest

from app.services.correlation import CorrelationEngine, WindowCounter


# ---------------------------------------------------------------------------
# WindowCounter unit tests
# ---------------------------------------------------------------------------

def test_window_counter_add_and_count():
    wc = WindowCounter(60)
    now = time.time()
    wc.add("e1", now)
    wc.add("e2", now)
    assert wc.count(now) == 2


def test_window_counter_evicts_old_events():
    wc = WindowCounter(60)
    old = time.time() - 120
    now = time.time()
    wc.add("old-event", old)
    wc.add("new-event", now)
    assert wc.count(now) == 1


def test_window_counter_event_ids():
    wc = WindowCounter(60)
    now = time.time()
    wc.add("e1", now)
    wc.add("e2", now)
    assert set(wc.event_ids()) == {"e1", "e2"}


def test_window_counter_all_evicted():
    wc = WindowCounter(10)
    old = time.time() - 60
    wc.add("old", old)
    assert wc.count(time.time()) == 0


# ---------------------------------------------------------------------------
# CorrelationEngine — structure
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return CorrelationEngine()


def test_engine_initialises(engine):
    assert engine is not None
    assert hasattr(engine, "_rules")
    assert hasattr(engine, "_counters")
    assert isinstance(engine._rules, list)
    assert isinstance(engine._counters, dict)


# ---------------------------------------------------------------------------
# CorrelationEngine._matches_condition
# ---------------------------------------------------------------------------

def _make_event(**kwargs):
    """Return a MagicMock SecurityEvent with the given field values."""
    event = MagicMock()
    event.parsed_fields = {}
    for k, v in kwargs.items():
        setattr(event, k, v)
    return event


def test_matches_single_field_equals(engine):
    event = _make_event(log_type="ssh", action="failed")
    condition = {"field": "log_type", "op": "equals", "value": "ssh"}
    assert engine._matches_condition(event, condition) is True


def test_no_match_single_field_equals(engine):
    event = _make_event(log_type="apache", action="failed")
    condition = {"field": "log_type", "op": "equals", "value": "ssh"}
    assert engine._matches_condition(event, condition) is False


def test_matches_and_filters(engine):
    event = _make_event(log_type="ssh", action="failed")
    condition = {
        "operator": "AND",
        "filters": [
            {"field": "log_type", "op": "equals", "value": "ssh"},
            {"field": "action", "op": "equals", "value": "failed"},
        ],
    }
    assert engine._matches_condition(event, condition) is True


def test_and_filters_one_mismatch(engine):
    event = _make_event(log_type="ssh", action="success")
    condition = {
        "operator": "AND",
        "filters": [
            {"field": "log_type", "op": "equals", "value": "ssh"},
            {"field": "action", "op": "equals", "value": "failed"},
        ],
    }
    assert engine._matches_condition(event, condition) is False


def test_matches_or_filters(engine):
    event = _make_event(severity="critical", action="block")
    condition = {
        "operator": "OR",
        "filters": [
            {"field": "severity", "op": "equals", "value": "critical"},
            {"field": "severity", "op": "equals", "value": "high"},
        ],
    }
    assert engine._matches_condition(event, condition) is True


def test_empty_filters_always_match(engine):
    event = _make_event(log_type="ssh")
    assert engine._matches_condition(event, {}) is True


def test_matches_contains_op(engine):
    event = _make_event(message="Failed password for root")
    condition = {"field": "message", "op": "contains", "value": "failed password"}
    assert engine._matches_condition(event, condition) is True


def test_matches_negate(engine):
    event = _make_event(severity="low")
    condition = {"field": "severity", "op": "equals", "value": "low", "negate": True}
    assert engine._matches_condition(event, condition) is False


def test_matches_in_op(engine):
    event = _make_event(severity="high")
    condition = {"field": "severity", "op": "in", "value": ["critical", "high"]}
    assert engine._matches_condition(event, condition) is True


def test_no_match_in_op(engine):
    event = _make_event(severity="low")
    condition = {"field": "severity", "op": "in", "value": ["critical", "high"]}
    assert engine._matches_condition(event, condition) is False


def test_matches_exists_op(engine):
    event = _make_event(source_ip="1.2.3.4")
    condition = {"field": "source_ip", "op": "exists"}
    assert engine._matches_condition(event, condition) is True


def test_not_exists_op(engine):
    event = _make_event(source_ip=None)
    condition = {"field": "source_ip", "op": "exists"}
    assert engine._matches_condition(event, condition) is False


def test_matches_regex_op(engine):
    event = _make_event(message="sudo: alice : TTY=pts/0")
    condition = {"field": "message", "op": "regex", "value": r"sudo:.*TTY="}
    assert engine._matches_condition(event, condition) is True


# ---------------------------------------------------------------------------
# CorrelationEngine._get_field — dot notation
# ---------------------------------------------------------------------------

def test_get_field_simple(engine):
    event = _make_event(log_type="ssh")
    assert engine._get_field(event, "log_type") == "ssh"


def test_get_field_dot_notation(engine):
    event = MagicMock()
    event.parsed_fields = {"event": "failed_auth", "auth_method": "password"}
    assert engine._get_field(event, "parsed_fields.event") == "failed_auth"


def test_get_field_dot_notation_missing_key(engine):
    event = MagicMock()
    event.parsed_fields = {"other_key": "value"}  # non-empty so condition is truthy
    assert engine._get_field(event, "parsed_fields.nonexistent") is None
