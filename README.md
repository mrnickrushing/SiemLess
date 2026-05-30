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

## API Reference

The API is available at `http://localhost:8000/api/v1`. Interactive docs are available at `http://localhost:8000/api/docs`.
