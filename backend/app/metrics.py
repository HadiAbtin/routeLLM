from prometheus_client import Counter, Histogram, Gauge

# LLM requests counter
LLM_REQUESTS_TOTAL = Counter(
    "routellm_llm_requests_total",
    "Total LLM chat requests",
    ["provider", "status"]  # status: "success" | "error"
)

# LLM latency histogram (seconds)
LLM_REQUEST_LATENCY_SECONDS = Histogram(
    "routellm_llm_request_latency_seconds",
    "Latency of LLM chat requests in seconds",
    ["provider"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)  # Buckets for latency distribution
)

# Token usage counter
LLM_TOKENS_TOTAL = Counter(
    "routellm_llm_tokens_total",
    "Total tokens used",
    ["provider", "type"]  # type: "prompt" | "completion" | "total"
)

# Key error counter
KEY_ERRORS_TOTAL = Counter(
    "routellm_provider_key_errors_total",
    "Total errors per provider key",
    ["provider", "key_id", "kind"]  # kind: "rate_limit" | "transient" | "client"
)

# Key status gauge
PROVIDER_KEY_STATUS = Gauge(
    "routellm_provider_key_status",
    "Status of provider keys (1=active, 0=inactive/disabled)",
    ["provider", "key_id", "status"]
)

# In-memory counters for stats API (updated alongside Prometheus metrics)
PROVIDER_REQUEST_COUNTS: dict[str, dict[str, int]] = {}


def set_key_status(provider: str, key_id: str, status: str):
    """
    Update the status gauge for a provider key.
    
    Args:
        provider: Provider name (e.g. "openai", "anthropic")
        key_id: Key ID (UUID as string)
        status: Status ("active", "cooling_down", "disabled")
    """
    # Set the current status to 1
    PROVIDER_KEY_STATUS.labels(
        provider=provider,
        key_id=str(key_id),
        status=status
    ).set(1.0)
    
    # Set other statuses to 0 for this key
    for other_status in ["active", "cooling_down", "disabled"]:
        if other_status != status:
            PROVIDER_KEY_STATUS.labels(
                provider=provider,
                key_id=str(key_id),
                status=other_status
            ).set(0.0)


def update_provider_request_count(provider: str, status: str):
    """
    Update in-memory request counts for stats API.
    
    Args:
        provider: Provider name
        status: "success" or "error"
    """
    if provider not in PROVIDER_REQUEST_COUNTS:
        PROVIDER_REQUEST_COUNTS[provider] = {"success": 0, "error": 0}
    
    PROVIDER_REQUEST_COUNTS[provider][status] += 1


def get_provider_request_counts() -> dict[str, dict[str, int]]:
    """
    Get current in-memory request counts.
    
    Returns:
        Dictionary mapping provider -> {"success": int, "error": int}
    """
    return PROVIDER_REQUEST_COUNTS.copy()

