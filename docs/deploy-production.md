# Production Deployment Guide

This guide covers production deployment considerations for route-llm-gateway.

## Environment Variables

### Backend Environment Variables

#### Required
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins (e.g., `https://yourdomain.com,https://www.yourdomain.com`)

#### Optional (Provider API Keys)
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `DEEPSEEK_API_KEY`: DeepSeek API key
- `GEMINI_API_KEY`: Gemini API key

#### Optional (Model Defaults)
- `OPENAI_DEFAULT_MODEL`: Default OpenAI model (default: `gpt-4o-mini`)
- `ANTHROPIC_DEFAULT_MODEL`: Default Anthropic model (default: `claude-sonnet-4-5-20250929`)
- `DEEPSEEK_DEFAULT_MODEL`: Default DeepSeek model (default: `deepseek-chat`)
- `GEMINI_DEFAULT_MODEL`: Default Gemini model (default: `gemini-pro`)

### Frontend Build Variables

**Important**: Frontend environment variables must be set at **build time**, not runtime.

When building the frontend image, set `VITE_API_BASE_URL`:

```bash
docker build \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com \
  -f deploy/docker/frontend.Dockerfile \
  -t route-llm-gateway-frontend:latest \
  .
```

## Docker Compose Production

### 1. Build Images

Build backend and frontend images with proper environment variables:

```bash
# Build backend
docker build -f deploy/docker/backend.Dockerfile -t route-llm-gateway-backend:latest .

# Build frontend (IMPORTANT: Set VITE_API_BASE_URL)
docker build \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com \
  -f deploy/docker/frontend.Dockerfile \
  -t route-llm-gateway-frontend:latest \
  .
```

### 2. Create Environment File

Create a `.env` file or set environment variables:

```bash
# Database
POSTGRES_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql+psycopg2://route_llm:your_secure_password_here@postgres:5432/route_llm

# Redis
REDIS_URL=redis://redis:6379/0

# CORS (comma-separated list of allowed origins)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...

# Frontend API URL (for build)
VITE_API_BASE_URL=https://api.yourdomain.com
```

### 3. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d
```

## CORS Configuration

### Development
Default CORS origins include:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:80` (Docker frontend)
- `http://localhost` (Default localhost)

### Production
Set `CORS_ORIGINS` environment variable with your production domains:

```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com,https://app.yourdomain.com
```

**Security Note**: Only include domains you trust. Never use `*` in production.

## Frontend API URL Configuration

The frontend needs to know where the backend API is located. This is configured at **build time** using `VITE_API_BASE_URL`.

### Example Build Commands

```bash
# Local development
docker build --build-arg VITE_API_BASE_URL=http://localhost:8000 -f deploy/docker/frontend.Dockerfile -t route-llm-gateway-frontend:dev .

# Production
docker build --build-arg VITE_API_BASE_URL=https://api.yourdomain.com -f deploy/docker/frontend.Dockerfile -t route-llm-gateway-frontend:prod .
```

### Why Build Time?

Vite environment variables (prefixed with `VITE_`) are embedded into the JavaScript bundle at build time. They cannot be changed at runtime. This is a security feature and performance optimization.

## Network Configuration

In Docker Compose, services can communicate using service names:
- `backend` → Backend service
- `frontend` → Frontend service
- `postgres` → PostgreSQL service
- `redis` → Redis service

However, **browser-based requests** (from the user's browser) must use `localhost` or your public domain, not Docker service names.

## Troubleshooting

### Network Error in Frontend

1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check CORS configuration:**
   - Verify `CORS_ORIGINS` includes your frontend URL
   - Check browser console for CORS errors

3. **Check frontend API URL:**
   - Open browser DevTools → Network tab
   - Check the request URL matches `VITE_API_BASE_URL` used at build time

### CORS Errors

If you see CORS errors in the browser console:

1. Add your frontend domain to `CORS_ORIGINS`
2. Restart backend service
3. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R)

## Security Checklist

- [ ] Change default passwords (`POSTGRES_PASSWORD`)
- [ ] Set `CORS_ORIGINS` to your production domains only
- [ ] Use HTTPS in production
- [ ] Set `VITE_API_BASE_URL` to your production API URL
- [ ] Keep API keys secure (use secrets management)
- [ ] Enable authentication (default admin user should change password)
- [ ] Review and restrict CORS origins

