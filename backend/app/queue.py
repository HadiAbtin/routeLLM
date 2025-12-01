import redis
from rq import Queue
from app.config import get_settings

_settings = get_settings()


def get_redis_connection() -> redis.Redis:
    """
    Get a Redis connection using settings.
    
    Returns:
        Redis client instance
    """
    import os
    # Check environment variable first (for Docker), then use settings
    redis_url = os.getenv("REDIS_URL") or _settings.redis_url
    return redis.from_url(redis_url)


def get_default_queue() -> Queue:
    """
    Get the default RQ queue.
    
    Returns:
        RQ Queue instance connected to Redis
    """
    redis_conn = get_redis_connection()
    return Queue("default", connection=redis_conn)

