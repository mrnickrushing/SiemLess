"""Windows event log parser."""
import re

RE_WINDOWS_LOGON = re.compile(
    r"Logon Type:\s+(?P<logon_type>\d+).*?Account Name:\s+(?P<user>\S+).*?"
    r"Source Network Address:\s+(?P<src_ip>\S+)",
    re.DOTALL,
)

_LOGON_TYPES: dict[int, str] = {
    2: "Interactive",
    3: "Network",
    4: "Batch",
    5: "Service",
    7: "Unlock",
    8: "NetworkCleartext",
    9: "NewCredentials",
    10: "RemoteInteractive",
    11: "CachedInteractive",
}


def _windows_logon_type(logon_type: int) -> str:
    return _LOGON_TYPES.get(logon_type, f"Unknown({logon_type})")


def parse_windows_event(message: str) -> dict:
    """Parse a Windows security event log message."""
    result: dict = {"log_type": "windows", "category": "authentication"}

    m = RE_WINDOWS_LOGON.search(message)
    if m:
        gd = m.groupdict()
        logon_type = int(gd.get("logon_type", 0))
        result.update({
            "source_ip": gd.get("src_ip"),
            "user": gd.get("user"),
            "action": "success",
            "parsed_fields": {
                "logon_type": logon_type,
                "logon_type_desc": _windows_logon_type(logon_type),
            },
        })
        return result

    if "4625" in message or "Logon Failure" in message or "failed" in message.lower():
        result["action"] = "failed"
        result["severity"] = "medium"
        result["parsed_fields"] = {"event": "logon_failure"}
    elif "4624" in message or "Logon Success" in message:
        result["action"] = "success"
        result["parsed_fields"] = {"event": "logon_success"}
    elif "4648" in message:
        result["action"] = "success"
        result["parsed_fields"] = {"event": "explicit_logon"}
        result["severity"] = "medium"
    elif "4720" in message:
        result["category"] = "system"
        result["severity"] = "high"
        result["parsed_fields"] = {"event": "user_account_created"}
    elif "4732" in message or "4728" in message:
        result["category"] = "system"
        result["severity"] = "high"
        result["parsed_fields"] = {"event": "group_member_added"}
    else:
        result["parsed_fields"] = {"event": "windows_generic"}

    return result
