# SiemLess

A full-featured, self-hosted SIEM (Security Information and Event Management) tool built with Python FastAPI, React, and PostgreSQL.

## Features

- **Log Ingestion**: Syslog (UDP/TCP), file upload, HTTP API, batch ingestion
- **Log Parsing**: SSH, Apache/Nginx, iptables, sudo, Windows events, CEF, syslog RFC3164/5424, JSON
- **Correlation Rules**: YAML-like rule engine with threshold and sliding-window detection
- **Alerting**: Email, Slack, and webhook notifications
- **Threat Intelligence**: IP reputation, hash lookups via AbuseIPDB and VirusTotal
- **Dashboard**: Real-time charts, event timeline, top sources, severity distribution
- **Search**: Full-text search with structured filter syntax

## Quick Start

```bash
# Clone and start
git clone https://github.com/mrnickrushing/siemless
cd siemless

# Optional: configure threat intel keys, email, Slack
cp .env.example .env
# edit .env

# Launch all services
docker compose up -d

# Open the dashboard
open http://localhost:3000
```

## Log Ingestion

### Syslog
Point your devices to `udp://localhost:514`. The syslog server starts automatically on internal port 5514; the Railway TCP proxy (or the Docker port mapping) forwards external port 514 to it.

### HTTP API
```bash
# Single event
curl -X POST http://localhost:8000/api/v1/ingest/event \
  -H "Content-Type: application/json" \
  -d '{"raw_log": "May 25 10:00:01 myhost sshd[1234]: Failed password for root from 10.0.0.1 port 22 ssh2", "log_source": "syslog"}'

# Raw log line
curl -X POST http://localhost:8000/api/v1/ingest/raw \
  -H "Content-Type: application/json" \
  -d '{"raw_log": "...", "log_source": "syslog", "log_type": "ssh"}'

# Upload log file
curl -X POST http://localhost:8000/api/v1/ingest/file \
  -F "file=@/var/log/auth.log" \
  -F "log_source=syslog"
```

### rsyslog forwarding
```
# /etc/rsyslog.conf
*.* @your-siemless-host:514   # external port — proxied to internal 5514
```

## Built-in Correlation Rules

| Rule | Description | Threshold |
|------|-------------|-----------|
| SSH Brute Force | Failed SSH auth from same IP | 5 in 5 min |
| Port Scan | Distinct dest ports from same IP | 20 in 1 min |
| Multiple Failed Logins | Failed logins for same user | 3 in 10 min |
| Privilege Escalation | sudo to root detected | 1 |
| Malware C2 | Traffic to threat intel IP | 1 |

## API Reference

The API is available at `http://localhost:8000/api/v1`. Interactive docs at `http://localhost:8000/docs`.

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /ingest/event | Ingest single event |
| POST | /ingest/batch | Ingest batch (up to 1000) |
| POST | /ingest/file | Upload log file |
| GET | /events | List/filter events |
| GET | /alerts | List alerts |
| PATCH | /alerts/{id} | Update alert status |
| GET | /rules | List rules |
| POST | /rules | Create rule |
| GET | /search?q= | Full-text search |
| GET | /stats/overview | Dashboard stats |
| POST | /threat-intel/check | Check indicator |

## Architecture

```
┌─────────────┐    ┌──────────────────────────────────────────┐
│   Sources   │    │              SiemLess Stack               │
│             │    │                                           │
│  Syslog ───────► │  FastAPI Backend (port 8000)             │
│  HTTP API ──────►│    ├─ Log Parser                         │
│  File Upload ───►│    ├─ Correlation Engine                  │
│             │    │    ├─ Threat Intel Service               │
└─────────────┘    │    └─ Alerting Service                   │
                   │           │                               │
                   │    PostgreSQL ◄──────────────────────────│
                   │    Redis (pub/sub + cache)                │
                   │                                           │
                   │  React Frontend (port 3000)               │
                   │    ├─ Dashboard                           │
                   │    ├─ Events / Search                     │
                   │    ├─ Alerts                              │
                   │    ├─ Rules                               │
                   │    └─ Threat Intel                        │
                   └──────────────────────────────────────────┘
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL async URL |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `SECRET_KEY` | (required) | JWT signing secret |
| `SYSLOG_PORT` | `5514` | UDP/TCP syslog listener port (internal; Railway proxy maps external 514 → 5514) |
| `THREAT_INTEL_ABUSEIPDB_KEY` | - | AbuseIPDB API key |
| `THREAT_INTEL_VIRUSTOTAL_KEY` | - | VirusTotal API key |
| `SLACK_WEBHOOK_URL` | - | Slack incoming webhook |
| `SMTP_HOST` | - | SMTP server for email alerts |
| `ALERT_EMAIL` | - | Destination email for alerts |

## Development

```bash
# Backend only (needs running postgres and redis)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend
npm install
npm run dev
```
