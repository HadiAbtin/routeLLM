from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.db import get_db, SessionLocal
from app.models import ProviderKey, Run, User
from app.metrics import get_provider_request_counts, LLM_REQUESTS_TOTAL, LLM_REQUEST_LATENCY_SECONDS, LLM_TOKENS_TOTAL, KEY_ERRORS_TOTAL
from app.api.auth import get_current_user, decode_access_token
from app.key_usage_timeseries import get_key_tokens_timeseries, get_all_keys_with_data, get_key_sample_count
from uuid import UUID

logger = logging.getLogger(__name__)

stats_router = APIRouter(prefix="/v1/stats", tags=["stats"])


@stats_router.get("/providers")
def get_provider_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get provider-level statistics with extended metrics.
    
    Returns:
        JSON with provider stats including request counts, key statuses, and time-based metrics
    """
    # Get request counts from in-memory metrics
    request_counts = get_provider_request_counts()
    
    # Query provider keys grouped by provider and status
    keys_query = db.query(
        ProviderKey.provider,
        ProviderKey.status,
        func.count(ProviderKey.id).label("count")
    ).group_by(ProviderKey.provider, ProviderKey.status).all()
    
    # Organize keys by provider
    keys_by_provider: Dict[str, Dict[str, int]] = {}
    for provider, status, count in keys_query:
        if provider not in keys_by_provider:
            keys_by_provider[provider] = {
                "active_keys": 0,
                "disabled_keys": 0,
                "cooling_down_keys": 0
            }
        if status == "active":
            keys_by_provider[provider]["active_keys"] = count
        elif status == "disabled":
            keys_by_provider[provider]["disabled_keys"] = count
        elif status == "cooling_down":
            keys_by_provider[provider]["cooling_down_keys"] = count
    
    # Get time windows
    now = datetime.utcnow()
    window_15m = now - timedelta(minutes=15)
    window_1h = now - timedelta(hours=1)
    
    # Query runs for time-based stats
    runs_15m = db.query(
        Run.provider,
        Run.status,
        func.count(Run.id).label("count")
    ).filter(
        Run.created_at >= window_15m
    ).group_by(Run.provider, Run.status).all()
    
    runs_1h = db.query(
        Run.provider,
        Run.status,
        func.count(Run.id).label("count")
    ).filter(
        Run.created_at >= window_1h
    ).group_by(Run.provider, Run.status).all()
    
    # Organize runs by provider
    runs_by_provider_15m: Dict[str, Dict[str, int]] = {}
    runs_by_provider_1h: Dict[str, Dict[str, int]] = {}
    
    for provider, status, count in runs_15m:
        if provider not in runs_by_provider_15m:
            runs_by_provider_15m[provider] = {"success": 0, "error": 0, "total": 0}
        if status == "succeeded":
            runs_by_provider_15m[provider]["success"] = count
        elif status == "failed":
            runs_by_provider_15m[provider]["error"] = count
        runs_by_provider_15m[provider]["total"] += count
    
    for provider, status, count in runs_1h:
        if provider not in runs_by_provider_1h:
            runs_by_provider_1h[provider] = {"success": 0, "error": 0, "total": 0}
        if status == "succeeded":
            runs_by_provider_1h[provider]["success"] = count
        elif status == "failed":
            runs_by_provider_1h[provider]["error"] = count
        runs_by_provider_1h[provider]["total"] += count
    
    # Build response
    providers_list = []
    
    # Get all unique providers
    all_providers = set(keys_by_provider.keys()) | set(request_counts.keys()) | set(runs_by_provider_15m.keys()) | set(runs_by_provider_1h.keys())
    
    for provider in sorted(all_providers):
        provider_stats = {
            "provider": provider,
            "total_requests_last_15m": runs_by_provider_15m.get(provider, {}).get("total", 0),
            "total_requests_last_1h": runs_by_provider_1h.get(provider, {}).get("total", 0),
            "success_count_last_15m": runs_by_provider_15m.get(provider, {}).get("success", 0),
            "error_count_last_15m": runs_by_provider_15m.get(provider, {}).get("error", 0),
            "rate_limit_errors_last_15m": 0,  # TODO: Track from metrics
            "transient_errors_last_15m": 0,  # TODO: Track from metrics
            "client_errors_last_15m": 0,  # TODO: Track from metrics
            "avg_latency_ms_last_15m": 0,  # TODO: Calculate from metrics
            "p95_latency_ms_last_15m": 0,  # TODO: Calculate from metrics
            "active_keys": keys_by_provider.get(provider, {}).get("active_keys", 0),
            "cooling_keys": keys_by_provider.get(provider, {}).get("cooling_down_keys", 0),
            "disabled_keys": keys_by_provider.get(provider, {}).get("disabled_keys", 0),
            "total_tokens_last_1h": 0,  # TODO: Calculate from metrics
            "prompt_tokens_last_1h": 0,  # TODO: Calculate from metrics
            "completion_tokens_last_1h": 0,  # TODO: Calculate from metrics
        }
        
        # Add in-memory request counts (fallback)
        if provider in request_counts:
            provider_stats["success_count_last_15m"] = max(
                provider_stats["success_count_last_15m"],
                request_counts[provider].get("success", 0)
            )
            provider_stats["error_count_last_15m"] = max(
                provider_stats["error_count_last_15m"],
                request_counts[provider].get("error", 0)
            )
        
        providers_list.append(provider_stats)
    
    return {"providers": providers_list}


@stats_router.get("/providers/timeseries")
def get_provider_timeseries(
    authorization: Optional[str] = Header(None),
    window_minutes: int = Query(60, ge=1, le=1440),
    step_seconds: int = Query(60, ge=10, le=3600),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get time-series data for providers from Run table.
    
    Returns:
        JSON with time-series points for requests, errors, and success counts
    """
    import time
    
    now = datetime.utcnow()
    window_seconds = window_minutes * 60
    window_start = now - timedelta(seconds=window_seconds)
    
    # Query runs in the time window
    runs = db.query(Run).filter(
        Run.created_at >= window_start,
        Run.created_at <= now
    ).all()
    
    # Calculate bucket count and align to current time
    bucket_count = max(1, int(window_seconds // step_seconds))
    
    # Align buckets to current time (round up to next step boundary)
    now_ts = time.time()
    now_aligned_up = int((now_ts + step_seconds - 1) // step_seconds) * step_seconds
    end_time = now_aligned_up
    start_time = end_time - (bucket_count * step_seconds)
    
    # Initialize buckets for each provider
    provider_buckets: Dict[str, List[Dict[str, Any]]] = {}
    
    # Get all unique providers from runs
    providers = set(run.provider for run in runs)
    
    # Initialize buckets for each provider
    for provider in providers:
        provider_buckets[provider] = []
        for i in range(bucket_count):
            bucket_ts = start_time + i * step_seconds
            provider_buckets[provider].append({
                "timestamp": datetime.utcfromtimestamp(bucket_ts).isoformat() + "Z",
                            "provider": provider,
                            "requests": 0,
                            "success": 0,
                            "errors": 0,
            })
    
    # Assign runs to buckets
    for run in runs:
        provider = run.provider
        if provider not in provider_buckets:
            continue
        
        # Use created_at for bucketing
        run_ts = run.created_at.timestamp()
        
        # Calculate bucket index
        idx = int((run_ts - start_time) // step_seconds)
        if idx < 0:
            idx = 0
        if idx >= bucket_count:
            idx = bucket_count - 1
        
        # Update bucket
        bucket = provider_buckets[provider][idx]
        bucket["requests"] += 1
        if run.status == "succeeded":
            bucket["success"] += 1
        elif run.status == "failed":
            bucket["errors"] += 1
    
    # Flatten to list of points
    points = []
    for provider_buckets_list in provider_buckets.values():
        points.extend(provider_buckets_list)
    
    # Sort by timestamp
    points.sort(key=lambda p: p["timestamp"])
    
    logger.info(f"Returning {len(points)} timeseries points for {len(providers)} providers")
    
    return {"points": points}


@stats_router.get("/providers/tokens")
def get_provider_tokens(
    period: str = Query("hour", regex="^(hour|day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get total token usage per provider for different time periods.
    
    Args:
        period: Time period - "hour", "day", "week", or "month"
    
    Returns:
        JSON with token usage per provider for the specified period
    """
    from app.queue import get_redis_connection
    import json
    import time
    
    now = time.time()
    
    # Define time windows
    period_seconds = {
        "hour": 3600,
        "day": 86400,
        "week": 604800,
        "month": 2592000,  # 30 days
    }
    
    window_seconds = period_seconds.get(period, 3600)
    start_time = now - window_seconds
    
    # Get all keys from Redis
    redis_client = get_redis_connection()
    pattern = "key_tokens:*"
    redis_keys = redis_client.keys(pattern)
    
    # Aggregate tokens by provider
    provider_tokens: Dict[str, int] = {}
    
    for redis_key in redis_keys:
        # Extract key_id from Redis key
        key_id = redis_key.decode().replace("key_tokens:", "")
        
        # Get all samples for this key
        samples_json = redis_client.lrange(redis_key, 0, -1)
        
        # Parse and filter samples within window
        total_tokens = 0
        for sample_json_str in samples_json:
            try:
                sample_data = json.loads(sample_json_str)
                sample_ts = sample_data.get("timestamp", 0)
                if sample_ts >= start_time:
                    total_tokens += sample_data.get("tokens", 0)
            except (json.JSONDecodeError, KeyError):
                continue
        
        if total_tokens > 0:
            # Get provider for this key
            try:
                key_uuid = UUID(key_id)
                key = db.query(ProviderKey).filter(ProviderKey.id == key_uuid).first()
                if key:
                    provider = key.provider
                    provider_tokens[provider] = provider_tokens.get(provider, 0) + total_tokens
            except (ValueError, Exception):
                continue
    
    # Format response - ensure all values are proper types
    result = []
    for provider, tokens in sorted(provider_tokens.items()):
        # Ensure provider is a string and tokens is an integer
        provider_str = str(provider) if provider else "unknown"
        tokens_int = int(tokens) if tokens else 0
        result.append({
            "provider": provider_str,
            "total_tokens": tokens_int,
            "period": str(period)
        })
    
    logger.info(f"Returning token usage for {len(result)} providers for period: {period}")
    
    # Always return a dict with providers array, never return object directly
    return {"providers": result if isinstance(result, list) else []}


@stats_router.get("/keys")
def get_key_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get key-level health and usage statistics.
    """
    keys = db.query(ProviderKey).all()
    now = datetime.utcnow()
    window_1h = now - timedelta(hours=1)
    
    keys_list = []
    for key in keys:
        # Query runs for this key (approximate - we don't track which key was used)
        # For now, use provider-level stats
        runs_1h = db.query(Run).filter(
            Run.provider == key.provider,
            Run.created_at >= window_1h
        ).all()
        
        success_count = sum(1 for r in runs_1h if r.status == "succeeded")
        error_count = sum(1 for r in runs_1h if r.status == "failed")
        total_requests = len(runs_1h)
        
        keys_list.append({
            "id": str(key.id),
            "provider": key.provider,
            "display_name": key.display_name,
            "status": key.status,
            "environment": key.environment,
            "priority": key.priority,
            # Use ISO 8601 as returned by SQLAlchemy; don't append extra 'Z' to avoid invalid timestamps
            "cooling_until": key.cooling_until.isoformat() if key.cooling_until else None,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "last_error_at": key.last_error_at.isoformat() if key.last_error_at else None,
            "error_count_recent": key.error_count_recent,
            "success_count_last_1h": success_count,
            "error_count_last_1h": error_count,
            "avg_latency_ms_last_1h": 0,  # TODO: Calculate
            "requests_last_1h": total_requests,
            "max_rpm": key.max_rpm,
            "max_tpm": key.max_tpm,
            "created_at": key.created_at.isoformat() if key.created_at else None,
            "updated_at": key.updated_at.isoformat() if key.updated_at else None,
        })
    
    return {"keys": keys_list}


@stats_router.get("/keys/errors")
def get_key_errors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get per-key error statistics.
    """
    keys = db.query(ProviderKey).all()
    now = datetime.utcnow()
    window_1h = now - timedelta(hours=1)
    
    keys_list = []
    for key in keys:
        # Query failed runs for this provider (approximate)
        failed_runs = db.query(Run).filter(
            Run.provider == key.provider,
            Run.status == "failed",
            Run.created_at >= window_1h
        ).all()
        
        # Parse error types from error messages (simple heuristic)
        rate_limit_count = sum(1 for r in failed_runs if r.error and "429" in r.error)
        transient_count = sum(1 for r in failed_runs if r.error and ("timeout" in r.error.lower() or "network" in r.error.lower()))
        client_count = sum(1 for r in failed_runs if r.error and ("401" in r.error or "403" in r.error or "400" in r.error))
        
        keys_list.append({
            "id": str(key.id),
            "provider": key.provider,
            "display_name": key.display_name,
            "rate_limit_errors_last_1h": rate_limit_count,
            "transient_errors_last_1h": transient_count,
            "client_errors_last_1h": client_count,
        })
    
    return {"keys": keys_list}


@stats_router.get("/keys/{key_id}/timeseries")
def get_key_tokens_timeseries_endpoint(
    key_id: str,
    window_minutes: int = Query(60, ge=1, le=1440),
    step_seconds: int = Query(300, ge=10, le=3600),
    current_user: User = Depends(get_current_user),
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get per-key token usage timeseries.

    Returns list of points:
        { "points": [{ "ts": ISO8601, "tokens": int }, ...] }
    """
    logger.info(f"Fetching timeseries for key {key_id} (window: {window_minutes} min, step: {step_seconds} sec)")
    points = get_key_tokens_timeseries(key_id, window_minutes, step_seconds)
    logger.info(f"Returning {len(points)} points for key {key_id}")
    return {"points": points}


@stats_router.get("/runs")
def get_runs_stats(
    window_minutes: int = Query(60, ge=1, le=1440),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get async runs statistics.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)
    
    runs = db.query(Run).filter(Run.created_at >= window_start).all()
    
    by_status = {
        "pending": 0,
        "queued": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "canceled": 0,
    }
    
    retry_histogram: Dict[int, int] = {}
    
    for run in runs:
        by_status[run.status] = by_status.get(run.status, 0) + 1
        retry_count = run.retry_count or 0
        retry_histogram[retry_count] = retry_histogram.get(retry_count, 0) + 1
    
    retry_histogram_list = [
        {"retry_count": count, "runs": runs_count}
        for count, runs_count in sorted(retry_histogram.items())
    ]
    
    return {
        "window_minutes": window_minutes,
        "total_runs": len(runs),
        "by_status": by_status,
        "retry_histogram": retry_histogram_list,
    }


@stats_router.get("/errors/recent")
def get_recent_errors(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get recent errors from runs and key errors.
    """
    # Get recent failed runs
    failed_runs = db.query(Run).filter(
        Run.status == "failed"
    ).order_by(Run.created_at.desc()).limit(limit).all()
    
    errors = []
    for run in failed_runs:
        # Determine error kind from error message
        error_kind = "transient"
        if run.error:
            if "429" in run.error:
                error_kind = "rate_limit"
            elif "401" in run.error or "403" in run.error or "400" in run.error:
                error_kind = "client"
        
        # Get key info (approximate - use first active key for provider)
        key = db.query(ProviderKey).filter(
            ProviderKey.provider == run.provider,
            ProviderKey.status == "active"
        ).first()
        
        errors.append({
            "timestamp": run.created_at.isoformat() + "Z",
            "provider": run.provider,
            "key_id": str(key.id) if key else None,
            "key_display_name": key.display_name if key else None,
            "kind": error_kind,
            "message": run.error[:200] if run.error else "Unknown error",
            "run_id": str(run.id),
        })
    
    return {"errors": errors}


@stats_router.get("/debug/token-keys")
def get_debug_token_keys(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Debug endpoint: Get list of all keys that have token usage data in memory.
    """
    keys_with_data = get_all_keys_with_data()
    result = []
    for key_id in keys_with_data:
        sample_count = get_key_sample_count(key_id)
        result.append({
            "key_id": key_id,
            "sample_count": sample_count
        })
    
    return {
        "total_keys_with_data": len(keys_with_data),
        "keys": result
    }


@stats_router.get("/debug/key/{key_id}")
def get_debug_key_info(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Debug endpoint: Get detailed information about why a key is or isn't being selected.
    """
    from app.config import get_settings
    from app.key_pool import can_use_key_for_rpm, key_score
    from app.models import is_key_effectively_active
    from datetime import datetime
    import time
    
    try:
        key_uuid = UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key ID format")
    
    key = db.query(ProviderKey).filter(ProviderKey.id == key_uuid).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    settings = get_settings()
    now = datetime.utcnow()
    now_ts = time.time()
    
    # Check all conditions
    is_effectively_active = is_key_effectively_active(key, now)
    can_use_rpm = can_use_key_for_rpm(key, settings, now_ts)
    score = key_score(key)
    
    # Get RPM state
    from app.key_pool import _rpm_state
    rpm_state = _rpm_state.get(str(key.id))
    rpm_info = None
    if rpm_state:
        rpm_info = {
            "window_start": rpm_state.window_start,
            "rpm_count": rpm_state.rpm_count,
            "max_rpm": key.max_rpm,
            "window_seconds": settings.key_rpm_window_seconds,
            "time_until_reset": max(0, settings.key_rpm_window_seconds - (now_ts - rpm_state.window_start))
        }
    
    # Check if key would be selected
    from app.key_pool import choose_best_key, _round_robin_index
    all_keys = db.query(ProviderKey).filter(
        ProviderKey.provider == key.provider,
        ProviderKey.status != "disabled"
    ).all()
    
    available_keys = []
    for k in all_keys:
        if (is_key_effectively_active(k, now) and 
            can_use_key_for_rpm(k, settings, now_ts)):
            available_keys.append(k)
    
    available_keys.sort(key=key_score)
    key_position = None
    if key in available_keys:
        key_position = available_keys.index(key)
        round_robin_index = _round_robin_index.get(key.provider, 0)
        would_be_selected = (round_robin_index % len(available_keys)) == key_position
    else:
        would_be_selected = False
    
    return {
        "key_id": str(key.id),
        "display_name": key.display_name,
        "provider": key.provider,
        "status": key.status,
        "priority": key.priority,
        "error_count_recent": key.error_count_recent,
        "cooling_until": key.cooling_until.isoformat() if key.cooling_until else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "last_error_at": key.last_error_at.isoformat() if key.last_error_at else None,
        "max_rpm": key.max_rpm,
        "max_tpm": key.max_tpm,
        "is_effectively_active": is_effectively_active,
        "can_use_rpm": can_use_rpm,
        "score": score,
        "rpm_state": rpm_info,
        "available_keys_count": len(available_keys),
        "key_position_in_available": key_position,
        "would_be_selected": would_be_selected,
        "round_robin_index": _round_robin_index.get(key.provider, 0),
        "all_available_keys": [
            {
                "display_name": k.display_name,
                "key_id": str(k.id)[:8],
                "score": key_score(k),
                "error_count": k.error_count_recent,
                "priority": k.priority
            }
            for k in available_keys
        ]
    }


@stats_router.get("/debug/run/{run_id}")
def get_debug_run_info(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Debug endpoint: Get information about a run and which key was likely used.
    """
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    run = db.query(Run).filter(Run.id == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Find likely key used (based on provider and last_used_at around run time)
    likely_keys = []
    if run.finished_at:
        # Look for keys that were used around the time the run finished
        time_window_start = run.finished_at - timedelta(minutes=5)
        time_window_end = run.finished_at + timedelta(minutes=5)
        
        keys = db.query(ProviderKey).filter(
            ProviderKey.provider == run.provider,
            ProviderKey.last_used_at >= time_window_start,
            ProviderKey.last_used_at <= time_window_end
        ).all()
        
        for key in keys:
            sample_count = get_key_sample_count(str(key.id))
            likely_keys.append({
                "key_id": str(key.id),
                "display_name": key.display_name,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                "token_samples_in_memory": sample_count,
                "has_token_data": sample_count > 0
            })
    
    # Also check all keys for this provider that have token data
    all_provider_keys_with_data = []
    keys_with_data = get_all_keys_with_data()
    for key_id in keys_with_data:
        # Check if this key belongs to the same provider
        try:
            key_uuid = UUID(key_id)
            key = db.query(ProviderKey).filter(ProviderKey.id == key_uuid).first()
            if key and key.provider == run.provider:
                sample_count = get_key_sample_count(key_id)
                all_provider_keys_with_data.append({
                    "key_id": key_id,
                    "display_name": key.display_name,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "token_samples_in_memory": sample_count
                })
        except (ValueError, Exception):
            continue
    
    return {
        "run_id": str(run.id),
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "likely_keys_used": likely_keys,
        "all_provider_keys_with_token_data": all_provider_keys_with_data,
        "note": "Token data is stored in-memory and may be lost if backend restarts"
    }
