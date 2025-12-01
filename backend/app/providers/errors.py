"""
Provider error hierarchy for clear error handling and retry logic.
"""
from typing import Optional


class ProviderError(Exception):
    """Base exception for all provider-related errors."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider returns 429 rate limit error."""
    
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderTransientError(ProviderError):
    """Raised for transient errors (5xx, network, timeout) that may succeed on retry."""
    pass


class ProviderClientError(ProviderError):
    """Raised for client errors (4xx except 429) that are not retriable."""
    pass

