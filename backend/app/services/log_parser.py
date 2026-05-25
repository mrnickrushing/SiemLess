"""
Log parser service: detects format, parses various log types,
normalizes into SecurityEventCreate schema.
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional

from app.schemas.event import SecurityEventCreate


# ---------------------------------------------------------------------------
# Compiled regular expressions
# ---------------------------------------------------------------------------

# Syslog RFC 3164: <PRI>MMM DD HH:MM:SS HOST PROC[PID]: MSG
RE_RFC3164 = re.compile(
    r"^(?:<(?P<pri>\d{1,3})>)?"
    r"(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
    r"(?P<message>.+)$",
    re.DOTALL,
)

# Syslog RFC 5424: <PRI>VERSION TIMESTAMP HOST APP PROCID MSGID SD MSG
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

# CEF: CEF:Version|DeviceVendor|DeviceProduct|DeviceVersion|SignatureID|Name|Severity|Extension
RE_CEF = re.compile(
    r"^(?:.*)?CEF:(?P<version>\d+)\|"
    r"(?P<vendor>[^|]*)\|(?P<product>[^|]*)\|(?P<dev_version>[^|]*)\|"
    r"(?P<sig_id>[^|]*)\|(?P<name>[^|]*)\|(?P<severity>[^|]*)\|"
    r"(?P<extension>.*)$",
    re.DOTALL,
)

# Apache / Nginx combined log
RE_APACHE = re.compile(
    r'^(?P<src_ip>\S+)\s+\S+\s+(?P<user>\S+)\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<url>\S+)\s+(?P<proto>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?',
)

# SSH log patterns
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
    r"Disconnected from(?: invalid user)? (?P<user>\S+)?\s*(?P<src_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) port (?P<port>\d+)"
)
RE_SSH_MAX_AUTH = re.compile(r"error: maximum authentication attempts exceeded.*from (?P<src_ip>\S+)")

# IPTables
RE_IPTABLES = re.compile(
    r"(?:IN=(?P<in_iface>\S*))?\s*"
    r"(?:OUT=(?P<out_iface>\S*))?\s*"
    r"(?:MAC=(?P<mac>[0-9a-f:]+))?\s*"
    r"(?:SRC=(?P<src_ip>\S+))?\s*"
    r"(?:DST=(?P<dst_ip>\S+))?\s*"
    r"(?:LEN=\d+\s*)?"
    r"(?:TOS=\S+\s*)?"
    r"(?:PREC=\S+\s*)?"
    r"(?:TTL=\d+\s*)?"
    r"(?:ID=\d+\s*)?"
    r"(?:(?:DF|CE|MF)\s*)?"
    r"(?:PROTO=(?P<proto>\S+))?\s*"
    r"(?:SPT=(?P<spt>\d+))?\s*"
    r"(?:DPT=(?P<dpt>\d+))?",
    re.IGNORECASE,
)

# Sudo log
RE_SUDO = re.compile(
    r"(?P<user>\S+)\s*:\s*(?:TTY=\S+\s*)?(?:PWD=\S+\s*)?USER=(?P<run_as>\S+)\s*;\s*COMMAND=(?P<command>.+)"
)

# Windows event-log style (simplified text)
RE_WINDOWS_LOGON = re.compile(
    r"Logon Type:\s+(?P<logon_type>\d+).*?Account Name:\s+(?P<user>\S+).*?"
    r"Source Network Address:\s+(?P<src_ip>\S+)",
    re.DOTALL,
)

# Nginx error log
RE_NGINX_ERROR = re.compile(
    r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[(?P<level>\w+)\]\s+\d+#\d+:\s+(?P<message>.+?)(?:,\s+client:\s+(?P<client_ip>\S+))?"
)

# Month name → number
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_priority(pri_str: Optional[str]) -> tuple[int, int]:
    """Return (facility, severity_num) from syslog priority."""
    if pri_str is None:
        return 1, 5
    pri = int(pri_str)
    return pri >> 3, pri & 0x07


def _syslog_sev_to_str(sev_num: int) -> str:
    mapping = {0: "critical", 1: "critical", 2: "critical", 3: "high", 4: "high", 5: "medium", 6: "low", 7: "low"}
    return mapping.get(sev_num, "low")


class LogParser:
    """Detects, parses, and normalises diverse log formats."""

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def parse(self, raw_log: str, log_source: str = "api") -> dict:
        """Parse a raw log string and return a normalised dict."""
        raw_log = raw_log.strip()
        fmt = self.detect_format(raw_log)
        parsed: dict = {}

        if fmt == "json":
            parsed = self.parse_json_log(raw_log)
        elif fmt == "cef":
            parsed = self.parse_cef(raw_log)
        elif fmt == "rfc5424":
            parsed = self.parse_syslog_rfc5424(raw_log)
        elif fmt == "rfc3164":
            parsed = self.parse_syslog_rfc3164(raw_log)
        else:
            parsed = {"message": raw_log, "log_type": "generic"}

        parsed["raw_log"] = raw_log
        parsed["log_source"] = log_source
        return parsed

    def detect_format(self, raw_log: str) -> str:
        """Return one of: json, cef, rfc5424, rfc3164, plain."""
        s = raw_log.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                json.loads(s)
                return "json"
            except json.JSONDecodeError:
                pass
        if "CEF:" in s:
            return "cef"
        if RE_RFC5424.match(s):
            return "rfc5424"
        if RE_RFC3164.match(s):
            return "rfc3164"
        return "plain"

    # -----------------------------------------------------------------------
    # Format parsers
    # -----------------------------------------------------------------------

    def parse_syslog_rfc3164(self, raw_log: str) -> dict:
        m = RE_RFC3164.match(raw_log.strip())
        if not m:
            return {"message": raw_log, "log_type": "generic"}

        gd = m.groupdict()
        facility, sev_num = _parse_priority(gd.get("pri"))

        # Build best-effort timestamp (current year)
        try:
            month = MONTHS.get(gd["month"].lower(), 1)
            year = datetime.now(timezone.utc).year
            ts_str = f"{year}-{month:02d}-{int(gd['day']):02d}T{gd['time']}Z"
            timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            timestamp = datetime.now(timezone.utc)

        message = gd.get("message", "")
        process = gd.get("process", "")
        log_type, top_fields, extra = self._classify_by_process_and_message(process, message)

        result: dict = {
            "timestamp": timestamp,
            "hostname": gd.get("hostname"),
            "process": process,
            "message": message,
            "log_type": log_type,
            "severity": _syslog_sev_to_str(sev_num),
            "parsed_fields": {
                "facility": facility,
                "pid": gd.get("pid"),
                **extra,
            },
        }
        # Merge top-level fields from specialised parser (source_ip, user, action, etc.)
        for k, v in top_fields.items():
            if v is not None:
                result[k] = v
        return result

    def parse_syslog_rfc5424(self, raw_log: str) -> dict:
        m = RE_RFC5424.match(raw_log.strip())
        if not m:
            return {"message": raw_log, "log_type": "generic"}

        gd = m.groupdict()
        facility, sev_num = _parse_priority(gd.get("pri"))

        try:
            ts_raw = gd["timestamp"]
            if ts_raw and ts_raw != "-":
                timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)

        message = gd.get("message", "")
        appname = gd.get("appname", "-")
        log_type, top_fields, extra = self._classify_by_process_and_message(appname, message)

        result: dict = {
            "timestamp": timestamp,
            "hostname": gd.get("hostname") if gd.get("hostname") != "-" else None,
            "process": appname if appname != "-" else None,
            "message": message,
            "log_type": log_type,
            "severity": _syslog_sev_to_str(sev_num),
            "parsed_fields": {
                "facility": facility,
                "procid": gd.get("procid"),
                "msgid": gd.get("msgid"),
                "structured_data": gd.get("structured_data"),
                **extra,
            },
        }
        # Merge top-level fields from specialised parser
        for k, v in top_fields.items():
            if v is not None:
                result[k] = v
        return result

    def parse_cef(self, raw_log: str) -> dict:
        m = RE_CEF.match(raw_log.strip())
        if not m:
            return {"message": raw_log, "log_type": "generic"}

        gd = m.groupdict()
        extension_str = gd.get("extension", "")
        ext = self._parse_cef_extension(extension_str)

        severity_raw = gd.get("severity", "5")
        try:
            severity_num = int(severity_raw)
            severity = self._cef_sev_to_str(severity_num)
        except ValueError:
            severity = severity_raw.lower() if severity_raw.lower() in ("low", "medium", "high", "critical") else "medium"

        return {
            "hostname": ext.get("dvchost") or ext.get("deviceAddress"),
            "source_ip": ext.get("src"),
            "destination_ip": ext.get("dst"),
            "source_port": int(ext["spt"]) if "spt" in ext else None,
            "destination_port": int(ext["dpt"]) if "dpt" in ext else None,
            "message": gd.get("name", ""),
            "severity": severity,
            "category": "network",
            "log_type": "firewall",
            "action": ext.get("act"),
            "parsed_fields": {
                "cef_vendor": gd.get("vendor"),
                "cef_product": gd.get("product"),
                "cef_sig_id": gd.get("sig_id"),
                **ext,
            },
        }

    def parse_json_log(self, raw_log: str) -> dict:
        try:
            data = json.loads(raw_log)
        except json.JSONDecodeError:
            return {"message": raw_log, "log_type": "generic"}

        if not isinstance(data, dict):
            return {"message": raw_log, "log_type": "generic"}

        # Try to extract common fields using multiple key naming conventions
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
            severity = self._normalise_severity(severity)
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

    # -----------------------------------------------------------------------
    # Specialised log parsers
    # -----------------------------------------------------------------------

    def parse_ssh_log(self, message: str) -> dict:
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

    def parse_apache_log(self, message: str) -> dict:
        m = RE_APACHE.match(message.strip())
        if not m:
            return {"log_type": "apache", "category": "application", "message": message}

        gd = m.groupdict()
        status = int(gd.get("status", 0))
        severity = "low"
        if status >= 500:
            severity = "medium"
        elif status in (401, 403):
            severity = "medium"

        return {
            "log_type": "apache",
            "category": "application",
            "source_ip": gd.get("src_ip"),
            "user": gd.get("user") if gd.get("user") != "-" else None,
            "action": "allow" if status < 400 else "deny",
            "severity": severity,
            "parsed_fields": {
                "http_method": gd.get("method"),
                "url": gd.get("url"),
                "protocol": gd.get("proto"),
                "status_code": status,
                "bytes_sent": gd.get("bytes"),
                "referer": gd.get("referer"),
                "user_agent": gd.get("ua"),
            },
        }

    def parse_nginx_log(self, message: str) -> dict:
        # Nginx access log has same combined format as Apache
        result = self.parse_apache_log(message)
        result["log_type"] = "nginx"
        return result

    def parse_iptables_log(self, message: str) -> dict:
        action = "deny"
        msg_upper = message.upper()
        if "ACCEPT" in msg_upper:
            action = "allow"
        elif "DROP" in msg_upper or "REJECT" in msg_upper or "BLOCK" in msg_upper:
            action = "deny"

        # Extract key=value pairs (handles IN=, SRC=, DST=, etc.)
        kv: dict[str, str] = {}
        for k, v in re.findall(r'(\w+)=(\S+)', message):
            kv[k.upper()] = v

        try:
            spt = int(kv["SPT"]) if "SPT" in kv else None
        except (ValueError, TypeError):
            spt = None
        try:
            dpt = int(kv["DPT"]) if "DPT" in kv else None
        except (ValueError, TypeError):
            dpt = None

        return {
            "log_type": "firewall",
            "category": "network",
            "source_ip": kv.get("SRC"),
            "destination_ip": kv.get("DST"),
            "source_port": spt,
            "destination_port": dpt,
            "action": action,
            "parsed_fields": {
                "in_iface": kv.get("IN"),
                "out_iface": kv.get("OUT"),
                "protocol": kv.get("PROTO"),
                "mac": kv.get("MAC"),
                "len": kv.get("LEN"),
                "ttl": kv.get("TTL"),
            },
        }

    def parse_sudo_log(self, message: str) -> dict:
        # Extract the invoking user from start of message (before the colon)
        user = None
        user_m = re.match(r"(\w+)\s*:", message)
        if user_m:
            user = user_m.group(1)

        # Extract key=value pairs (TTY=, PWD=, USER=, COMMAND=)
        kv: dict[str, str] = {}
        for k, v in re.findall(r"(\w+)=((?:[^;]|(?!;))*?)(?:\s*;|\s*$)", message):
            kv[k.upper()] = v.strip()

        run_as = kv.get("USER") or ""
        command = kv.get("COMMAND") or ""

        # Fallback to original regex if kv extraction didn't work
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

    def parse_windows_event(self, message: str) -> dict:
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
                    "logon_type_desc": self._windows_logon_type(logon_type),
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

    # -----------------------------------------------------------------------
    # Normalisation
    # -----------------------------------------------------------------------

    def normalize(self, parsed: dict) -> "SecurityEventCreate":
        """Convert a parsed dict into a SecurityEventCreate."""
        now = datetime.now(timezone.utc)
        timestamp = parsed.get("timestamp")
        if not isinstance(timestamp, datetime):
            timestamp = now

        return SecurityEventCreate(
            timestamp=timestamp,
            source_ip=parsed.get("source_ip"),
            destination_ip=parsed.get("destination_ip"),
            source_port=parsed.get("source_port"),
            destination_port=parsed.get("destination_port"),
            hostname=parsed.get("hostname"),
            log_source=parsed.get("log_source", "api"),
            log_type=parsed.get("log_type", "generic"),
            severity=self.classify_severity(parsed),
            category=parsed.get("category", self._category_from_log_type(parsed.get("log_type", "generic"))),
            message=parsed.get("message"),
            raw_log=parsed.get("raw_log"),
            parsed_fields=parsed.get("parsed_fields"),
            tags=self.extract_tags(parsed),
            country=parsed.get("country"),
            user=parsed.get("user"),
            process=parsed.get("process"),
            action=parsed.get("action"),
        )

    def classify_severity(self, parsed: dict) -> str:
        """Heuristic severity classification."""
        existing = parsed.get("severity")
        if existing and existing in ("low", "medium", "high", "critical"):
            return existing

        action = parsed.get("action", "")
        log_type = parsed.get("log_type", "")
        pf = parsed.get("parsed_fields") or {}
        event = pf.get("event", "")
        message = (parsed.get("message") or "").lower()

        # Critical indicators
        if any(w in message for w in ("ransomware", "rootkit", "backdoor", "exploit")):
            return "critical"
        if event in ("privilege_escalation",) or (log_type == "sudo" and pf.get("run_as") == "root"):
            return "high"

        # High
        if action == "failed" and log_type == "ssh":
            return "medium"  # Single failure is medium; brute force detected by correlation
        if event in ("logon_failure", "invalid_user", "max_auth_exceeded"):
            return "medium"
        if event in ("user_account_created", "group_member_added"):
            return "high"

        # HTTP 5xx
        status_code = pf.get("status_code", 0)
        if status_code and isinstance(status_code, int):
            if status_code >= 500:
                return "medium"
            if status_code in (401, 403):
                return "low"

        # Firewall deny
        if log_type == "firewall" and action == "deny":
            return "low"

        # Windows logon failure
        if log_type == "windows" and action == "failed":
            return "medium"

        return "low"

    def extract_tags(self, parsed: dict) -> list[str]:
        tags = []
        log_type = parsed.get("log_type", "")
        action = parsed.get("action", "")
        pf = parsed.get("parsed_fields") or {}
        event = pf.get("event", "")

        if log_type:
            tags.append(log_type)
        if action:
            tags.append(action)
        if event:
            tags.append(event)

        # Add severity tag
        severity = parsed.get("severity", "")
        if severity:
            tags.append(f"severity:{severity}")

        # Source indicators
        if parsed.get("source_ip"):
            tags.append("has_src_ip")
        if parsed.get("user"):
            tags.append("has_user")

        return list(set(tags))

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _classify_by_process_and_message(self, process: str, message: str) -> tuple[str, dict, dict]:
        """Return (log_type, top_level_fields, extra_parsed_fields) based on process name and message."""
        proc_lower = (process or "").lower()
        msg_lower = (message or "").lower()

        if "sshd" in proc_lower:
            ssh_result = self.parse_ssh_log(message)
            top = {k: v for k, v in ssh_result.items() if k in ("source_ip", "user", "action", "source_port", "severity")}
            return "ssh", top, ssh_result.get("parsed_fields", {})

        if any(p in proc_lower for p in ("apache", "httpd", "nginx")):
            web_result = self.parse_apache_log(message)
            log_type = "nginx" if "nginx" in proc_lower else "apache"
            top = {k: v for k, v in web_result.items() if k in ("source_ip", "user", "action", "severity")}
            return log_type, top, web_result.get("parsed_fields", {})

        if "sudo" in proc_lower:
            sudo_result = self.parse_sudo_log(message)
            top = {k: v for k, v in sudo_result.items() if k in ("user", "action", "severity")}
            return "sudo", top, sudo_result.get("parsed_fields", {})

        if "kernel" in proc_lower or "iptables" in msg_lower:
            ipt_result = self.parse_iptables_log(message)
            top = {k: v for k, v in ipt_result.items() if k in ("source_ip", "destination_ip", "source_port", "destination_port", "action")}
            return "firewall", top, ipt_result.get("parsed_fields", {})

        if "windows" in proc_lower or "security" in proc_lower:
            win_result = self.parse_windows_event(message)
            top = {k: v for k, v in win_result.items() if k in ("source_ip", "user", "action", "severity")}
            return "windows", top, win_result.get("parsed_fields", {})

        return "generic", {}, {}

    def _parse_cef_extension(self, ext_str: str) -> dict:
        result = {}
        # CEF extension: key=value pairs, value may contain \= escaped equals
        # Use a simple state-machine parser
        parts = re.findall(r"(\w+)=((?:[^=\\]|\\.)*?)(?=\s+\w+=|$)", ext_str)
        for key, val in parts:
            result[key] = val.strip()
        return result

    def _cef_sev_to_str(self, sev: int) -> str:
        if sev <= 3:
            return "low"
        if sev <= 6:
            return "medium"
        if sev <= 8:
            return "high"
        return "critical"

    def _normalise_severity(self, sev: str) -> str:
        sev = sev.lower()
        if sev in ("critical", "emergency", "alert", "emerg"):
            return "critical"
        if sev in ("error", "err", "high", "severe"):
            return "high"
        if sev in ("warning", "warn", "medium", "notice"):
            return "medium"
        return "low"

    def _category_from_log_type(self, log_type: str) -> str:
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

    def _windows_logon_type(self, logon_type: int) -> str:
        mapping = {
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
        return mapping.get(logon_type, f"Unknown({logon_type})")
