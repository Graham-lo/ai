# Setup Guide

This guide covers prerequisites, environment variables, and how to run the project on Windows, macOS, and Linux.

## Prerequisites

Common:
- Git
- Docker Desktop (Windows/macOS) or Docker Engine + Docker Compose (Linux)

Optional (local dev):
- Python 3.11
- Node.js 20+

## Environment Variables

Create a `.env` file in repo root:

```
MASTER_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
API_TOKEN=devtoken
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Notes:
- `MASTER_KEY` must be a 32-byte key in base64 (AES-GCM).
- `API_TOKEN` is the backend auth token used by the frontend.
- `DEEPSEEK_API_KEY` is optional if you only need raw reports.

## Docker (Recommended)

### Windows
1. Install Docker Desktop and enable WSL2 backend.
2. Start Docker Desktop.
3. In `F:\vscode\jys\repo`:

```
docker compose up --build
```

Backend: `http://localhost:18000`  
Frontend: `http://localhost:13000`

### macOS / Linux
1. Install Docker Desktop (macOS) or Docker Engine + Compose (Linux).
2. In repo root:

```
docker compose up --build
```

Backend: `http://localhost:18000`  
Frontend: `http://localhost:13000`

## Local Dev (Optional)

### Backend (FastAPI)
1. Create venv and install deps:

```
python -m venv .venv
.\.venv\Scripts\activate    # Windows PowerShell
pip install -r backend/requirements.txt
```

2. Run migrations:

```
cd backend
alembic -c /app/alembic.ini upgrade head
```

3. Start API:

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)
1. Install deps:

```
cd frontend
npm install
```

2. Start dev server:

```
npm run dev
```

Default dev frontend: `http://localhost:3000`

## Common Troubleshooting

- Port conflict: change ports in `docker-compose.yml`.
- Docker image pull failure: configure Docker Desktop proxy if needed.
- DeepSeek failure: verify `DEEPSEEK_API_KEY` and network access.

