"""
LogParser dispatcher — detects format, delegates to the appropriate
format-specific module, then normalises the result.
"""
import json
from datetime import datetime, timezone

from app.schemas.event import SecurityEventCreate
from app.services.parsers.base import (
    RE_RFC3164,
    RE_RFC5424,
    MONTHS,
    parse_priority,
    syslog_sev_to_str,
    normalise_severity,
    category_from_log_type,
)
from app.services.parsers.ssh import parse_ssh_log
from app.services.parsers.apache import parse_apache_log, parse_nginx_log
from app.services.parsers.firewall import parse_iptables_log
from app.services.parsers.sudo import parse_sudo_log
from app.services.parsers.windows import parse_windows_event
from app.services.parsers.json_log import parse_json_log
from app.services.parsers.cef import parse_cef


class LogParser:
    """Detects, parses, and normalises diverse log formats."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, raw_log: str, log_source: str = "api") -> dict:
        raw_log = raw_log.strip()
        fmt = self.detect_format(raw_log)

        if fmt == "json":
            parsed = parse_json_log(raw_log)
        elif fmt == "cef":
            parsed = parse_cef(raw_log)
        elif fmt == "rfc5424":
            parsed = self._parse_syslog_rfc5424(raw_log)
        elif fmt == "rfc3164":
            parsed = self._parse_syslog_rfc3164(raw_log)
        else:
            parsed = {"message": raw_log, "log_type": "generic"}

        parsed["raw_log"] = raw_log
        parsed["log_source"] = log_source
        return parsed

    def detect_format(self, raw_log: str) -> str:
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

    def normalize(self, parsed: dict) -> SecurityEventCreate:
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
            category=parsed.get(
                "category",
                category_from_log_type(parsed.get("log_type", "generic")),
            ),
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
        existing = parsed.get("severity")
        if existing and existing in ("low", "medium", "high", "critical"):
            return existing

        action = parsed.get("action", "")
        log_type = parsed.get("log_type", "")
        pf = parsed.get("parsed_fields") or {}
        event = pf.get("event", "")
        message = (parsed.get("message") or "").lower()

        if any(w in message for w in ("ransomware", "rootkit", "backdoor", "exploit")):
            return "critical"
        if event == "privilege_escalation" or (log_type == "sudo" and pf.get("run_as") == "root"):
            return "high"
        if action == "failed" and log_type == "ssh":
            return "medium"
        if event in ("logon_failure", "invalid_user", "max_auth_exceeded"):
            return "medium"
        if event in ("user_account_created", "group_member_added"):
            return "high"

        status_code = pf.get("status_code", 0)
        if isinstance(status_code, int) and status_code:
            if status_code >= 500:
                return "medium"
            if status_code in (401, 403):
                return "low"

        if log_type == "firewall" and action == "deny":
            return "low"
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
        if parsed.get("severity"):
            tags.append(f"severity:{parsed['severity']}")
        if parsed.get("source_ip"):
            tags.append("has_src_ip")
        if parsed.get("user"):
            tags.append("has_user")

        return list(set(tags))

    # ------------------------------------------------------------------
    # Syslog parsers (kept here — they rely on the classify/dispatch logic)
    # ------------------------------------------------------------------

    def _parse_syslog_rfc3164(self, raw_log: str) -> dict:
        m = RE_RFC3164.match(raw_log.strip())
        if not m:
            return {"message": raw_log, "log_type": "generic"}

        gd = m.groupdict()
        facility, sev_num = parse_priority(gd.get("pri"))

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
            "severity": syslog_sev_to_str(sev_num),
            "parsed_fields": {"facility": facility, "pid": gd.get("pid"), **extra},
        }
        for k, v in top_fields.items():
            if v is not None:
                result[k] = v
        return result

    def _parse_syslog_rfc5424(self, raw_log: str) -> dict:
        m = RE_RFC5424.match(raw_log.strip())
        if not m:
            return {"message": raw_log, "log_type": "generic"}

        gd = m.groupdict()
        facility, sev_num = parse_priority(gd.get("pri"))

        try:
            ts_raw = gd["timestamp"]
            timestamp = (
                datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if ts_raw and ts_raw != "-"
                else datetime.now(timezone.utc)
            )
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
            "severity": syslog_sev_to_str(sev_num),
            "parsed_fields": {
                "facility": facility,
                "procid": gd.get("procid"),
                "msgid": gd.get("msgid"),
                "structured_data": gd.get("structured_data"),
                **extra,
            },
        }
        for k, v in top_fields.items():
            if v is not None:
                result[k] = v
        return result

    def _classify_by_process_and_message(
        self, process: str, message: str
    ) -> tuple[str, dict, dict]:
        proc_lower = (process or "").lower()

        if "sshd" in proc_lower:
            r = parse_ssh_log(message)
            top = {k: r[k] for k in ("source_ip", "user", "action", "source_port", "severity") if k in r}
            return "ssh", top, r.get("parsed_fields", {})

        if any(p in proc_lower for p in ("apache", "httpd", "nginx")):
            r = parse_apache_log(message)
            log_type = "nginx" if "nginx" in proc_lower else "apache"
            top = {k: r[k] for k in ("source_ip", "user", "action", "severity") if k in r}
            return log_type, top, r.get("parsed_fields", {})

        if "sudo" in proc_lower:
            r = parse_sudo_log(message)
            top = {k: r[k] for k in ("user", "action", "severity") if k in r}
            return "sudo", top, r.get("parsed_fields", {})

        if "kernel" in proc_lower or "iptables" in message.lower():
            r = parse_iptables_log(message)
            top = {k: r[k] for k in ("source_ip", "destination_ip", "source_port", "destination_port", "action") if k in r}
            return "firewall", top, r.get("parsed_fields", {})

        if "windows" in proc_lower or "security" in proc_lower:
            r = parse_windows_event(message)
            top = {k: r[k] for k in ("source_ip", "user", "action", "severity") if k in r}
            return "windows", top, r.get("parsed_fields", {})

        return "generic", {}, {}
