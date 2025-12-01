import httpx
from fastapi import HTTPException
from typing import Dict, Any, List
import logging
import os

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse, ChatResponseMessage, Usage
from app.providers.base import BaseProvider
from app.providers.errors import ProviderRateLimitError, ProviderTransientError, ProviderClientError, ProviderAuthenticationError

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """Google Gemini provider implementation."""
    
    name = "gemini"
    supports_attachments = False  # Not implemented yet
    
    async def chat(self, key: str, request: ChatRequest, stored_files: dict = None) -> ChatResponse:
        """
        Send a chat completion request to Google Gemini API.
        
        Args:
            key: API key to use for this request
            request: ChatRequest with messages and optional parameters
            
        Returns:
            ChatResponse with model, message, and usage information
            
        Raises:
            HTTPException: If API key is missing or request fails
        """
        if not key:
            raise ProviderClientError("Gemini API key is not provided.")
        
        settings = get_settings()
        
        # Determine model to use (default from config)
        model = request.model or settings.gemini_default_model
        
        # Gemini API base URL
        base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        # Prepare contents for Gemini API
        # Gemini uses a different format - it expects "contents" array with parts
        contents: List[Dict[str, Any]] = []
        system_instruction = None
        
        for msg in request.messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                # Map roles: OpenAI uses "assistant", Gemini uses "model"
                role = "model" if msg.role == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })
        
        # Prepare payload for Gemini API
        payload: Dict[str, Any] = {
            "contents": contents
        }
        
        # Add system instruction if present
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        # Add generation config
        generation_config: Dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        
        if generation_config:
            payload["generationConfig"] = generation_config
        
        # Prepare headers
        # Gemini uses API key as query parameter, not header
        # But we'll use it in the URL
        
        # Configure proxy if available
        if settings.http_proxy:
            os.environ["HTTP_PROXY"] = settings.http_proxy
        if settings.https_proxy:
            os.environ["HTTPS_PROXY"] = settings.https_proxy
        
        # Make request to Gemini API
        # Note: Gemini uses API key as query parameter
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{base_url}/models/{model}:generateContent?key={key}",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                # Handle non-200 responses
                if response.status_code != 200:
                    error_body = response.text
                    logger.error(f"Gemini API error: {response.status_code} - {error_body}")
                    
                    # Try to parse error message
                    try:
                        error_json = response.json()
                        error_message = error_json.get("error", {}).get("message", "Unknown error")
                    except:
                        error_message = error_body
                    
                    # Parse Retry-After header if present
                    retry_after = None
                    if "retry-after" in response.headers:
                        try:
                            retry_after = float(response.headers["retry-after"])
                        except (ValueError, TypeError):
                            pass
                    
                    # Map status codes to error types
                    if response.status_code == 429:
                        raise ProviderRateLimitError(
                            f"Gemini API rate limit: {error_message}",
                            retry_after=retry_after
                        )
                    elif response.status_code >= 500:
                        raise ProviderTransientError(f"Gemini API server error: {error_message}")
                    elif response.status_code == 401 or "authentication" in error_message.lower() or ("invalid" in error_message.lower() and "api" in error_message.lower()):
                        # Authentication errors: disable the key and allow failover to another key
                        raise ProviderAuthenticationError(f"Gemini API authentication error: {error_message}")
                    else:
                        raise ProviderClientError(f"Gemini API client error: {error_message}")
                
                # Parse successful response
                data = response.json()
                
                # Gemini API response format
                if "candidates" not in data or not data["candidates"]:
                    raise ProviderTransientError("Gemini API returned no candidates")
                
                candidate = data["candidates"][0]
                if "content" not in candidate or "parts" not in candidate["content"]:
                    raise ProviderTransientError("Gemini API returned invalid response format")
                
                # Get the first text part
                parts = candidate["content"]["parts"]
                if not parts or "text" not in parts[0]:
                    raise ProviderTransientError("Gemini API returned empty content")
                
                text_content = parts[0]["text"]
                
                # Build response message
                response_message = ChatResponseMessage(
                    role="assistant",
                    content=text_content
                )
                
                # Extract usage if present
                usage = None
                if "usageMetadata" in data:
                    usage_data = data["usageMetadata"]
                    usage = Usage(
                        prompt_tokens=usage_data.get("promptTokenCount"),
                        completion_tokens=usage_data.get("candidatesTokenCount"),
                        total_tokens=usage_data.get("totalTokenCount")
                    )
                
                return ChatResponse(
                    model=model,
                    message=response_message,
                    usage=usage
                )
                
            except httpx.TimeoutException:
                logger.error("Gemini API request timed out")
                raise ProviderTransientError("Request to Gemini API timed out")
            except httpx.RequestError as e:
                logger.error(f"Gemini API request error: {str(e)}")
                raise ProviderTransientError(f"Failed to connect to Gemini API: {str(e)}")

