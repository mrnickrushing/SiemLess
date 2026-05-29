"""
ECS-lite log normalization service.
Maps event fields to a subset of the Elastic Common Schema (ECS).
"""
from datetime import datetime
from typing import Any


def normalize_to_ecs(event_dict: dict, parsed_fields: dict) -> dict:
    """Map event fields to ECS-lite schema. Returns a dict of ECS fields."""
    timestamp = event_dict.get("timestamp")
    if isinstance(timestamp, datetime):
        ts_str = timestamp.isoformat()
    else:
        ts_str = str(timestamp) if timestamp else datetime.utcnow().isoformat()

    return {
        "ecs.version": "1.0",
        "@timestamp": ts_str,
        "event.action": (
            parsed_fields.get("action")
            or event_dict.get("action")
            or event_dict.get("category", "unknown")
        ),
        "event.category": event_dict.get("category", "unknown"),
        "event.outcome": _map_outcome(parsed_fields, event_dict),
        "source.ip": (
            event_dict.get("source_ip")
            or parsed_fields.get("src_ip")
        ),
        "destination.ip": (
            event_dict.get("destination_ip")
            or parsed_fields.get("dest_ip")
            or parsed_fields.get("destination_ip")
        ),
        "user.name": (
            event_dict.get("user")
            or parsed_fields.get("username")
            or parsed_fields.get("user")
        ),
        "host.hostname": (
            event_dict.get("hostname")
            or parsed_fields.get("hostname")
        ),
        "process.name": (
            event_dict.get("process")
            or parsed_fields.get("process")
            or parsed_fields.get("program")
        ),
        "network.transport": (
            parsed_fields.get("protocol")
            or parsed_fields.get("transport")
        ),
        "log.original": event_dict.get("raw_log"),
        "log.level": event_dict.get("severity", "info"),
        "source.port": event_dict.get("source_port"),
        "destination.port": event_dict.get("destination_port"),
    }


def _map_outcome(parsed_fields: dict, event_dict: dict) -> str:
    action = str(
        parsed_fields.get("action")
        or event_dict.get("action")
        or ""
    ).lower()
    if any(w in action for w in ["fail", "denied", "reject", "error", "invalid"]):
        return "failure"
    if any(w in action for w in ["success", "accept", "allow", "login"]):
        return "success"
    return "unknown"
