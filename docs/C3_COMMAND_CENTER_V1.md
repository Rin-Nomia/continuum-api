# Continuum Command Center (C3) v1.1

## Overview

C3 is an independent, visual operations console for commercial runtime governance.

Design goals:
- strong operator control
- zero raw content exposure
- non-invasive read from `usage.db`

## Security Model

- **Independent port**: default `127.0.0.1:8501`
- **Admin authentication**: requires `C3_ADMIN_PASSWORD`
- **Read-only telemetry path**: dashboard reads metrics from `usage.db` (SQLite)
- **Heartbeat anti-tamper**: usage events include HMAC heartbeat fields; dashboard verifies integrity

## Required Environment Variables

- `LOG_SALT` (required, also used as fallback signing key)
- `C3_ADMIN_PASSWORD` (required for login)
- `LICENSE_KEY` (required for decrypting `.key` / `.enc`)
- `LICENSE_FILE` (optional, default `license/license.enc`)
- `USAGE_DB_PATH` (optional, default `logs/usage.db`)
- `USAGE_SIGNING_KEY` (optional, default to `LOG_SALT`)

## Launch

```bash
python3 manage.py dashboard
```

Optional custom bind:

```bash
python3 manage.py dashboard --host 127.0.0.1 --port 8501
```

Direct Streamlit mode:

```bash
streamlit run c3_dashboard.py --server.address 127.0.0.1 --server.port 8501
```

## Functional Layout (Mockup Description)

```
[C3 Login]
  └─ Admin Password

[License Identity]
  ├─ Customer Name
  ├─ UID
  └─ Tier (Lite / Pro / Enterprise)

[TTL Countdown]
  └─ Days remaining (<=30 days turns warning color)

[Mode Status]
  ├─ LOG_SALT mounted (OK/MISSING)
  ├─ Decision Health (24h status)
  └─ Heartbeat Guard (OK/ALERT)

[Traffic Quota Dashboard]
  ├─ Progress bar: current usage / quota
  ├─ 30-day ratio chart: ALLOW / GUIDE / ERROR
  └─ 30-day volume chart

[Cost Estimator]
  ├─ Base monthly cost
  ├─ Overage count
  ├─ Overage fee
  └─ Projected total

[Action Module]
  ├─ Generate Audit File        -> logs/usage/EVIDENCE_SUMMARY.sig
  ├─ Update License (.key/.enc) -> replace LICENSE_FILE after decrypt validation
  └─ Scrub Log Export           -> logs/exports/scrub_log_export_<timestamp>.json
```

## Action Module Output Notes

### 1) Generate Audit File
- Output: `logs/usage/EVIDENCE_SUMMARY.sig`
- Content: encrypted and signed monthly summary (content-free)

### 2) Update License
- Validates uploaded license envelope by decrypting with `LICENSE_KEY`
- Keeps backup of old license before replacing

### 3) Scrub Log Export
- Exports content-free records aligned to `EVIDENCE_SCHEMA_V1` key contract
- No raw text persistence

