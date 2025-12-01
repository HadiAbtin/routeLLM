from typing import Dict
from app.providers.base import BaseProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.deepseek_provider import DeepSeekProvider
from app.providers.gemini_provider import GeminiProvider

# Registry of available providers
PROVIDERS: Dict[str, BaseProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "deepseek": DeepSeekProvider(),
    "gemini": GeminiProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """
    Get a provider instance by name.
    
    Args:
        name: Provider name (e.g. "openai", "anthropic")
        
    Returns:
        BaseProvider instance
        
    Raises:
        ValueError: If provider is not found
    """
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available providers: {list(PROVIDERS.keys())}")
    
    return PROVIDERS[name]

