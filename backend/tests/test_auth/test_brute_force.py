"""Tests for the login brute-force rate limiter in the auth router."""
import time
import pytest

from fastapi import HTTPException

from app.routers.auth import _check_and_record_failure, _failed_attempts


class TestBruteForceProtection:
    def setup_method(self):
        _failed_attempts.clear()

    def test_first_failure_allowed(self):
        _check_and_record_failure("alice")  # should not raise

    def test_nine_failures_allowed(self):
        now = time.monotonic()
        _failed_attempts["bob"] = [now] * 9
        _check_and_record_failure("bob")  # 10th attempt — still within limit

    def test_ten_failures_raises_429(self):
        now = time.monotonic()
        _failed_attempts["carol"] = [now] * 10
        with pytest.raises(HTTPException) as exc_info:
            _check_and_record_failure("carol")
        assert exc_info.value.status_code == 429

    def test_retry_after_header_present(self):
        now = time.monotonic()
        _failed_attempts["dave"] = [now] * 10
        with pytest.raises(HTTPException) as exc_info:
            _check_and_record_failure("dave")
        assert "Retry-After" in exc_info.value.headers

    def test_old_failures_are_evicted(self):
        old = time.monotonic() - 301  # outside 300s window
        _failed_attempts["eve"] = [old] * 10
        _check_and_record_failure("eve")  # all attempts expired — should not raise

    def test_different_users_independent(self):
        now = time.monotonic()
        _failed_attempts["frank"] = [now] * 10
        # Grace should be unaffected
        _check_and_record_failure("grace")  # should not raise

    def test_each_call_records_an_attempt(self):
        _check_and_record_failure("henry")
        assert len(_failed_attempts["henry"]) == 1
        _check_and_record_failure("henry")
        assert len(_failed_attempts["henry"]) == 2

    def test_window_resets_after_expiry(self):
        # Simulate 10 attempts just outside the window
        old = time.monotonic() - 301
        _failed_attempts["ivan"] = [old] * 10
        # After expiry the counter resets, so one more should be fine
        _check_and_record_failure("ivan")
        # Now the window should have only the 1 fresh attempt
        assert len(_failed_attempts["ivan"]) == 1
