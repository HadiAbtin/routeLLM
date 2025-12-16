from sqlalchemy import Column, String, Integer, DateTime, func, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional
import uuid

Base = declarative_base()


class ProviderKey(Base):
    """
    Model for storing provider API keys with metadata.
    
    TODO: Encrypt api_key field before storing (currently plain text).
    """
    __tablename__ = "provider_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    provider = Column(String(50), nullable=False, index=True)  # e.g. "openai", "anthropic"
    display_name = Column(String(255), nullable=False)
    api_key = Column(String(500), nullable=False)  # TODO: Encrypt this field
    environment = Column(String(50), default="prod")  # "dev", "staging", "prod"
    max_rpm = Column(Integer, nullable=True)  # Maximum requests per minute
    max_tpm = Column(Integer, nullable=True)  # Maximum tokens per minute
    priority = Column(Integer, default=100, nullable=False)  # Lower = more preferred
    status = Column(String(20), default="active", nullable=False)  # "active", "cooling_down", "disabled"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    error_count_recent = Column(Integer, default=0, nullable=False)
    cooling_until = Column(DateTime(timezone=True), nullable=True)  # When key can be used again after error


def is_key_effectively_active(key: ProviderKey, now: datetime) -> bool:
    """
    Check if a key is effectively active (status + cooling check).
    
    Args:
        key: ProviderKey instance
        now: Current datetime
        
    Returns:
        True if key can be used, False otherwise
    """
    if key.status == "disabled":
        return False
    
    if key.cooling_until:
        # Ensure both datetimes are timezone-aware for comparison
        from datetime import timezone
        
        if key.cooling_until.tzinfo is None:
            cooling_until_aware = key.cooling_until.replace(tzinfo=timezone.utc)
        else:
            cooling_until_aware = key.cooling_until
        
        if now.tzinfo is None:
            now_aware = now.replace(tzinfo=timezone.utc)
        else:
            now_aware = now
        
        if cooling_until_aware > now_aware:
            return False
    
    return True


class Run(Base):
    """
    Model for tracking asynchronous LLM agent runs.
    """
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, queued, running, succeeded, failed, canceled
    provider = Column(String(50), nullable=False, index=True)
    model = Column(String(100), nullable=True)
    max_tokens = Column(Integer, nullable=True)  # Maximum tokens for this run (uses default if None)
    input_messages = Column(JSONB, nullable=False)  # JSON array of messages
    output_message = Column(JSONB, nullable=True)  # JSON message or null
    error = Column(Text, nullable=True)  # Error message if failed
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)  # Unique key for idempotency
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Index for faster lookups
    __table_args__ = (
        Index('idx_runs_status_created', 'status', 'created_at'),
    )
    retry_count = Column(Integer, default=0, nullable=False)  # Number of retry attempts
    last_error_reason = Column(Text, nullable=True)  # Last error reason for debugging


class User(Base):
    """
    Model for admin users.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(String(10), default="true", nullable=False)  # Store as string for simplicity
    must_change_password = Column(String(10), default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StoredFile(Base):
    """
    Model for storing uploaded files and images.
    """
    __tablename__ = "stored_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    filename = Column(String(255), nullable=False)  # Original filename
    mime_type = Column(String(100), nullable=False)  # e.g. "image/png", "application/pdf"
    size_bytes = Column(Integer, nullable=False)  # File size in bytes
    storage_path = Column(String(500), nullable=False, unique=True)  # Path on disk
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

