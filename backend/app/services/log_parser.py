"""
Backwards-compatibility shim.

The LogParser class has been moved to app.services.parsers.
This module re-exports it so existing imports keep working without changes.
"""
from app.services.parsers import LogParser  # noqa: F401

__all__ = ["LogParser"]
