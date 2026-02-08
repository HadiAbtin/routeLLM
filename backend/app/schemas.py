from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID


class ChatAttachment(BaseModel):
    """Attachment reference for a chat message."""
    file_id: str = Field(..., description="ID of the uploaded file")
    type: Literal["image", "file", "document"] = Field(..., description="Type of attachment: 'image' for images, 'file' or 'document' for other files")


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""
    role: Literal["system", "user", "assistant"]
    content: str
    attachments: Optional[list[ChatAttachment]] = Field(None, description="Optional list of file attachments")


class ChatRequest(BaseModel):
    """Request model for chat completion."""
    messages: list[ChatMessage] = Field(..., min_length=1, description="List of chat messages")
    model: Optional[str] = Field(None, description="Model to use (overrides default)")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    provider: Optional[str] = Field("openai", description="Provider to use (e.g. 'openai', 'anthropic')")


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ChatResponseMessage(BaseModel):
    """Response message from the LLM."""
    role: str
    content: str


class ChatResponse(BaseModel):
    """Response model for chat completion."""
    model: str
    message: ChatResponseMessage
    usage: Optional[Usage] = None


# Provider Key Schemas
ProviderKeyStatus = Literal["active", "cooling_down", "disabled"]


class ProviderKeyBase(BaseModel):
    """Base schema for provider key."""
    provider: str
    display_name: str
    api_key: str
    environment: str = "prod"
    max_rpm: Optional[int] = None
    max_tpm: Optional[int] = None
    priority: int = 100
    status: ProviderKeyStatus = "active"


class ProviderKeyCreate(ProviderKeyBase):
    """Schema for creating a provider key."""
    pass


class ProviderKeyUpdate(BaseModel):
    """Schema for updating a provider key (all fields optional)."""
    provider: Optional[str] = None
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    environment: Optional[str] = None
    max_rpm: Optional[int] = None
    max_tpm: Optional[int] = None
    priority: Optional[int] = None
    status: Optional[ProviderKeyStatus] = None


class ProviderKeyRead(ProviderKeyBase):
    """Schema for reading a provider key."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    error_count_recent: int = 0

    class Config:
        from_attributes = True  # For SQLAlchemy ORM


# Agent Run Schemas
RunStatus = Literal["pending", "queued", "running", "succeeded", "failed", "canceled"]


class AgentRunCreate(BaseModel):
    """Schema for creating an agent run."""
    provider: Optional[str] = Field("openai", description="Provider to use")
    model: Optional[str] = Field(None, description="Model to use (optional)")
    messages: list[ChatMessage] = Field(..., min_length=1, description="LLM messages array")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate (uses default if not provided)")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for duplicate prevention")


class AgentRunResponse(BaseModel):
    """Schema for agent run response."""
    run_id: UUID
    status: RunStatus


class AgentRunRead(BaseModel):
    """Schema for reading an agent run."""
    id: UUID
    status: RunStatus
    provider: str
    model: Optional[str] = None
    input_messages: list[dict]  # JSON messages
    output_message: Optional[dict] = None  # JSON message or null
    error: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True



# Provider Schemas
class ProviderBase(BaseModel):
    """Base schema for provider."""
    name: str
    type: str  # "openai", "anthropic", "azure", "gemini", etc.
    base_url: Optional[str] = None
    description: Optional[str] = None


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""
    pass


class ProviderUpdate(BaseModel):
    """Schema for updating a provider (all fields optional)."""
    name: Optional[str] = None
    type: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None


class ProviderRead(ProviderBase):
    """Schema for reading a provider."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # For SQLAlchemy ORM
