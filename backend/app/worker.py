"""
Worker module for processing async agent runs.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Run, StoredFile
from app.schemas import ChatRequest, ChatMessage, ChatAttachment
from app.key_pool import (
    choose_best_key,
    register_key_usage,
    update_key_usage,
    mark_key_error,
    decay_key_errors,
)
from app.providers.registry import get_provider
from app.providers.errors import (
    ProviderRateLimitError,
    ProviderTransientError,
    ProviderClientError
)
from app.config import get_settings
from app.queue import get_default_queue
from app.key_usage_timeseries import record_key_tokens
from typing import Set, Optional
from uuid import UUID as UUIDType
import time

logger = logging.getLogger(__name__)


def process_run_job(run_id: str, attempt: int = 1) -> None:
    """
    Process a single agent run job with retry support.
    
    This function is called by RQ worker when a job is dequeued.
    
    Args:
        run_id: UUID string of the run to process
        attempt: Current attempt number (starts at 1)
    """
    db: Session = SessionLocal()
    
    try:
        # Load run from database
        run_uuid = UUID(run_id)
        db_run = db.query(Run).filter(Run.id == run_uuid).first()
        
        if not db_run:
            logger.error(f"Run {run_id} not found in database")
            return
        
        # Check if run was canceled
        if db_run.status == "canceled":
            logger.info(f"Run {run_id} was canceled, skipping")
            return
        
        # Update status to running
        db_run.status = "running"
        db_run.started_at = datetime.utcnow()
        db.commit()
        db.refresh(db_run)
        
        logger.info(f"Run {run_id} started processing")
        
        # Prepare ChatRequest from run data (with attachments support)
        messages = []
        file_ids = set()
        
        for msg_data in db_run.input_messages:
            # Extract attachments if present
            attachments = None
            if "attachments" in msg_data:
                attachments = [
                    ChatAttachment(file_id=att["file_id"], type=att["type"])
                    for att in msg_data["attachments"]
                ]
                # Collect file IDs
                for att in attachments:
                    file_ids.add(att.file_id)
            
            messages.append(ChatMessage(
                role=msg_data["role"],
                content=msg_data.get("content", ""),
                attachments=attachments
            ))
        
        # Resolve stored files if attachments are present
        stored_files = {}
        if file_ids:
            settings = get_settings()
            # Convert string IDs to UUIDs and query
            file_uuids = []
            id_mapping = {}
            for file_id_str in file_ids:
                try:
                    file_uuid = UUIDType(file_id_str)
                    file_uuids.append(file_uuid)
                    id_mapping[file_uuid] = file_id_str
                except ValueError:
                    logger.warning(f"Invalid file_id format: {file_id_str}")
                    continue
            
            # Query database
            stored_file_objs = db.query(StoredFile).filter(StoredFile.id.in_(file_uuids)).all()
            
            # Build mapping with public URLs
            for stored_file in stored_file_objs:
                file_id_str = id_mapping[stored_file.id]
                public_url = f"{settings.public_base_url}/v1/files/{stored_file.id}"
                stored_files[file_id_str] = {
                    "id": str(stored_file.id),
                    "filename": stored_file.filename,
                    "mime_type": stored_file.mime_type,
                    "size_bytes": stored_file.size_bytes,
                    "public_url": public_url,
                    "storage_path": stored_file.storage_path
                }
        
        chat_request = ChatRequest(
            messages=messages,
            model=db_run.model,
            provider=db_run.provider
        )
        
        settings = get_settings()
        max_attempts = settings.worker_max_attempts
        now = datetime.utcnow()
        now_ts = time.time()
        excluded: Set[str] = set()
        provider = get_provider(db_run.provider)
        
        # Retry loop with failover across keys
        while True:
            # Decay errors for all keys of this provider (opportunistic cleanup)
            # This is a simple approach - in production you might want a background task
            
            # Choose best available key
            selected_key = choose_best_key(
                db, db_run.provider, settings, now, excluded_key_ids=excluded
            )
            
            if not selected_key:
                # No usable keys - check if we should retry
                if attempt < max_attempts:
                    delay = min(
                        settings.worker_base_backoff_seconds * (2 ** (attempt - 1)),
                        settings.worker_max_backoff_seconds
                    )
                    logger.warning(
                        f"Run {run_id} attempt {attempt}: No available keys, "
                        f"requeuing with {delay}s delay"
                    )
                    queue = get_default_queue()
                    queue.enqueue_in(
                        timedelta(seconds=delay),
                        process_run_job,
                        run_id,
                        attempt + 1
                    )
                    db_run.status = "queued"
                    db_run.retry_count = attempt
                    db_run.last_error_reason = "No available keys"
                    db.commit()
                    return
                else:
                    # Max attempts reached
                    db_run.status = "failed"
                    db_run.error = "No available keys after all retries"
                    db_run.retry_count = attempt
                    db_run.finished_at = datetime.utcnow()
                    db.commit()
                    logger.error(f"Run {run_id} failed: No available keys after {max_attempts} attempts")
                    return
            
            excluded.add(str(selected_key.id))
            
            # Decay errors for this key if needed
            decay_key_errors(db, selected_key, settings, now)
            
            # Pre-check RPM and register usage
            register_key_usage(selected_key, settings, now_ts)
            selected_key.last_used_at = now
            db.add(selected_key)
            db.commit()
            
            # Call provider (async function needs to be run in event loop)
            try:
                # Run async provider.chat() in event loop with stored_files
                response = asyncio.run(provider.chat(
                    key=selected_key.api_key,
                    request=chat_request,
                    stored_files=stored_files if stored_files else None
                ))
                
                # Success: reset cooling if needed
                if selected_key.status == "cooling_down":
                    if not selected_key.cooling_until or selected_key.cooling_until <= now:
                        selected_key.status = "active"
                        selected_key.cooling_until = None
                        db.add(selected_key)
                        db.commit()
                
                # Update run with success
                db_run.status = "succeeded"
                db_run.output_message = {
                    "role": response.message.role,
                    "content": response.message.content
                }
                db_run.finished_at = datetime.utcnow()
                db_run.retry_count = attempt - 1  # Number of retries used
                
                # Update key usage
                update_key_usage(db, selected_key, now)

                # Record token usage per key if available
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

                    if total_tokens > 0:
                        logger.info(f"Recording {total_tokens} tokens for key {selected_key.id} (provider: {db_run.provider}, run: {run_id})")
                        record_key_tokens(str(selected_key.id), total_tokens)
                    else:
                        logger.warning(f"No tokens to record for key {selected_key.id} (run: {run_id}) - usage: {usage}")
                else:
                    logger.warning(f"No usage data in response for key {selected_key.id} (provider: {db_run.provider}, run: {run_id})")
                
                db.commit()
                
                logger.info(f"Run {run_id} completed successfully after {attempt} attempt(s)")
                return
                
            except ProviderRateLimitError as e:
                error_message = str(e)
                logger.warning(f"Run {run_id} attempt {attempt}: Rate limit error: {error_message}")
                mark_key_error(db, selected_key, settings, now, is_rate_limit=True)
                
                # Check if we should retry
                if attempt < max_attempts:
                    # Use retry_after from error if available, otherwise exponential backoff
                    retry_after = getattr(e, "retry_after", None)
                    if retry_after is None:
                        delay = min(
                            settings.worker_base_backoff_seconds * (2 ** (attempt - 1)),
                            settings.worker_max_backoff_seconds
                        )
                    else:
                        delay = min(retry_after, settings.worker_max_backoff_seconds)
                    
                    logger.info(f"Requeuing run {run_id} with {delay}s delay due to rate limit")
                    queue = get_default_queue()
                    queue.enqueue_in(
                        timedelta(seconds=delay),
                        process_run_job,
                        run_id,
                        attempt + 1
                    )
                    db_run.status = "queued"
                    db_run.retry_count = attempt
                    db_run.last_error_reason = f"Rate limit: {error_message}"
                    db.commit()
                    return
                else:
                    # Max attempts reached
                    db_run.status = "failed"
                    db_run.error = f"Rate limit error after {max_attempts} attempts: {error_message}"
                    db_run.retry_count = attempt
                    db_run.finished_at = datetime.utcnow()
                    db.commit()
                    logger.error(f"Run {run_id} failed after {max_attempts} attempts: {error_message}")
                    return
                    
            except ProviderTransientError as e:
                error_message = str(e)
                logger.warning(f"Run {run_id} attempt {attempt}: Transient error: {error_message}")
                mark_key_error(db, selected_key, settings, now, is_rate_limit=False)
                
                # Check if we should retry
                if attempt < max_attempts:
                    delay = min(
                        settings.worker_base_backoff_seconds * (2 ** (attempt - 1)),
                        settings.worker_max_backoff_seconds
                    )
                    logger.info(f"Requeuing run {run_id} with {delay}s delay due to transient error")
                    queue = get_default_queue()
                    queue.enqueue_in(
                        timedelta(seconds=delay),
                        process_run_job,
                        run_id,
                        attempt + 1
                    )
                    db_run.status = "queued"
                    db_run.retry_count = attempt
                    db_run.last_error_reason = f"Transient error: {error_message}"
                    db.commit()
                    return
                else:
                    # Max attempts reached
                    db_run.status = "failed"
                    db_run.error = f"Transient error after {max_attempts} attempts: {error_message}"
                    db_run.retry_count = attempt
                    db_run.finished_at = datetime.utcnow()
                    db.commit()
                    logger.error(f"Run {run_id} failed after {max_attempts} attempts: {error_message}")
                    return
                    
            except ProviderClientError as e:
                # Non-retriable: mark failed immediately
                error_message = str(e)
                logger.error(f"Run {run_id} attempt {attempt}: Client error (non-retriable): {error_message}")
                db_run.status = "failed"
                db_run.error = error_message
                db_run.retry_count = attempt
                db_run.last_error_reason = f"Client error: {error_message}"
                db_run.finished_at = datetime.utcnow()
                db.commit()
                return
            
    except Exception as e:
        logger.exception(f"Unexpected error processing run {run_id}: {str(e)}")
        # Try to mark run as failed
        try:
            db_run = db.query(Run).filter(Run.id == UUID(run_id)).first()
            if db_run:
                db_run.status = "failed"
                db_run.error = f"Worker error: {str(e)}"
                db_run.finished_at = datetime.utcnow()
                db.commit()
        except:
            pass
    finally:
        db.close()

