from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import time
from typing import Set, Optional
from uuid import UUID
from datetime import datetime

from app.schemas import ChatRequest, ChatResponse
from app.db import get_db
from app.models import StoredFile, User
from app.config import get_settings
from app.key_pool import (
    choose_best_key,
    register_key_usage,
    update_key_usage,
    mark_key_error,
    decay_key_errors
)
from app.providers.registry import get_provider
from app.providers.errors import (
    ProviderRateLimitError,
    ProviderTransientError,
    ProviderClientError
)
from app.config import get_settings
from app.metrics import (
    LLM_REQUESTS_TOTAL,
    LLM_REQUEST_LATENCY_SECONDS,
    LLM_TOKENS_TOTAL,
    KEY_ERRORS_TOTAL,
    update_provider_request_count,
)
from app.key_usage_timeseries import record_key_tokens
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/v1/llm", tags=["llm"])


def _collect_file_ids(request: ChatRequest) -> Set[str]:
    """Collect all unique file_ids from message attachments."""
    file_ids = set()
    for message in request.messages:
        if message.attachments:
            for att in message.attachments:
                file_ids.add(att.file_id)
    return file_ids


def _resolve_stored_files(db: Session, file_ids: Set[str]) -> dict:
    """
    Resolve file_ids to StoredFile records and build a mapping with public URLs.
    
    Returns:
        dict mapping file_id (str) -> dict with keys: id, filename, mime_type, size_bytes, public_url
    """
    if not file_ids:
        return {}
    
    # Convert string IDs to UUIDs
    file_uuids = []
    id_mapping = {}  # UUID -> original string ID
    for file_id_str in file_ids:
        try:
            file_uuid = UUID(file_id_str)
            file_uuids.append(file_uuid)
            id_mapping[file_uuid] = file_id_str
        except ValueError:
            logger.warning(f"Invalid file_id format: {file_id_str}")
            continue
    
    # Query database
    stored_files = db.query(StoredFile).filter(StoredFile.id.in_(file_uuids)).all()
    
    # Build mapping with public URLs
    result = {}
    for stored_file in stored_files:
        file_id_str = id_mapping[stored_file.id]
        public_url = f"{settings.public_base_url}/v1/files/{stored_file.id}"
        result[file_id_str] = {
            "id": str(stored_file.id),
            "filename": stored_file.filename,
            "mime_type": stored_file.mime_type,
            "size_bytes": stored_file.size_bytes,
            "public_url": public_url
        }
    
    # Check for missing files
    found_ids = {id_mapping[sf.id] for sf in stored_files}
    missing_ids = file_ids - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown attachment file_id(s): {', '.join(missing_ids)}"
        )
    
    return result


@router.post("/chat", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Chat completion endpoint.
    
    Sends a chat request to the configured LLM provider using a key from the key pool.
    
    Args:
        request: ChatRequest containing messages, optional provider, and parameters
        db: Database session
        
    Returns:
        ChatResponse with model, message, and usage information
        
    Raises:
        HTTPException: If provider returns an error, no keys available, or other issues
    """
    # Determine provider (default to "openai")
    provider_name = request.provider or "openai"
    
    # Collect file IDs from attachments
    file_ids = _collect_file_ids(request)
    
    # Resolve stored files if attachments are present
    stored_files = {}
    if file_ids:
        stored_files = _resolve_stored_files(db, file_ids)
        
        # Check if provider supports attachments
        provider = get_provider(provider_name)
        if not provider.supports_attachments:
            raise HTTPException(
                status_code=400,
                detail=f"Attachments are not supported for provider '{provider_name}' yet."
            )
    
    # Start timing for latency metric
    start_time = time.perf_counter()
    
    try:
        settings = get_settings()
        now = datetime.utcnow()
        excluded: Set[str] = set()
        attempts = 0
        max_attempts = settings.sync_llm_max_retries + 1  # first try + retries
        last_exception: Optional[Exception] = None
        
        # Get provider instance (if not already retrieved above)
        if not file_ids:
            provider = get_provider(provider_name)
        
        # Retry loop with failover across keys
        while attempts < max_attempts:
            attempts += 1
            now = datetime.utcnow()
            now_ts = time.time()
            
            # Choose best available key (excluding previously tried ones)
            selected_key = choose_best_key(
                db, provider_name, settings, now, excluded_key_ids=excluded
            )
            
            if selected_key:
                logger.info(f"Attempt {attempts}/{max_attempts} with key {selected_key.id} ({selected_key.display_name}) for provider {provider_name}")
            
            if not selected_key:
                # No usable keys at all
                break
            
            excluded.add(str(selected_key.id))
            
            # Decay errors for this key if needed
            decay_key_errors(db, selected_key, settings, now)
            
            # Pre-check RPM and register usage
            register_key_usage(selected_key, settings, now_ts)
            selected_key.last_used_at = now
            db.add(selected_key)
            db.commit()
            
            try:
                # Call provider with selected key and stored files
                response = await provider.chat(
                    key=selected_key.api_key,
                    request=request,
                    stored_files=stored_files if stored_files else None
                )
                
                # Success: reset cooling if needed
                if selected_key.status == "cooling_down":
                    if not selected_key.cooling_until or selected_key.cooling_until <= now:
                        selected_key.status = "active"
                        selected_key.cooling_until = None
                        db.add(selected_key)
                        db.commit()
                
                # Calculate duration
                duration = time.perf_counter() - start_time
                
                # Record metrics for successful request
                LLM_REQUEST_LATENCY_SECONDS.labels(provider=provider_name).observe(duration)
                LLM_REQUESTS_TOTAL.labels(provider=provider_name, status="success").inc()
                update_provider_request_count(provider_name, "success")
                
                # Record token usage if available
                if response.usage:
                    usage = response.usage
                    total_tokens = 0
                    
                    # Prefer total_tokens if available, otherwise calculate from prompt + completion
                    if usage.total_tokens is not None:
                        total_tokens = usage.total_tokens
                    else:
                        if usage.prompt_tokens is not None:
                            total_tokens += usage.prompt_tokens
                        if usage.completion_tokens is not None:
                            total_tokens += usage.completion_tokens
                    
                    # Update Prometheus metrics
                    if usage.prompt_tokens is not None:
                        LLM_TOKENS_TOTAL.labels(provider=provider_name, type="prompt").inc(
                            usage.prompt_tokens
                        )
                    if usage.completion_tokens is not None:
                        LLM_TOKENS_TOTAL.labels(
                            provider=provider_name, type="completion"
                        ).inc(usage.completion_tokens)
                    if usage.total_tokens is not None:
                        LLM_TOKENS_TOTAL.labels(provider=provider_name, type="total").inc(
                            usage.total_tokens
                        )
                    elif total_tokens > 0:
                        # If total_tokens wasn't provided but we calculated it, still record it
                        LLM_TOKENS_TOTAL.labels(provider=provider_name, type="total").inc(total_tokens)

                    # Record per-key token timeseries (in-memory)
                    if total_tokens > 0:
                        logger.info(f"Recording {total_tokens} tokens for key {selected_key.id} (provider: {provider_name})")
                        record_key_tokens(str(selected_key.id), total_tokens)
                    else:
                        logger.warning(f"No tokens to record for key {selected_key.id} - usage: {usage}")
                else:
                    logger.warning(f"No usage data in response for key {selected_key.id} (provider: {provider_name})")
                
                # Update last_used_at
                update_key_usage(db, selected_key, now)
                
                return response
                
            except ProviderRateLimitError as e:
                last_exception = e
                mark_key_error(db, selected_key, settings, now, is_rate_limit=True)
                # Continue to try next key (no sleep in sync endpoint)
                continue
                
            except ProviderTransientError as e:
                last_exception = e
                mark_key_error(db, selected_key, settings, now, is_rate_limit=False)
                # Continue to try next key
                continue
                
            except ProviderClientError as e:
                # Non-retriable: bubble up immediately
                # Record metric for client error
                KEY_ERRORS_TOTAL.labels(
                    provider=provider_name,
                    key_id=str(selected_key.id),
                    kind="client"
                ).inc()
                duration = time.perf_counter() - start_time
                LLM_REQUEST_LATENCY_SECONDS.labels(provider=provider_name).observe(duration)
                LLM_REQUESTS_TOTAL.labels(provider=provider_name, status="error").inc()
                update_provider_request_count(provider_name, "error")
                raise HTTPException(status_code=400, detail=str(e))
        
        # All attempts exhausted or no keys available
        duration = time.perf_counter() - start_time
        LLM_REQUEST_LATENCY_SECONDS.labels(provider=provider_name).observe(duration)
        LLM_REQUESTS_TOTAL.labels(provider=provider_name, status="error").inc()
        update_provider_request_count(provider_name, "error")
        
        # Return appropriate error
        if isinstance(last_exception, ProviderRateLimitError):
            retry_after = getattr(last_exception, "retry_after", None) or settings.sync_llm_max_retry_wait_seconds
            headers = {"Retry-After": str(int(retry_after))}
            raise HTTPException(
                status_code=429,
                detail="All keys are rate-limited, please retry later.",
                headers=headers
            )
        elif last_exception is not None:
            raise HTTPException(
                status_code=503,
                detail="LLM request failed after retries."
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"No available keys for provider '{provider_name}'."
            )
    except HTTPException:
        # Re-raise HTTPExceptions (from key pool, provider, etc.)
        raise
    except ValueError as e:
        # Provider not found
        logger.error(f"Provider error: {str(e)}")
        duration = time.perf_counter() - start_time
        LLM_REQUEST_LATENCY_SECONDS.labels(provider=provider_name).observe(duration)
        LLM_REQUESTS_TOTAL.labels(provider=provider_name, status="error").inc()
        update_provider_request_count(provider_name, "error")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        # Catch unexpected exceptions
        logger.exception("Unexpected error in chat completion")
        duration = time.perf_counter() - start_time
        LLM_REQUEST_LATENCY_SECONDS.labels(provider=provider_name).observe(duration)
        LLM_REQUESTS_TOTAL.labels(provider=provider_name, status="error").inc()
        update_provider_request_count(provider_name, "error")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
