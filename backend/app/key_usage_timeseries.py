from dataclasses import dataclass
from typing import List
import time
from datetime import datetime
import logging
import json

from app.queue import get_redis_connection

logger = logging.getLogger(__name__)


@dataclass
class TokenSample:
  timestamp: float  # seconds since epoch
  tokens: int

  def to_dict(self) -> dict:
    return {"timestamp": self.timestamp, "tokens": self.tokens}
  
  @classmethod
  def from_dict(cls, data: dict) -> "TokenSample":
    return cls(timestamp=data["timestamp"], tokens=data["tokens"])


# Keep up to this many seconds (e.g. 24 hours)
_MAX_WINDOW_SECONDS = 24 * 60 * 60

# Redis key prefix for token samples
_REDIS_KEY_PREFIX = "key_tokens:"


def _get_redis_key(key_id: str) -> str:
  """Get Redis key for a provider key ID."""
  return f"{_REDIS_KEY_PREFIX}{key_id}"


def _get_redis():
  """Get Redis connection."""
  try:
    return get_redis_connection()
  except Exception as e:
    logger.error(f"Failed to get Redis connection: {e}")
    raise


def record_key_tokens(key_id: str, tokens: int) -> None:
  """
  Record a token usage sample for a given key.
  Stores data in Redis so it's accessible from both worker and backend.

  Args:
      key_id: Provider key ID (UUID as string)
      tokens: Number of tokens used in this request (total)
  """
  if tokens <= 0:
      logger.debug(f"Skipping token recording for key {key_id}: tokens={tokens} (non-positive)")
      return

  now = time.time()
  sample = TokenSample(timestamp=now, tokens=int(tokens))
  
  try:
    redis_client = _get_redis()
    redis_key = _get_redis_key(key_id)
    
    # Add new sample to Redis list (left push for FIFO)
    sample_json = json.dumps(sample.to_dict())
    redis_client.lpush(redis_key, sample_json)
    
    # Set expiration on the key (max window + buffer)
    redis_client.expire(redis_key, _MAX_WINDOW_SECONDS + 3600)

    # Evict old samples beyond max window
    cutoff = now - _MAX_WINDOW_SECONDS
    evicted = 0
    
    # Get all samples and filter
    all_samples_json = redis_client.lrange(redis_key, 0, -1)
    valid_samples = []
    
    for sample_json_str in all_samples_json:
      try:
        sample_data = json.loads(sample_json_str)
        sample_ts = sample_data["timestamp"]
        if sample_ts >= cutoff:
          valid_samples.append(sample_json_str)
        else:
          evicted += 1
      except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Invalid sample data in Redis for key {key_id}: {e}")
        evicted += 1
    
    # Replace list with valid samples only
    if evicted > 0:
      redis_client.delete(redis_key)
      if valid_samples:
        redis_client.rpush(redis_key, *valid_samples)
        redis_client.expire(redis_key, _MAX_WINDOW_SECONDS + 3600)
    
    total_samples = len(valid_samples)
    logger.info(f"Recorded {tokens} tokens for key {key_id} at {datetime.utcfromtimestamp(now).isoformat()}Z (total samples: {total_samples}, evicted: {evicted})")
    
  except Exception as e:
    logger.error(f"Failed to record tokens in Redis for key {key_id}: {e}")
    # Fallback: log but don't fail
    logger.warning(f"Token recording failed, but continuing. Key: {key_id}, Tokens: {tokens}")


def get_key_tokens_timeseries(
  key_id: str,
  window_minutes: int,
  step_seconds: int,
) -> List[dict]:
  """
  Build a simple timeseries of token usage for a key over the given window.
  Reads data from Redis.

  Returns list of points sorted by time:
      [{ "ts": ISO8601, "tokens": int }, ...]
  """
  now = time.time()
  window_seconds = window_minutes * 60
  start = now - window_seconds

  try:
    redis_client = _get_redis()
    redis_key = _get_redis_key(key_id)
    
    # Get all samples from Redis
    all_samples_json = redis_client.lrange(redis_key, 0, -1)
    
    if not all_samples_json:
      logger.debug(f"No token samples found for key {key_id} in Redis")
      return []

    # Parse and filter samples within window
    samples = []
    for sample_json_str in all_samples_json:
      try:
        sample_data = json.loads(sample_json_str)
        sample = TokenSample.from_dict(sample_data)
        if sample.timestamp >= start:
          samples.append(sample)
      except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Invalid sample data in Redis for key {key_id}: {e}")
        continue

    if not samples:
      logger.debug(f"No samples within {window_minutes} minute window for key {key_id} (window start: {datetime.utcfromtimestamp(start).isoformat()}Z)")
      return []

    logger.info(f"Retrieving timeseries for key {key_id}: {len(samples)} samples in {window_minutes} minute window")

    # Calculate bucket count
    bucket_count = max(1, int(window_seconds // step_seconds))
    buckets = [0] * bucket_count

    # Align buckets to current time
    # We want the last bucket to include "now", so we align to the next step boundary
    # Example: if now=15:29:14 and step=300 (5 min):
    #   - Round up to next boundary: 15:30:00
    #   - Last bucket: 15:25:00 to 15:30:00 (includes now)
    #   - Previous bucket: 15:20:00 to 15:25:00
    now_aligned_up = int((now + step_seconds - 1) // step_seconds) * step_seconds
    # Last bucket ends at now_aligned_up, starts at now_aligned_up - step_seconds
    end_time = now_aligned_up  # Last bucket ends here (exclusive, so includes now)
    start_time = end_time - (bucket_count * step_seconds)

    # Assign samples to buckets
    for s in samples:
      # Calculate which bucket this sample belongs to
      # Buckets are aligned to end_time (current time)
      idx = int((s.timestamp - start_time) // step_seconds)
      if idx < 0:
        # Sample is before our window, skip it
        continue
      if idx >= bucket_count:
        # Sample is after our window, put it in the last bucket
        idx = bucket_count - 1
      buckets[idx] += s.tokens

    # Generate points with aligned timestamps
    points: List[dict] = []
    for i, value in enumerate(buckets):
      # Calculate bucket start time (aligned to step boundaries)
      bucket_ts = start_time + i * step_seconds
      points.append(
        {
          "ts": datetime.utcfromtimestamp(bucket_ts).isoformat() + "Z",
          "tokens": value,
        }
      )

    return points

  except Exception as e:
    logger.error(f"Failed to get timeseries from Redis for key {key_id}: {e}")
    return []


def get_all_keys_with_data() -> List[str]:
  """
  Get list of all key IDs that have token usage data in Redis.
  Useful for debugging.
  """
  try:
    redis_client = _get_redis()
    # Get all keys matching the pattern
    pattern = f"{_REDIS_KEY_PREFIX}*"
    keys = redis_client.keys(pattern)
    # Extract key IDs (remove prefix)
    key_ids = [key.decode().replace(_REDIS_KEY_PREFIX, "") for key in keys]
    return key_ids
  except Exception as e:
    logger.error(f"Failed to get keys from Redis: {e}")
    return []


def get_key_sample_count(key_id: str) -> int:
  """
  Get the number of samples stored for a key in Redis.
  Useful for debugging.
  """
  try:
    redis_client = _get_redis()
    redis_key = _get_redis_key(key_id)
    count = redis_client.llen(redis_key)
    return count
  except Exception as e:
    logger.error(f"Failed to get sample count from Redis for key {key_id}: {e}")
    return 0
