"""Sudo log parser."""
import re

RE_SUDO = re.compile(
    r"(?P<user>\S+)\s*:\s*(?:TTY=\S+\s*)?(?:PWD=\S+\s*)?USER=(?P<run_as>\S+)\s*;\s*COMMAND=(?P<command>.+)"
)


def parse_sudo_log(message: str) -> dict:
    """Parse a sudo log message into a normalised dict."""
    user = None
    user_m = re.match(r"(\w+)\s*:", message)
    if user_m:
        user = user_m.group(1)

    kv: dict[str, str] = {}
    for k, v in re.findall(r"(\w+)=((?:[^;]|(?!;))*?)(?:\s*;|\s*$)", message):
        kv[k.upper()] = v.strip()

    run_as = kv.get("USER") or ""
    command = kv.get("COMMAND") or ""

    if not run_as:
        m = RE_SUDO.search(message)
        if m:
            gd = m.groupdict()
            user = user or gd.get("user")
            run_as = gd.get("run_as", "")
            command = gd.get("command", "")

    if not user and not run_as:
        return {"log_type": "sudo", "category": "system", "message": message}

    severity = "high" if run_as == "root" else "medium"

    return {
        "log_type": "sudo",
        "category": "system",
        "user": user,
        "severity": severity,
        "action": "success",
        "parsed_fields": {
            "run_as": run_as,
            "command": command,
            "event": "privilege_escalation" if run_as == "root" else "sudo_command",
            "tty": kv.get("TTY"),
            "pwd": kv.get("PWD"),
        },
    }
