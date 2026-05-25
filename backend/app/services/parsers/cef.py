"""CEF (Common Event Format) log parser."""
import re

from app.services.parsers.base import RE_CEF


def _parse_cef_extension(ext_str: str) -> dict:
    result = {}
    parts = re.findall(r"(\w+)=((?:[^=\\]|\\.)*?)(?=\s+\w+=|$)", ext_str)
    for key, val in parts:
        result[key] = val.strip()
    return result


def _cef_sev_to_str(sev: int) -> str:
    if sev <= 3:
        return "low"
    if sev <= 6:
        return "medium"
    if sev <= 8:
        return "high"
    return "critical"


def parse_cef(raw_log: str) -> dict:
    """Parse a CEF-formatted log line into a normalised dict."""
    m = RE_CEF.match(raw_log.strip())
    if not m:
        return {"message": raw_log, "log_type": "generic"}

    gd = m.groupdict()
    ext = _parse_cef_extension(gd.get("extension", ""))

    severity_raw = gd.get("severity", "5")
    try:
        severity = _cef_sev_to_str(int(severity_raw))
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
