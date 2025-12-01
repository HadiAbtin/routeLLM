import time
from collections import defaultdict
from typing import Optional, Tuple, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.models import ProviderKey, is_key_effectively_active
from app.config import AppSettings
from app.metrics import KEY_ERRORS_TOTAL


@dataclass
class KeyUsageState:
    """In-memory state for tracking key usage."""
    window_start: float
    rpm_count: int


# In-memory RPM state: key_id -> KeyUsageState
_rpm_state: dict[str, KeyUsageState] = {}

# Simple round-robin index per provider
# Stored in Redis to persist across restarts
_round_robin_index: dict[str, int] = defaultdict(int)


def can_use_key_for_rpm(key: ProviderKey, settings: AppSettings, now_ts: float) -> bool:
    """
    Check if a key can be used based on its RPM limit.
    
    Args:
        key: ProviderKey instance
        settings: AppSettings instance
        now_ts: Current timestamp (time.time())
        
    Returns:
        True if key can be used, False otherwise
    """
    # If no RPM limit, always allow
    if key.max_rpm is None:
        return True
    
    key_id_str = str(key.id)
    
    # Get or initialize state for this key
    if key_id_str not in _rpm_state:
        _rpm_state[key_id_str] = KeyUsageState(window_start=now_ts, rpm_count=0)
        return True
    
    state = _rpm_state[key_id_str]
    window_seconds = settings.key_rpm_window_seconds
    
    # If window expired, reset
    if now_ts - state.window_start >= window_seconds:
        state.window_start = now_ts
        state.rpm_count = 0
        return True
    
    # Check if under limit
    return state.rpm_count < key.max_rpm


def register_key_usage(key: ProviderKey, settings: AppSettings, now_ts: float) -> None:
    """
    Register that a key was used (increment RPM counter).
    
    Args:
        key: ProviderKey instance
        settings: AppSettings instance
        now_ts: Current timestamp (time.time())
    """
    key_id_str = str(key.id)
    window_seconds = settings.key_rpm_window_seconds
    
    # Get or initialize state
    if key_id_str not in _rpm_state:
        _rpm_state[key_id_str] = KeyUsageState(window_start=now_ts, rpm_count=1)
    else:
        state = _rpm_state[key_id_str]
        
        # Reset if window expired
        if now_ts - state.window_start >= window_seconds:
            state.window_start = now_ts
            state.rpm_count = 1
        else:
            state.rpm_count += 1


def key_score(key: ProviderKey) -> tuple:
    """
    Compute a score for key selection (lower is better).
    
    Args:
        key: ProviderKey instance
        
    Returns:
        Tuple of (error_score, priority_score, created_score)
    """
    error_score = key.error_count_recent or 0
    priority_score = key.priority or 100
    created_score = int(key.created_at.timestamp())
    return (error_score, priority_score, created_score)


def choose_best_key(
    db: Session,
    provider: str,
    settings: AppSettings,
    now: datetime,
    excluded_key_ids: Optional[Set[str]] = None,
) -> Optional[ProviderKey]:
    """
    Choose the best available key for the given provider.
    
    Uses health-aware selection with error tracking and round-robin.
    
    Args:
        db: Database session
        provider: Provider name (e.g. "openai")
        settings: AppSettings instance
        now: Current datetime
        excluded_key_ids: Set of key IDs to exclude (already tried in this request)
        
    Returns:
        ProviderKey instance or None if no usable keys
    """
    if excluded_key_ids is None:
        excluded_key_ids = set()
    
    # Query for non-disabled keys for this provider
    keys = db.query(ProviderKey).filter(
        ProviderKey.provider == provider,
        ProviderKey.status != "disabled"
    ).all()
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Decay errors for all keys before selection (opportunistic cleanup)
    # This ensures cooling periods are properly expired before checking availability
    for key in keys:
        decay_key_errors(db, key, settings, now)
    
    logger.info(f"Choosing best key for provider '{provider}'. Found {len(keys)} keys (excluding disabled):")
    for key in keys:
        logger.info(f"  - {key.display_name} ({str(key.id)[:8]}...): status={key.status}, error_count={key.error_count_recent}, priority={key.priority}, cooling_until={key.cooling_until}")
    
    if not keys:
        logger.warning(f"No keys found for provider '{provider}'")
        return None
    
    # Filter by effective active status and cooling
    available_keys = []
    now_ts = time.time()
    
    for key in keys:
        key_id_str = str(key.id)
        
        # Skip excluded keys
        if key_id_str in excluded_key_ids:
            logger.info(f"Key {key.display_name} ({key_id_str}) excluded (already tried)")
            continue
        
        # Check effective active status
        if not is_key_effectively_active(key, now):
            reason = "disabled" if key.status == "disabled" else f"cooling until {key.cooling_until}" if key.cooling_until else "unknown"
            logger.info(f"Key {key.display_name} ({key_id_str}) not effectively active: {reason}")
            continue
        
        # Check RPM limit
        if not can_use_key_for_rpm(key, settings, now_ts):
            rpm_state = _rpm_state.get(key_id_str)
            rpm_info = f"RPM: {rpm_state.rpm_count}/{key.max_rpm}" if rpm_state and key.max_rpm else "RPM limit check failed"
            logger.info(f"Key {key.display_name} ({key_id_str}) cannot be used: {rpm_info}")
            continue
        
        available_keys.append(key)
        logger.info(f"Key {key.display_name} ({key_id_str}) is available (error_count={key.error_count_recent}, priority={key.priority})")
    
    if not available_keys:
        return None
    
    # Sort by score (error_count, priority, created_at)
    available_keys.sort(key=key_score)
    
    # Log all available keys with their scores
    if available_keys:
        logger.info(f"Available keys for {provider} (sorted by score):")
        for idx, key in enumerate(available_keys):
            score = key_score(key)
            logger.info(f"  [{idx}] {key.display_name} ({str(key.id)[:8]}...): score={score}, error_count={key.error_count_recent}, priority={key.priority}")
    
    # Apply round-robin on top
    # Use Redis to persist round-robin index across restarts
    from app.queue import get_redis_connection
    redis_client = get_redis_connection()
    redis_key = f"round_robin_index:{provider}"
    
    try:
        # Get current index from Redis, default to 0
        current_index_str = redis_client.get(redis_key)
        if current_index_str:
            current_index = int(current_index_str.decode())
        else:
            current_index = 0
    except (ValueError, AttributeError):
        current_index = 0
    
    # Select key using round-robin
    index = current_index % len(available_keys)
    selected_key = available_keys[index]
    
    # Increment and store in Redis
    next_index = current_index + 1
    try:
        redis_client.set(redis_key, str(next_index))
    except Exception as e:
        logger.warning(f"Failed to update round-robin index in Redis: {e}")
        # Fallback to in-memory
        _round_robin_index[provider] = next_index
    
    logger.info(f"Selected key for {provider}: {selected_key.display_name} ({str(selected_key.id)[:8]}...) [round-robin index: {index}, next: {next_index}]")
    
    return selected_key


def mark_key_error(
    db: Session,
    key: ProviderKey,
    settings: AppSettings,
    now: datetime,
    is_rate_limit: bool,
    is_authentication_error: bool = False,
) -> None:
    """
    Mark a key as having an error.
    
    Args:
        db: Database session
        key: ProviderKey instance
        settings: AppSettings instance
        now: Current datetime
        is_rate_limit: Whether error was a rate limit (429)
        is_authentication_error: Whether error was an authentication error (401/invalid key)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    key.error_count_recent = (key.error_count_recent or 0) + 1
    key.last_error_at = now
    
    if is_authentication_error:
        # Authentication errors: disable the key permanently (admin must re-enable)
        key.status = "disabled"
        key.cooling_until = None
        logger.warning(f"Key {key.display_name} ({str(key.id)[:8]}...) disabled due to authentication error")
    elif is_rate_limit:
        # Rate limit errors: set cooling period
        cooldown_seconds = settings.key_cooldown_seconds_on_429
        key.cooling_until = now + timedelta(seconds=cooldown_seconds)
        key.status = "cooling_down"
        logger.info(f"Key {key.display_name} ({str(key.id)[:8]}...) cooling down for {cooldown_seconds}s due to rate limit")
    else:
        # Other transient errors: set cooling period
        cooldown_seconds = settings.key_cooldown_seconds_on_network_error
        key.cooling_until = now + timedelta(seconds=cooldown_seconds)
        key.status = "cooling_down"
        logger.info(f"Key {key.display_name} ({str(key.id)[:8]}...) cooling down for {cooldown_seconds}s due to transient error")
    
    # Record metric
    error_kind = "rate_limit" if is_rate_limit else ("authentication" if is_authentication_error else "transient")
    KEY_ERRORS_TOTAL.labels(
        provider=key.provider,
        key_id=str(key.id),
        kind=error_kind
    ).inc()
    
    db.add(key)
    db.commit()


def decay_key_errors(db: Session, key: ProviderKey, settings: AppSettings, now: datetime) -> None:
    """
    Decay error count and reactivate key if cooling period expired.
    
    Args:
        db: Database session
        key: ProviderKey instance
        settings: AppSettings instance
        now: Current datetime
    """
    decay_minutes = settings.key_error_decay_minutes
    
    # Decay error count if last error is old enough
    if key.last_error_at:
        # Ensure both datetimes are timezone-aware
        if key.last_error_at.tzinfo is None:
            # If last_error_at is naive, make it aware (UTC)
            from datetime import timezone
            last_error_aware = key.last_error_at.replace(tzinfo=timezone.utc)
        else:
            last_error_aware = key.last_error_at
        
        if now.tzinfo is None:
            from datetime import timezone
            now_aware = now.replace(tzinfo=timezone.utc)
        else:
            now_aware = now
        
        error_age_minutes = (now_aware - last_error_aware).total_seconds() / 60
        if error_age_minutes >= decay_minutes:
            key.error_count_recent = 0
    
    # Reactivate if cooling period expired
    if key.status == "cooling_down":
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
            
            if cooling_until_aware <= now_aware:
                key.status = "active"
                key.cooling_until = None
                db.add(key)
                db.commit()


def update_key_usage(db: Session, key: ProviderKey, now: datetime) -> None:
    """
    Update last_used_at timestamp for a key in the database.
    
    Args:
        db: Database session
        key: ProviderKey instance
        now: Current datetime
    """
    key.last_used_at = now
    db.add(key)
    db.commit()


# Legacy wrapper for backward compatibility
def choose_key_for_provider(db: Session, provider: str) -> ProviderKey:
    """
    Legacy wrapper around choose_best_key for backward compatibility.
    
    Raises HTTPException if no key available (old behavior).
    """
    from app.config import get_settings
    
    settings = get_settings()
    now = datetime.utcnow()
    
    key = choose_best_key(db, provider, settings, now)
    
    if not key:
        raise HTTPException(
            status_code=503,
            detail=f"No available keys for provider '{provider}'"
        )
    
    return key
