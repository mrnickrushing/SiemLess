"""JSON log parser."""
import json
from datetime import datetime, timezone

from app.services.parsers.base import normalise_severity


def parse_json_log(raw_log: str) -> dict:
    """Parse a JSON-formatted log line into a normalised dict."""
    try:
        data = json.loads(raw_log)
    except json.JSONDecodeError:
        return {"message": raw_log, "log_type": "generic"}

    if not isinstance(data, dict):
        return {"message": raw_log, "log_type": "generic"}

    def _get(*keys):
        for k in keys:
            v = data.get(k) or data.get(k.lower()) or data.get(k.upper())
            if v is not None:
                return v
        return None

    ts = _get("timestamp", "time", "@timestamp", "datetime", "date")
    timestamp = None
    if ts:
        try:
            if isinstance(ts, (int, float)):
                timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            timestamp = None

    message = _get("message", "msg", "log", "text", "event.message") or raw_log
    src_ip = _get("src_ip", "source_ip", "src", "client_ip", "remote_addr", "clientip")
    dst_ip = _get("dst_ip", "dest_ip", "destination_ip", "dst")
    hostname = _get("hostname", "host", "computer", "machine")
    user = _get("user", "username", "account", "user.name")
    process = _get("process", "proc", "application", "app")
    severity = _get("severity", "level", "priority", "loglevel")

    if severity and isinstance(severity, str):
        severity = normalise_severity(severity)
    else:
        severity = "low"

    return {
        "timestamp": timestamp,
        "source_ip": str(src_ip) if src_ip else None,
        "destination_ip": str(dst_ip) if dst_ip else None,
        "hostname": str(hostname) if hostname else None,
        "user": str(user) if user else None,
        "process": str(process) if process else None,
        "message": str(message),
        "severity": severity,
        "log_type": "generic",
        "category": "system",
        "parsed_fields": {k: v for k, v in data.items()},
    }
