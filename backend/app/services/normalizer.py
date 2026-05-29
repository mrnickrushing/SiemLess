"""
ECS-lite log normalization service.
Maps event fields to a subset of the Elastic Common Schema (ECS).
"""
from datetime import datetime
from typing import Any


def normalize_to_ecs(event_dict: dict, parsed_fields: dict) -> dict:
    """
    Normalize event and parsed field dictionaries into a subset of Elastic Common Schema (ECS) fields.
    
    This builds and returns a dictionary of ECS-like keys populated from values in event_dict and parsed_fields, applying sensible fallbacks and defaults. If `event_dict["timestamp"]` is a datetime it is converted to ISO-8601; if missing or falsy a current UTC ISO-8601 timestamp is used. Common fields produced include `@timestamp`, `ecs.version`, `event.action`, `event.category`, `event.outcome`, `source.ip`, `destination.ip`, `user.name`, `host.hostname`, `process.name`, `network.transport`, `log.original`, `log.level`, `source.port`, and `destination.port`.
    
    Parameters:
        event_dict (dict): Original event data (may contain raw and top-level fields such as timestamp, action, category, source_ip, destination_ip, user, hostname, process, program, raw_log, severity, source_port, destination_port).
        parsed_fields (dict): Values extracted by parsing (may contain alternate keys such as action, src_ip, dest_ip, destination_ip, username, user, hostname, process, program, protocol, transport).
    
    Returns:
        dict: A dictionary of ECS-like fields populated from the provided inputs (see summary for notable keys).
    """
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
    """
    Determine the ECS `event.outcome` value by inspecting an action string.
    
    Checks the `action` key from `parsed_fields` first, then `event_dict`, lowercases it, and maps keywords to outcomes.
    
    Parameters:
        parsed_fields (dict): Parsed field values; the function will prefer `parsed_fields["action"]` if present.
        event_dict (dict): Original event data; used as a fallback source for the `action` value.
    
    Returns:
        str: `"failure"` if the action text contains any of `fail`, `denied`, `reject`, `error`, or `invalid`; \
    `"success"` if it contains any of `success`, `accept`, `allow`, or `login`; `"unknown"` otherwise.
    """
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
