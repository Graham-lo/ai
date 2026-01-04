# Trade Check Engine (MVP)

This project provides a plug-in based trading diagnostic engine with a FastAPI backend, Next.js frontend, and Postgres storage.

## Quick Start (Docker)

1. Create `.env` in repo root (example):

```
MASTER_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
API_TOKEN=devtoken
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

2. Start services:

```
docker compose up --build
```

Backend runs on `http://localhost:18000`, frontend on `http://localhost:13000`.

## Full Setup Guide

See `SETUP.md` for Windows/macOS/Linux prerequisites, Docker and local dev steps, and environment variable reference.

## Security Notes

- Use read-only API keys and enable IP whitelisting.
- Secrets are encrypted at rest and never returned in plaintext.
- No trading or withdrawal endpoints are implemented.

## Sign Convention

- Cashflow amount uses positive for inflow and negative for outflow.
- Trading fees and interest are treated as costs (absolute values) in net after fees.

## CLI Usage

```
python -m app.cli sync --preset last_30d --exchange bybit
python -m app.cli report --preset last_month --net-mode fees_plus_funding --exchange all
```

## Adding a New Plugin

1. Copy `backend/app/plugins/template` to a new folder.
2. Edit `manifest.json` with auth_fields and capabilities.
3. Implement `adapter.py` and `client.py`.
4. Restart backend to load the manifest.

## Report Net Modes

- `fees_only`: Net after Fees (excludes funding)
- `fees_plus_funding`: Net after Fees & Funding

Funding is always shown separately.
