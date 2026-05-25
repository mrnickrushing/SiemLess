"""
Shared pytest fixtures — sample raw log strings for every format.
"""
import pytest


# ---------------------------------------------------------------------------
# SSH samples
# ---------------------------------------------------------------------------

@pytest.fixture
def ssh_failed_password():
    return "Failed password for root from 203.0.113.42 port 54321 ssh2"

@pytest.fixture
def ssh_failed_invalid_user():
    return "Failed password for invalid user deploy from 198.51.100.7 port 22322 ssh2"

@pytest.fixture
def ssh_accepted():
    return "Accepted publickey for alice from 10.0.0.5 port 49821 ssh2"

@pytest.fixture
def ssh_invalid_user():
    return "Invalid user testuser from 198.51.100.99 port 40001"

@pytest.fixture
def ssh_max_auth():
    return "error: maximum authentication attempts exceeded for root from 203.0.113.1 port 22 ssh2"


# ---------------------------------------------------------------------------
# Apache / web samples
# ---------------------------------------------------------------------------

@pytest.fixture
def apache_200():
    return '192.168.1.1 - - [25/May/2026:10:00:00 +0000] "GET /index.html HTTP/1.1" 200 1024 "-" "Mozilla/5.0"'

@pytest.fixture
def apache_401():
    return '10.0.0.1 - bob [25/May/2026:10:01:00 +0000] "GET /admin HTTP/1.1" 401 512 "-" "curl/7.81.0"'

@pytest.fixture
def apache_500():
    return '172.16.0.1 - - [25/May/2026:10:02:00 +0000] "POST /api/data HTTP/1.1" 500 256 "-" "python-requests/2.31"'

@pytest.fixture
def apache_403():
    return '10.10.10.10 - - [25/May/2026:10:03:00 +0000] "GET /etc/passwd HTTP/1.1" 403 128 "-" "BadBot/1.0"'


# ---------------------------------------------------------------------------
# Firewall / iptables samples
# ---------------------------------------------------------------------------

@pytest.fixture
def iptables_drop():
    return "kernel: [12345.678] IN=eth0 OUT= MAC=00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd SRC=203.0.113.5 DST=10.0.0.1 LEN=40 TOS=0x00 PREC=0x00 TTL=244 ID=54321 PROTO=TCP SPT=45678 DPT=22 WINDOW=65535 RES=0x00 SYN URGP=0 DROP"

@pytest.fixture
def iptables_accept():
    return "kernel: IN=eth0 SRC=10.0.0.5 DST=10.0.0.1 PROTO=TCP SPT=80 DPT=443 ACCEPT"

@pytest.fixture
def iptables_no_ports():
    return "kernel: IN=eth0 SRC=1.2.3.4 DST=5.6.7.8 PROTO=ICMP DROP"


# ---------------------------------------------------------------------------
# Sudo samples
# ---------------------------------------------------------------------------

@pytest.fixture
def sudo_root():
    return "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash"

@pytest.fixture
def sudo_non_root():
    return "bob : TTY=pts/1 ; PWD=/tmp ; USER=www-data ; COMMAND=/usr/bin/systemctl restart nginx"


# ---------------------------------------------------------------------------
# Windows samples
# ---------------------------------------------------------------------------

@pytest.fixture
def windows_4625():
    return "Security Event ID 4625: Logon Failure\nLogon Type: 3\nAccount Name: Administrator\nSource Network Address: 203.0.113.88"

@pytest.fixture
def windows_4624():
    return "Security Event ID 4624: Logon Success\nLogon Type: 3\nAccount Name: alice\nSource Network Address: 10.0.0.5"

@pytest.fixture
def windows_4720():
    return "Security Event ID 4720: A user account was created. Account Name: hacker"

@pytest.fixture
def windows_4732():
    return "Security Event ID 4732: A member was added to a security-enabled local group."


# ---------------------------------------------------------------------------
# CEF samples
# ---------------------------------------------------------------------------

@pytest.fixture
def cef_standard():
    return "CEF:0|Vendor|Product|1.0|100|Connection blocked|7|src=203.0.113.1 dst=10.0.0.1 spt=12345 dpt=443 act=block"

@pytest.fixture
def cef_low_severity():
    return "CEF:0|Vendor|Product|1.0|200|Info event|2|src=10.0.0.1 dst=10.0.0.2"

@pytest.fixture
def cef_no_extension():
    return "CEF:0|Vendor|Product|1.0|300|Test|5|"


# ---------------------------------------------------------------------------
# JSON samples
# ---------------------------------------------------------------------------

@pytest.fixture
def json_basic():
    return '{"timestamp": "2026-05-25T10:00:00Z", "message": "test event", "severity": "high", "src_ip": "1.2.3.4"}'

@pytest.fixture
def json_epoch():
    return '{"time": 1748160000, "msg": "epoch timestamp test", "level": "warning"}'
