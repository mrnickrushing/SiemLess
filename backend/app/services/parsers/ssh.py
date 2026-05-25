"""SSH log parser."""
import re

RE_SSH_FAILED = re.compile(
    r"Failed (?P<auth_method>\S+) for(?: invalid user)? (?P<user>\S+) from (?P<src_ip>\S+) port (?P<port>\d+)"
)
RE_SSH_ACCEPTED = re.compile(
    r"Accepted (?P<auth_method>\S+) for (?P<user>\S+) from (?P<src_ip>\S+) port (?P<port>\d+)"
)
RE_SSH_INVALID = re.compile(
    r"Invalid user (?P<user>\S+) from (?P<src_ip>\S+)(?: port (?P<port>\d+))?"
)
RE_SSH_DISCONNECT = re.compile(
    r"Disconnected from(?: invalid user)? (?P<user>\S+)?\s*"
    r"(?P<src_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) port (?P<port>\d+)"
)
RE_SSH_MAX_AUTH = re.compile(
    r"error: maximum authentication attempts exceeded.*from (?P<src_ip>\S+)"
)


def parse_ssh_log(message: str) -> dict:
    """Parse an SSH daemon log message into a normalised dict."""
    result: dict = {"log_type": "ssh", "category": "authentication"}

    m = RE_SSH_FAILED.search(message)
    if m:
        result.update({
            "source_ip": m.group("src_ip"),
            "user": m.group("user"),
            "action": "failed",
            "source_port": int(m.group("port")),
            "parsed_fields": {"auth_method": m.group("auth_method"), "event": "failed_auth"},
        })
        return result

    m = RE_SSH_ACCEPTED.search(message)
    if m:
        result.update({
            "source_ip": m.group("src_ip"),
            "user": m.group("user"),
            "action": "success",
            "source_port": int(m.group("port")),
            "parsed_fields": {"auth_method": m.group("auth_method"), "event": "accepted_auth"},
        })
        return result

    m = RE_SSH_INVALID.search(message)
    if m:
        result.update({
            "source_ip": m.group("src_ip"),
            "user": m.group("user"),
            "action": "failed",
            "parsed_fields": {"event": "invalid_user"},
        })
        return result

    m = RE_SSH_MAX_AUTH.search(message)
    if m:
        result.update({
            "source_ip": m.group("src_ip"),
            "action": "failed",
            "parsed_fields": {"event": "max_auth_exceeded"},
        })
        return result

    result["parsed_fields"] = {"event": "ssh_generic"}
    return result
