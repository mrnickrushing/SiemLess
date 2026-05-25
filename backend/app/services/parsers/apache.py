"""Apache / Nginx access and error log parsers."""
import re

RE_APACHE = re.compile(
    r'^(?P<src_ip>\S+)\s+\S+\s+(?P<user>\S+)\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<url>\S+)\s+(?P<proto>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?',
)

RE_NGINX_ERROR = re.compile(
    r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\s+"
    r"\[(?P<level>\w+)\]\s+\d+#\d+:\s+"
    r"(?P<message>.+?)(?:,\s+client:\s+(?P<client_ip>\S+))?"
)


def parse_apache_log(message: str) -> dict:
    """Parse an Apache/Nginx combined access log line."""
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


def parse_nginx_log(message: str) -> dict:
    """Nginx access log uses the same combined format as Apache."""
    result = parse_apache_log(message)
    result["log_type"] = "nginx"
    return result
