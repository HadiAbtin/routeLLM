# Docker Compose Deployment Guide

This guide explains how to run route-llm-gateway using Docker Compose for local development and testing.

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB of available RAM
- Ports 8000, 5173, 5432, 6379, 9090 available (or modify in `docker-compose.dev.yml`)

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd route-llm-gateway
   ```

2. **Create environment file:**
   ```bash
   cp .env.backend.example .env.backend
   # Edit .env.backend and add your API keys
   ```

3. **Start all services:**
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```

4. **Access the services:**
   - Frontend Dashboard: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Prometheus: http://localhost:9090
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

5. **Login to Dashboard:**
   - Default email: `admin@example.com`
   - Default password: `admin`
   - ⚠️ **Important**: Change the password on first login!

## Environment Variables

Create a `.env.backend` file in the project root with the following variables:

### Required (for LLM providers)
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic (optional)
ANTHROPIC_API_KEY=sk-ant-...

# DeepSeek (optional)
DEEPSEEK_API_KEY=sk-...

# Gemini (optional)
GEMINI_API_KEY=...
```

### Optional Configuration
```bash
# Database (defaults work for docker-compose)
DATABASE_URL=postgresql+psycopg2://route_llm:route_llm@postgres:5432/route_llm

# Redis (defaults work for docker-compose)
REDIS_URL=redis://redis:6379/0

# Model defaults
OPENAI_DEFAULT_MODEL=gpt-4o-mini
ANTHROPIC_DEFAULT_MODEL=claude-3-5-haiku-20241022
DEEPSEEK_DEFAULT_MODEL=deepseek-chat
GEMINI_DEFAULT_MODEL=gemini-pro
```

## Services

The docker-compose setup includes:

- **backend**: FastAPI application (port 8000)
  - Handles API requests and routing logic
  - Token usage tracking with Redis
  - File management
  - Authentication (JWT)
- **frontend**: React application served by nginx (port 5173)
  - Real-time dashboard with auto-refresh
  - Provider health monitoring
  - Token usage analytics
  - Key management interface
- **worker**: RQ worker for processing async runs
  - Background job processing
  - Token usage recording
- **postgres**: PostgreSQL database (port 5432)
  - Provider keys storage
  - Agent runs and status
  - User accounts
  - File metadata
- **redis**: Redis for job queue and timeseries (port 6379)
  - Job queue for async processing
  - Token usage timeseries storage
- **prometheus**: Metrics collection (port 9090)
  - Request counts
  - Error rates
  - Key status metrics

## Common Operations

### View logs
```bash
# All services
docker compose -f docker-compose.dev.yml logs -f

# Specific service
docker compose -f docker-compose.dev.yml logs -f backend
docker compose -f docker-compose.dev.yml logs -f worker
```

### Stop services
```bash
docker compose -f docker-compose.dev.yml down
```

### Stop and remove volumes (clean slate)
```bash
docker compose -f docker-compose.dev.yml down -v
```

### Rebuild specific service
```bash
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up -d backend
```

## Troubleshooting

### Port already in use
If a port is already in use, modify `docker-compose.dev.yml` to use different ports.

### Database connection errors
Ensure PostgreSQL container is running:
```bash
docker compose -f docker-compose.dev.yml ps postgres
```

### Worker not processing jobs
Check worker logs:
```bash
docker compose -f docker-compose.dev.yml logs worker
```

Ensure Redis is accessible:
```bash
docker compose -f docker-compose.dev.yml exec redis redis-cli ping
```

### Frontend can't connect to backend
Check CORS settings in `backend/app/main.py` and ensure backend is running.

## Development Tips

1. **Hot reload**: Backend supports hot reload with `--reload` flag (already configured in docker-compose)
2. **Database migrations**: Run migrations manually if needed:
   ```bash
   docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
   ```
3. **Access database**: Use psql to inspect database:
   ```bash
   docker compose -f docker-compose.dev.yml exec postgres psql -U route_llm -d route_llm
   ```
4. **View token usage data in Redis**:
   ```bash
   docker compose -f docker-compose.dev.yml exec redis redis-cli
   # Then in redis-cli:
   KEYS key_tokens:*
   LRANGE key_tokens:{key_id} 0 -1
   ```
5. **Create admin user** (if needed):
   ```bash
   docker compose -f docker-compose.dev.yml exec backend python create_admin_user.py
   ```

## Dashboard Features

Once logged in, you can:

- **Monitor Provider Health**: View real-time status of all providers
- **Track Token Usage**: See token consumption per provider with time filtering (hour/day/week/month)
- **Manage Keys**: View and manage provider keys
- **View Key Analytics**: Detailed token usage charts for individual keys
- **Monitor Error Rates**: Track success and error rates per provider
- **Auto-refresh**: Enable automatic data refresh for real-time monitoring

