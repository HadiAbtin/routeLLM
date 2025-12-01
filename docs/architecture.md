# Architecture Overview

This document describes the architecture of Route LLM Gateway, a high-performance gateway for routing and managing LLM requests.

## System Components

### Backend (FastAPI)
- **Technology**: Python 3.11+ with FastAPI and Uvicorn
- **Location**: `backend/app/`
- **Main Entry**: `backend/app/main.py`
- **Port**: 8000
- **Features**:
  - RESTful API with OpenAPI/Swagger documentation
  - CORS enabled for frontend communication
  - JWT-based authentication
  - Health check endpoint at `/health`
  - Auto-generated API documentation at `/docs`
  - Provider abstraction layer
  - Intelligent key selection with rate limiting
  - Token usage tracking with Redis
  - File upload and management
  - Multimodal support (text + images)

### Frontend (React + Vite)
- **Technology**: React 19, TypeScript, Vite, TailwindCSS
- **Location**: `frontend/`
- **Port**: 5173 (dev), 80 (production/Docker)
- **Features**:
  - Modern React with TypeScript
  - Vite for fast development and optimized builds
  - Real-time dashboard with auto-refresh
  - Provider health monitoring
  - Token usage analytics with time filtering
  - Key management interface
  - Authentication UI
  - Responsive design with dark mode support

### Worker (RQ)
- **Technology**: Python RQ (Redis Queue)
- **Location**: `backend/worker.py`
- **Purpose**: Process async agent runs
- **Features**:
  - Background job processing
  - Job status tracking
  - Error handling and retries

### Database (PostgreSQL)
- **Image**: postgres:16
- **Port**: 5432
- **Database**: route_llm
- **User**: route_llm
- **Purpose**:
  - Store provider keys and configuration
  - Store agent runs and status
  - Store user accounts and authentication
  - Store file metadata

### Cache & Queue (Redis)
- **Image**: redis:7
- **Port**: 6379
- **Purpose**:
  - Job queue for async processing
  - Token usage timeseries storage
  - Shared state between backend and worker

### Monitoring (Prometheus)
- **Image**: prom/prometheus
- **Port**: 9090
- **Purpose**: Metrics collection and monitoring

## Network Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
       ├─── localhost:5173 (Frontend)
       │    └─── React Dashboard
       │
       └─── localhost:8000 (Backend API)
            │
            ├─── PostgreSQL:5432 (Database)
            ├─── Redis:6379 (Queue + Timeseries)
            └─── External APIs
                 ├─── OpenAI API
                 ├─── Anthropic API
                 ├─── DeepSeek API
                 └─── Gemini API
```

## Data Flow

### Synchronous Chat Request
```
Client → Backend → Key Selection → Provider API → Response → Client
                ↓
         Token Usage Recording (Redis)
```

### Async Agent Run
```
Client → Backend → Redis Queue → Worker → Provider API → Update Status
                ↓                                    ↓
         Return Job ID                        Token Usage Recording
```

### Dashboard Data
```
Frontend → Backend → Database (Provider Stats)
                  → Redis (Token Usage Timeseries)
                  → Prometheus (Metrics)
```

## Key Selection Algorithm

1. **Filter Active Keys**: Only keys with `status = 'active'`
2. **Check Rate Limits**: Exclude keys that have exceeded RPM limit
3. **Check Cooling Period**: Exclude keys in cooling period (after errors)
4. **Round-Robin Selection**: Select next key in rotation
5. **Error Handling**: On error, mark key as cooling and retry with next key

## Token Usage Tracking

### Storage
- **Backend**: Redis lists with JSON-encoded samples
- **Key Format**: `key_tokens:{key_id}`
- **Sample Format**: `{"timestamp": float, "tokens": int}`
- **Retention**: 24 hours (auto-eviction)

### Aggregation
- **Bucketing**: Time-based bucketing for efficient querying
- **Alignment**: Buckets aligned to current time for real-time accuracy
- **Time Windows**: Support for hour, day, week, month views

### Query Flow
```
Dashboard → Backend → Redis → Parse Samples → Bucket by Time → Return Timeseries
```

## Authentication Flow

1. **Login**: `POST /v1/auth/login` → Returns JWT token
2. **Protected Routes**: Include `Authorization: Bearer {token}` header
3. **Token Validation**: Backend validates JWT on each request
4. **Password Change**: `POST /v1/auth/change-password` (requires authentication)

## File Management

### Upload Flow
```
Client → POST /v1/files → Backend → Save to Disk → Store Metadata in DB → Return File ID
```

### Usage in LLM Requests
```
Client → POST /v1/llm/chat (with file_id) → Backend → Load File → Send to Provider
```

### Storage
- **Location**: `/app/storage` (configurable)
- **Database**: File metadata stored in `File` table
- **Access**: Files require authentication

## Provider Abstraction

All LLM providers implement a common interface:

```python
class BaseProvider:
    async def chat_completion(...) -> ChatResponse
    def get_usage_from_response(...) -> TokenUsage
```

### Supported Providers
- **OpenAI**: GPT-4, GPT-3.5, GPT-4o, GPT-4o-mini
- **Anthropic**: Claude 3.5 Sonnet, Claude 3.5 Haiku
- **DeepSeek**: DeepSeek Chat, DeepSeek Coder
- **Gemini**: Gemini Pro, Gemini Pro Vision

## Error Handling

### Key Errors
- **Rate Limit Exceeded**: Key marked as cooling for 60 seconds
- **API Error**: Key marked as cooling, retry with next key
- **Invalid Key**: Key disabled, excluded from selection

### Request Errors
- **Provider Unavailable**: Try next available key
- **Network Error**: Retry with exponential backoff
- **Invalid Request**: Return error to client

## Monitoring & Metrics

### Prometheus Metrics
- Request counts per provider
- Error rates per provider
- Key status counts
- Response times

### Dashboard Metrics
- Real-time provider health
- Token usage per provider (time-filtered)
- Key statistics
- Error rates

## Security

### Authentication
- JWT tokens with expiration
- Password hashing (bcrypt)
- Protected API endpoints

### File Security
- Files stored on disk (not in database)
- Access controlled via authentication
- File IDs are UUIDs (not guessable)

### API Security
- CORS configuration
- Input validation
- SQL injection prevention (SQLAlchemy ORM)
- Rate limiting per key

## Scalability Considerations

### Horizontal Scaling
- **Backend**: Stateless, can run multiple instances
- **Worker**: Can run multiple workers for parallel job processing
- **Database**: PostgreSQL with connection pooling
- **Redis**: Can be clustered for high availability

### Performance Optimizations
- **Token Timeseries**: Redis for fast reads/writes
- **Key Selection**: In-memory caching of key status
- **Database Queries**: Optimized with indexes
- **Frontend**: React Query for efficient data fetching

## Future Enhancements

- Advanced caching layer
- Multi-tenant support
- Webhook notifications
- Cost tracking and analytics
- Advanced rate limiting strategies
- Request/response caching
