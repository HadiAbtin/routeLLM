from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from uuid import UUID
import logging
from datetime import datetime, timezone

from app.db import get_db
from app.models import Run, User
from app.schemas import AgentRunCreate, AgentRunResponse, AgentRunRead
from app.queue import get_default_queue
from app.worker import process_run_job
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agent/runs", tags=["agent-runs"])


@router.post("", response_model=AgentRunResponse, status_code=201)
def create_run(
    run_data: AgentRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AgentRunResponse:
    """
    Create a new async agent run.
    
    If idempotency_key is provided and a run with that key exists,
    returns the existing run without creating a new one.
    """
    import sys
    print(">>> ENDPOINT CALLED <<<", file=sys.stderr, flush=True)
    
    # 🔍 DEBUG 1: Raw run_data from FastAPI
    import json as json_lib
    import sys
    
    # Force output to stderr (Docker captures this)
    print("=" * 60, file=sys.stderr, flush=True)
    print("🔍 DEBUG 1: RAW run_data.model_dump():", file=sys.stderr, flush=True)
    print(json_lib.dumps(run_data.model_dump(), indent=2, ensure_ascii=False), file=sys.stderr, flush=True)
    print("=" * 60, file=sys.stderr, flush=True)
    
    # Also check each message
    for i, m in enumerate(run_data.messages):
        print(f"DEBUG message[{i}] attachments: {m.attachments}", file=sys.stderr, flush=True)
        print(f"DEBUG message[{i}] attachments type: {type(m.attachments)}", file=sys.stderr, flush=True)
        print(f"DEBUG message[{i}] attachments is not None: {m.attachments is not None}", file=sys.stderr, flush=True)
    
    # Check for existing run with idempotency_key
    if run_data.idempotency_key:
        existing_run = db.query(Run).filter(
            Run.idempotency_key == run_data.idempotency_key
        ).first()
        
        if existing_run:
            logger.info(f"Found existing run with idempotency_key: {run_data.idempotency_key}")
            return AgentRunResponse(
                run_id=existing_run.id,
                status=existing_run.status
            )
    
    # Create new run
    provider = run_data.provider or "openai"
    
    # Convert messages to JSON-serializable format (including attachments)
    messages_json = []
    for idx, msg in enumerate(run_data.messages):
        # 🔍 DEBUG 2: Pydantic message object
        logger.error(f"\n🔍 DEBUG 2: MESSAGE #{idx} Pydantic object:")
        logger.error(f"  - msg.attachments: {msg.attachments}")
        logger.error(f"  - type(msg.attachments): {type(msg.attachments)}")
        logger.error(f"  - msg.attachments is not None: {msg.attachments is not None}")
        if msg.attachments:
            logger.error(f"  - len(msg.attachments): {len(msg.attachments)}")
        
        msg_dict = {
            "role": msg.role,
            "content": msg.content
        }
        
        # Include attachments if present
        if msg.attachments is not None and len(msg.attachments) > 0:
            msg_dict["attachments"] = [
                {"file_id": att.file_id, "type": att.type}
                for att in msg.attachments
            ]
        
        # 🔍 DEBUG 3: Final dict going to DB
        logger.error(f"\n🔍 DEBUG 3: MESSAGE #{idx} dict going to DB:")
        logger.error(json_lib.dumps(msg_dict, indent=2, ensure_ascii=False))
        logger.error("-" * 60)
        
        messages_json.append(msg_dict)
    
    # 🔍 DEBUG 4: Final messages_json before Run creation
    logger.error(f"\n🔍 DEBUG 4: Final messages_json (before Run creation):")
    logger.error(json_lib.dumps(messages_json, indent=2, ensure_ascii=False))
    logger.error("=" * 60)
    
    db_run = Run(
        status="pending",
        provider=provider,
        model=run_data.model,
        max_tokens=run_data.max_tokens,
        input_messages=messages_json,
        idempotency_key=run_data.idempotency_key
    )
    
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    
    # 🔍 DEBUG 5: What was actually stored in DB
    logger.error(f"\n🔍 DEBUG 5: What was stored in DB (after refresh):")
    logger.error(json_lib.dumps(db_run.input_messages, indent=2, ensure_ascii=False))
    logger.error("=" * 60)
    
    # Enqueue job with extended timeout (30 minutes for long-running requests)
    try:
        from app.config import get_settings
        settings = get_settings()
        queue = get_default_queue()
        # Set job_timeout to 30 minutes (1800 seconds) to allow long-running agent runs
        queue.enqueue(process_run_job, str(db_run.id), job_timeout=settings.provider_timeout_seconds)
        
        # Update status to queued
        db_run.status = "queued"
        db.commit()
        db.refresh(db_run)
        
        logger.info(f"Enqueued run {db_run.id} for processing")
        
    except Exception as e:
        logger.error(f"Failed to enqueue run {db_run.id}: {str(e)}")
        # Mark as failed if enqueue fails
        db_run.status = "failed"
        db_run.error = f"Failed to enqueue job: {str(e)}"
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enqueue run: {str(e)}"
        )
    
    return AgentRunResponse(
        run_id=db_run.id,
        status=db_run.status
    )


@router.get("/{run_id}", response_model=AgentRunRead)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AgentRunRead:
    """
    Get a specific agent run by ID.
    """
    db_run = db.query(Run).filter(Run.id == run_id).first()
    
    if not db_run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return db_run


@router.post("/{run_id}/cancel", response_model=AgentRunRead)
def cancel_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AgentRunRead:
    """
    Cancel an agent run.
    
    Only works if run is still pending, queued, or running.
    """
    db_run = db.query(Run).filter(Run.id == run_id).first()
    
    if not db_run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if db_run.status in ["succeeded", "failed", "canceled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status: {db_run.status}"
        )
    
    db_run.status = "canceled"
    db_run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_run)
    
    logger.info(f"Canceled run {run_id}")
    
    return db_run

