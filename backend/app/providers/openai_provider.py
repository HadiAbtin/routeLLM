import httpx
from fastapi import HTTPException
from typing import Dict, Any, Optional
import logging
import os

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse, ChatResponseMessage, Usage, ChatMessage
from app.providers.base import BaseProvider
from app.providers.errors import ProviderRateLimitError, ProviderTransientError, ProviderClientError, ProviderAuthenticationError
from app.models import StoredFile

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation."""
    
    name = "openai"
    supports_attachments = True  # OpenAI supports vision models with image attachments
    
    def _build_openai_message(self, message: ChatMessage, stored_files: Optional[dict] = None) -> dict:
        """
        Build an OpenAI message format, handling attachments for multimodal support.
        
        For OpenAI vision models, content is an array of parts:
        - {"type": "text", "text": "..."}
        - {"type": "image_url", "image_url": {"url": "https://..."}}
        """
        parts = []
        
        # Add text content if present
        if message.content:
            parts.append({"type": "text", "text": message.content})
        
        # Add attachments if present
        if message.attachments and stored_files:
            for att in message.attachments:
                stored_file = stored_files.get(att.file_id)
                if not stored_file:
                    logger.warning(f"File {att.file_id} not found in stored_files, skipping attachment")
                    continue
                
                if att.type == "image":
                    # For OpenAI vision, use the public URL
                    # stored_file is a dict with keys: id, filename, mime_type, size_bytes, public_url
                    image_url = stored_file.get("public_url")
                    if not image_url:
                        # Fallback: construct URL from file_id
                        image_url = f"{get_settings().public_base_url}/v1/files/{att.file_id}"
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    })
                else:
                    # For non-image files, add as text reference
                    parts.append({
                        "type": "text",
                        "text": f"[Attached file: {stored_file.get('filename', 'file')}]"
                    })
        
        # If no parts, return simple format (backward compatibility)
        if not parts:
            return {"role": message.role, "content": message.content or ""}
        
        # Return multimodal format
        return {"role": message.role, "content": parts}
    
    async def chat(self, key: str, request: ChatRequest, stored_files: Optional[dict] = None) -> ChatResponse:
        """
        Send a chat completion request to OpenAI.
        
        Args:
            key: API key to use for this request
            request: ChatRequest with messages and optional parameters
            
        Returns:
            ChatResponse with model, message, and usage information
            
        Raises:
            HTTPException: If API key is missing or request fails
        """
        if not key:
            raise HTTPException(
                status_code=500,
                detail="OpenAI API key is not provided."
            )
        
        settings = get_settings()
        
        # Determine model to use
        model = request.model or settings.openai_default_model
        
        # Determine base URL
        base_url = settings.openai_base_url or "https://api.openai.com/v1"
        
        # Prepare messages for OpenAI API (with multimodal support if attachments present)
        messages = [
            self._build_openai_message(msg, stored_files)
            for msg in request.messages
        ]
        
        # Prepare payload
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages
        }
        
        # Add optional parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        # Configure proxy if available
        # httpx automatically reads HTTP_PROXY and HTTPS_PROXY from environment variables
        # Set them from settings if provided (httpx will use them automatically)
        if settings.http_proxy:
            os.environ["HTTP_PROXY"] = settings.http_proxy
        if settings.https_proxy:
            os.environ["HTTPS_PROXY"] = settings.https_proxy
        
        # Make request to OpenAI
        # httpx will automatically use HTTP_PROXY/HTTPS_PROXY from environment
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                # Handle non-200 responses
                if response.status_code != 200:
                    error_body = response.text
                    logger.error(f"OpenAI API error: {response.status_code} - {error_body}")
                    
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
                            f"OpenAI API rate limit: {error_message}",
                            retry_after=retry_after
                        )
                    elif response.status_code >= 500:
                        raise ProviderTransientError(f"OpenAI API server error: {error_message}")
                    elif response.status_code == 401 or "authentication" in error_message.lower() or ("invalid" in error_message.lower() and "api" in error_message.lower()):
                        # Authentication errors: disable the key and allow failover to another key
                        raise ProviderAuthenticationError(f"OpenAI API authentication error: {error_message}")
                    else:
                        raise ProviderClientError(f"OpenAI API client error: {error_message}")
                
                # Parse successful response
                data = response.json()
                
                # Extract response data
                choice = data["choices"][0]
                message_data = choice["message"]
                
                # Build response message
                response_message = ChatResponseMessage(
                    role=message_data["role"],
                    content=message_data["content"]
                )
                
                # Extract usage if present
                usage = None
                if "usage" in data:
                    usage_data = data["usage"]
                    usage = Usage(
                        prompt_tokens=usage_data.get("prompt_tokens"),
                        completion_tokens=usage_data.get("completion_tokens"),
                        total_tokens=usage_data.get("total_tokens")
                    )
                
                return ChatResponse(
                    model=data["model"],
                    message=response_message,
                    usage=usage
                )
                
            except httpx.TimeoutException:
                logger.error("OpenAI API request timed out")
                raise ProviderTransientError("Request to OpenAI API timed out")
            except httpx.RequestError as e:
                logger.error(f"OpenAI API request error: {str(e)}")
                raise ProviderTransientError(f"Failed to connect to OpenAI API: {str(e)}")
