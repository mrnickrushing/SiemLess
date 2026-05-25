"""IPTables / firewall log parser."""
import re


def parse_iptables_log(message: str) -> dict:
    """Parse an iptables kernel log line into a normalised dict."""
    action = "deny"
    msg_upper = message.upper()
    if "ACCEPT" in msg_upper:
        action = "allow"
    elif "DROP" in msg_upper or "REJECT" in msg_upper or "BLOCK" in msg_upper:
        action = "deny"

    kv: dict[str, str] = {}
    for k, v in re.findall(r'(\w+)=(\S+)', message):
        kv[k.upper()] = v

    def _int(key: str):
        try:
            return int(kv[key]) if key in kv else None
        except (ValueError, TypeError):
            return None

    return {
        "log_type": "firewall",
        "category": "network",
        "source_ip": kv.get("SRC"),
        "destination_ip": kv.get("DST"),
        "source_port": _int("SPT"),
        "destination_port": _int("DPT"),
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
