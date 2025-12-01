# Troubleshooting Guide

## Issue 1: Docker Hub 403 Forbidden Error

### Problem
When running `docker compose up`, you get:
```
403 Forbidden: Since Docker is a US company, we must comply with US export control regulations...
```

This happens because Docker Hub blocks access from certain countries including Iran.

### Solutions

#### Option A: Use Alternative Image Sources (Recommended)

You can modify the Dockerfiles to use alternative registries or pre-pulled images.

**For backend.Dockerfile:**
- Use a local Python installation or pre-pulled image
- Or use alternative Python images from other registries

**For frontend.Dockerfile:**
- Use pre-pulled Node.js images
- Or build Node.js from source

#### Option B: Use Pre-pulled Images Locally

1. Pull images manually (if you have access via VPN/proxy):
```bash
docker pull python:3.11-slim
docker pull node:20-alpine
docker pull nginx:alpine
docker pull postgres:16
docker pull redis:7
```

2. Then run docker-compose (it will use local images)

#### Option C: Run Without Docker (Recommended for Development)

Since you're in development, you can run everything locally:

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**PostgreSQL & Redis (if needed):**
```bash
# Use local installations or run only these services in Docker
docker compose -f docker-compose.dev.yml up postgres redis
```

## Issue 2: OpenAI API Connection Error

### Problem
Error: `Failed to connect to OpenAI API: [Errno -5] No address associated with hostname`

This means the DNS cannot resolve `api.openai.com`.

### Solutions

#### Option A: Use Proxy for OpenAI API

If you have access to a proxy, you can configure httpx to use it:

1. Update `backend/app/providers/openai_provider.py` to support proxy:
```python
# In the httpx.AsyncClient call, add proxies parameter
async with httpx.AsyncClient(
    timeout=60.0,
    proxies={
        "http://": "http://your-proxy:port",
        "https://": "http://your-proxy:port"
    }
) as client:
```

2. Or set environment variable:
```bash
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

#### Option B: Use Alternative OpenAI-Compatible API

If you have access to an OpenAI-compatible API (like local LLM or alternative provider):

1. Set `OPENAI_BASE_URL` in your `.env` or `.env.backend`:
```bash
OPENAI_BASE_URL=https://your-alternative-api.com/v1
OPENAI_API_KEY=your-api-key
```

2. The code already supports custom base URLs via `openai_base_url` setting.

#### Option C: Use Local LLM (Future Enhancement)

For Phase 2+, you can add support for local LLM providers like:
- Ollama
- LocalAI
- vLLM

These don't require external API access.

### Testing Without OpenAI

You can test the API structure without actually calling OpenAI:

1. The `/v1/llm/chat` endpoint will return proper error messages
2. The OpenAPI docs at `/docs` will show the correct schema
3. Frontend will display error messages properly

## Quick Fix: Run Locally (No Docker)

For immediate development, skip Docker and run locally:

```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend  
cd frontend
npm install
npm run dev

# Terminal 3: Optional - PostgreSQL & Redis only
docker compose -f docker-compose.dev.yml up postgres redis
```

This avoids the Docker Hub issue entirely.

