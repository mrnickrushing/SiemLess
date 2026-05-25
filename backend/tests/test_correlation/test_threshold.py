"""Tests for the correlation engine sliding-window threshold logic."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.correlation import CorrelationEngine


@pytest.fixture
def engine():
    return CorrelationEngine()


@pytest.fixture
def mock_rule():
    rule = MagicMock()
    rule.id = "test-rule-id"
    rule.name = "SSH Brute Force"
    rule.threshold = 3
    rule.time_window = 60  # 60 second window
    rule.severity = "high"
    rule.category = "authentication"
    rule.condition = {"log_type": "ssh", "action": "failed"}
    rule.mitre_tactic = "TA0006"
    rule.mitre_technique = "T1110"
    rule.alert_title_template = "SSH brute force detected"
    rule.alert_description_template = "Rule triggered {count} times."
    return rule


@pytest.fixture
def mock_event():
    event = MagicMock()
    event.id = "event-id-1"
    event.log_type = "ssh"
    event.action = "failed"
    event.source_ip = "203.0.113.1"
    event.user = "root"
    event.severity = "medium"
    event.category = "authentication"
    event.hostname = "server1"
    return event


def test_engine_initialises(engine):
    assert engine is not None
    assert hasattr(engine, "_rules")
    assert hasattr(engine, "_event_windows")


def test_rule_matches_event(engine, mock_rule, mock_event):
    """Rule condition {log_type: ssh, action: failed} should match a failed SSH event."""
    assert engine._rule_matches(mock_rule, mock_event) is True


def test_rule_does_not_match_different_log_type(engine, mock_rule, mock_event):
    mock_event.log_type = "apache"
    assert engine._rule_matches(mock_rule, mock_event) is False


def test_rule_does_not_match_different_action(engine, mock_rule, mock_event):
    mock_event.action = "success"
    assert engine._rule_matches(mock_rule, mock_event) is False


def test_window_count_below_threshold_does_not_fire(engine, mock_rule, mock_event):
    """2 events below threshold=3 should not fire an alert."""
    key = f"{mock_rule.id}:{mock_event.source_ip}"
    now = time.time()
    engine._event_windows[key] = [now, now]
    result = engine._check_threshold(mock_rule, mock_event, key)
    assert result is False


def test_window_count_at_threshold_fires(engine, mock_rule, mock_event):
    """3 events at threshold=3 should fire an alert."""
    key = f"{mock_rule.id}:{mock_event.source_ip}"
    now = time.time()
    engine._event_windows[key] = [now, now, now]
    result = engine._check_threshold(mock_rule, mock_event, key)
    assert result is True


def test_old_events_are_evicted(engine, mock_rule, mock_event):
    """Events older than time_window should be evicted before threshold check."""
    key = f"{mock_rule.id}:{mock_event.source_ip}"
    old_time = time.time() - 120  # 2 minutes ago, outside 60s window
    engine._event_windows[key] = [old_time, old_time, old_time]
    result = engine._check_threshold(mock_rule, mock_event, key)
    # After eviction, 0 events remain — below threshold
    assert result is False
    assert len(engine._event_windows.get(key, [])) == 0
