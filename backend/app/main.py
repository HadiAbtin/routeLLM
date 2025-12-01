from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict
import os
from pathlib import Path
from app.config import get_settings
from app.api.v1_llm import router as llm_router
from app.api.admin_keys import router as admin_keys_router
from app.api.stats import stats_router
from app.api.agent_runs import router as agent_runs_router
from app.api.files import router as files_router
from app.api.auth import router as auth_router
from app.metrics_endpoint import metrics_router
from app.db import init_db, SessionLocal
from app.models import User
from app.api.auth import get_password_hash

# Load settings on startup
settings = get_settings()

app = FastAPI(
    title="Route LLM Gateway API",
    version="0.0.1",
    description="A high-performance gateway for routing and managing LLM requests"
)

# Log settings on startup (optional, for debugging)
print(f"Environment: {settings.env}")
print(f"OpenAI Default Model: {settings.openai_default_model}")
print(f"OpenAI API Key configured: {'Yes' if settings.openai_api_key else 'No'}")
print(f"Database URL: {settings.database_url}")

# Include routers
app.include_router(auth_router)  # Auth routes (no protection needed)
app.include_router(llm_router)
app.include_router(admin_keys_router)
app.include_router(stats_router)
app.include_router(agent_runs_router)
app.include_router(files_router)
app.include_router(metrics_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and storage directory on application startup."""
    init_db()
    
    # Create storage directory if it doesn't exist
    storage_dir = Path(settings.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    print(f"Storage directory: {storage_dir.absolute()}")
    
    # Create default admin user if none exists
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == settings.default_admin_email).first()
        if not admin_user:
            # Password is already short enough (Admin123! is only 10 chars)
            password_hash = get_password_hash(settings.default_admin_password)
            admin_user = User(
                email=settings.default_admin_email,
                password_hash=password_hash,
                is_admin="true",
                must_change_password="true"
            )
            db.add(admin_user)
            db.commit()
            print(f"✅ Created default admin user: {settings.default_admin_email}")
        else:
            print(f"ℹ️  Admin user already exists: {settings.default_admin_email}")
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

# Enable CORS for localhost and Docker
# Note: Frontend runs in browser (not in container), so it uses localhost
# But we also allow requests from frontend container name for internal health checks
# In production, you should set CORS_ORIGINS environment variable
import os

# Get allowed origins from environment or use defaults
cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins_env:
    # Split by comma and strip whitespace
    allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    # Default origins for development
    allowed_origins = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",   # Alternative dev port
        "http://127.0.0.1:5173",
        "http://localhost:80",     # Docker frontend port mapping
        "http://localhost",       # Default localhost (no port)
        "http://127.0.0.1:80",
        "http://127.0.0.1",       # Default 127.0.0.1 (no port)
        # Docker internal network (for health checks, not for browser)
        "http://frontend:80",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    
    Returns a JSON object with the service status, name, and current timestamp.
    This endpoint can be used to verify that the API is running and responsive.
    
    Returns:
        Dict containing:
        - status: "ok" if service is healthy
        - service: Service name identifier
        - time: ISO 8601 formatted UTC timestamp
    """
    return {
        "status": "ok",
        "service": "route-llm-gateway",
        "time": datetime.utcnow().isoformat() + "Z"
    }

