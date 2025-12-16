import httpx
from fastapi import HTTPException
from typing import Dict, Any, Optional
import logging
import os
import base64

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse, ChatResponseMessage, Usage, ChatMessage
from app.providers.base import BaseProvider, resolve_storage_path
from app.providers.errors import ProviderRateLimitError, ProviderTransientError, ProviderClientError, ProviderAuthenticationError

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic (Claude) provider implementation."""
    
    name = "anthropic"
    supports_attachments = True  # Claude 3.5 supports images
    
    def _build_anthropic_message(self, message: ChatMessage, stored_files: Optional[dict] = None) -> dict:
        """
        Build an Anthropic message format, handling attachments for multimodal support.
        
        Anthropic Claude 3.5 supports images via content blocks:
        - {"type": "text", "text": "..."}
        - {"type": "image", "source": {"type": "url", "url": "..."}}
        """
        content_blocks = []
        
        # Add text content if present
        if message.content:
            content_blocks.append({"type": "text", "text": message.content})
        
        # Add attachments if present
        logger.info(f"Checking attachments: message.attachments={message.attachments}, stored_files keys={list(stored_files.keys()) if stored_files else None}")
        if message.attachments and stored_files:
            logger.info(f"Processing {len(message.attachments)} attachments")
            for att in message.attachments:
                stored_file = stored_files.get(att.file_id)
                if not stored_file:
                    logger.warning(f"File {att.file_id} not found in stored_files, skipping attachment")
                    continue
                
                if att.type == "image":
                    # For Anthropic, we need to use base64 encoding since localhost URLs won't work
                    # Fetch the image file and encode it
                    try:
                        # Use helper function to resolve storage path
                        storage_path_str = stored_file.get("storage_path", "")
                        storage_path = resolve_storage_path(storage_path_str, att.file_id)
                        
                        if not storage_path or not storage_path.exists():
                            logger.error(f"Image file not found for {att.file_id} (path: {storage_path_str})")
                            continue
                        
                        logger.info(f"Encoding image from path: {storage_path}")
                        
                        # Read and encode image
                        with open(storage_path, "rb") as f:
                            image_data = f.read()
                            image_base64 = base64.b64encode(image_data).decode("utf-8")
                        
                        logger.info(f"Image encoded successfully, size: {len(image_base64)} chars")
                        
                        # Determine media type
                        mime_type = stored_file.get("mime_type", "image/jpeg")
                        
                        # Anthropic requires base64 with data URI format
                        content_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_base64
                            }
                        })
                        logger.info(f"Added image content block for file {att.file_id}")
                    except Exception as e:
                        logger.error(f"Failed to encode image {att.file_id}: {str(e)}", exc_info=True)
                        # Fallback: add as text reference
                        content_blocks.append({
                            "type": "text",
                            "text": f"[Image: {stored_file.get('filename', 'image')} - failed to encode]"
                        })
                else:
                    # For non-image files, add as text reference
                    content_blocks.append({
                        "type": "text",
                        "text": f"[Attached file: {stored_file.get('filename', 'file')}]"
                    })
        
        # If no content blocks, return simple text format (backward compatibility)
        if not content_blocks:
            return {
                "role": message.role,
                "content": message.content or ""
            }
        
        # Return multimodal format
        return {
            "role": message.role,
            "content": content_blocks
        }
    
    async def chat(self, key: str, request: ChatRequest, stored_files: Optional[dict] = None) -> ChatResponse:
        """
        Send a chat completion request to Anthropic Claude API.
        
        Args:
            key: API key to use for this request
            request: ChatRequest with messages and optional parameters
            stored_files: Optional dict mapping file_id -> stored file info for attachments
            
        Returns:
            ChatResponse with model, message, and usage information
            
        Raises:
            HTTPException: If API key is missing or request fails
        """
        if not key:
            raise ProviderClientError("Anthropic API key is not provided.")
        
        settings = get_settings()
        
        # Determine model to use (default from config)
        # Valid models: claude-3-5-sonnet-20241022, claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
        model = request.model or settings.anthropic_default_model
        
        # Anthropic API base URL
        base_url = "https://api.anthropic.com/v1"
        
        # Prepare messages for Anthropic API
        # Anthropic uses a different format - it needs system message separately
        # And supports multimodal content blocks for images
        messages = []
        system_message = None
        
        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                # Build message with multimodal support
                anthropic_msg = self._build_anthropic_message(msg, stored_files)
                messages.append(anthropic_msg)
        
        # Prepare payload for Anthropic API
        # Use request max_tokens if provided, otherwise use default from settings
        # Anthropic has model-specific limits (e.g., claude-opus-4-5: 64000, claude-sonnet-4-5: 8192)
        # We'll use the default and let API enforce its limits (it will return an error if exceeded)
        max_tokens = request.max_tokens or settings.default_max_tokens
        
        # Cap at Anthropic's maximum (64000 for most models)
        # This prevents API errors for models with lower limits
        max_tokens = min(max_tokens, 64000)
        
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens  # Anthropic requires max_tokens
        }
        
        # Add system message if present
        if system_message:
            payload["system"] = system_message
        
        # Add optional parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        
        # Prepare headers for Anthropic API
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Log for debugging
        logger.debug(f"Anthropic API request - Model: {model}, Base URL: {base_url}")
        
        # Configure proxy if available
        if settings.http_proxy:
            os.environ["HTTP_PROXY"] = settings.http_proxy
        if settings.https_proxy:
            os.environ["HTTPS_PROXY"] = settings.https_proxy
        
        # Make request to Anthropic API
        # TEST: Simulate 429 for testing retry logic
        if request.messages and len(request.messages) > 0:
            first_content = request.messages[0].content if hasattr(request.messages[0], 'content') else ""
            if first_content == "force429":
                logger.warning("Simulating 429 rate limit error for testing")
                raise ProviderRateLimitError(
                    "Simulated rate limit error for testing",
                    retry_after=30.0
                )
            elif first_content == "force_transient_error":
                logger.warning("Simulating transient error for testing")
                raise ProviderTransientError("Simulated transient error for testing")
        
        # Use configurable timeout (default 30 minutes for long-running requests)
        timeout_seconds = settings.provider_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{base_url}/messages",
                    json=payload,
                    headers=headers
                )
                
                # Handle non-200 responses
                if response.status_code != 200:
                    error_body = response.text
                    logger.error(f"Anthropic API error: {response.status_code} - {error_body}")
                    
                    # Try to parse error message
                    try:
                        error_json = response.json()
                        # Anthropic error format: {"error": {"type": "...", "message": "..."}}
                        error_type = error_json.get("error", {}).get("type", "")
                        error_message = error_json.get("error", {}).get("message", "Unknown error")
                        full_error = f"{error_type}: {error_message}" if error_type else error_message
                    except:
                        full_error = error_body
                    
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
                            f"Anthropic API rate limit: {full_error}",
                            retry_after=retry_after
                        )
                    elif response.status_code >= 500:
                        raise ProviderTransientError(f"Anthropic API server error: {full_error}")
                    elif response.status_code == 401 or "authentication" in error_type.lower() or ("invalid" in error_message.lower() and "api-key" in error_message.lower()):
                        # Authentication errors: disable the key and allow failover to another key
                        raise ProviderAuthenticationError(f"Anthropic API authentication error: {full_error}")
                    else:
                        raise ProviderClientError(f"Anthropic API client error: {full_error}")
                
                # Parse successful response
                data = response.json()
                
                # Anthropic API response format is different
                # Extract the first content block (usually text)
                content_blocks = data.get("content", [])
                if not content_blocks:
                    raise HTTPException(
                        status_code=500,
                        detail="Anthropic API returned empty content"
                    )
                
                # Get the first text content block
                first_content = content_blocks[0]
                if first_content.get("type") != "text":
                    raise HTTPException(
                        status_code=500,
                        detail=f"Unsupported content type: {first_content.get('type')}"
                    )
                
                # Build response message
                response_message = ChatResponseMessage(
                    role="assistant",
                    content=first_content.get("text", "")
                )
                
                # Extract usage if present
                usage = None
                if "usage" in data:
                    usage_data = data["usage"]
                    input_tokens = usage_data.get("input_tokens", 0)
                    output_tokens = usage_data.get("output_tokens", 0)
                    total_tokens = input_tokens + output_tokens
                    logger.info(f"Anthropic API usage: input_tokens={input_tokens}, output_tokens={output_tokens}, total_tokens={total_tokens}")
                    usage = Usage(
                        prompt_tokens=input_tokens,  # Anthropic uses "input_tokens"
                        completion_tokens=output_tokens,  # Anthropic uses "output_tokens"
                        total_tokens=total_tokens
                    )
                
                return ChatResponse(
                    model=data.get("model", model),
                    message=response_message,
                    usage=usage
                )
                
            except httpx.TimeoutException:
                logger.error("Anthropic API request timed out")
                raise ProviderTransientError("Request to Anthropic API timed out")
            except httpx.RequestError as e:
                logger.error(f"Anthropic API request error: {str(e)}")
                raise ProviderTransientError(f"Failed to connect to Anthropic API: {str(e)}")

