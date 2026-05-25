"""
Shared constants, compiled regexes, and utility functions used by
multiple format-specific parser modules.
"""
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Month name → number
# ---------------------------------------------------------------------------
MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ---------------------------------------------------------------------------
# Syslog regexes
# ---------------------------------------------------------------------------

# RFC 3164: <PRI>MMM DD HH:MM:SS HOST PROC[PID]: MSG
RE_RFC3164 = re.compile(
    r"^(?:<(?P<pri>\d{1,3})>)?"
    r"(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
    r"(?P<message>.+)$",
    re.DOTALL,
)

# RFC 5424: <PRI>VERSION TIMESTAMP HOST APP PROCID MSGID SD MSG
RE_RFC5424 = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<version>\d+)\s+"
    r"(?P<timestamp>\S+)\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<appname>\S+)\s+"
    r"(?P<procid>\S+)\s+"
    r"(?P<msgid>\S+)\s+"
    r"(?P<structured_data>\S+)\s*"
    r"(?P<message>.*)$",
    re.DOTALL,
)

# CEF header
RE_CEF = re.compile(
    r"^(?:.*)?CEF:(?P<version>\d+)\|"
    r"(?P<vendor>[^|]*)\|(?P<product>[^|]*)\|(?P<dev_version>[^|]*)\|"
    r"(?P<sig_id>[^|]*)\|(?P<name>[^|]*)\|(?P<severity>[^|]*)\|"
    r"(?P<extension>.*)$",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------

def parse_priority(pri_str: Optional[str]) -> tuple[int, int]:
    """Return (facility, severity_num) from a syslog PRI string."""
    if pri_str is None:
        return 1, 5
    pri = int(pri_str)
    return pri >> 3, pri & 0x07


def syslog_sev_to_str(sev_num: int) -> str:
    mapping = {
        0: "critical", 1: "critical", 2: "critical",
        3: "high", 4: "high",
        5: "medium",
        6: "low", 7: "low",
    }
    return mapping.get(sev_num, "low")


def normalise_severity(sev: str) -> str:
    sev = sev.lower()
    if sev in ("critical", "emergency", "alert", "emerg"):
        return "critical"
    if sev in ("error", "err", "high", "severe"):
        return "high"
    if sev in ("warning", "warn", "medium", "notice"):
        return "medium"
    return "low"


def category_from_log_type(log_type: str) -> str:
    mapping = {
        "ssh": "authentication",
        "apache": "application",
        "nginx": "application",
        "firewall": "network",
        "windows": "authentication",
        "sudo": "system",
        "generic": "system",
    }
    return mapping.get(log_type, "system")
