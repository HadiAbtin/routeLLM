from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging
from app.schemas import ChatRequest, ChatResponse
from app.config import get_settings

logger = logging.getLogger(__name__)


def resolve_storage_path(storage_path_str: str, file_id: str = None) -> Optional[Path]:
    """
    Helper function to resolve storage_path from DB to actual file path.
    
    Handles cases where storage_path might be:
    - Relative: "storage/file.jpg" -> resolves to storage_dir / "file.jpg"
    - Absolute: "/app/storage/file.jpg" -> uses as is
    - With "storage/" prefix: "storage/file.jpg" -> removes prefix and uses storage_dir
    
    Args:
        storage_path_str: Storage path from database
        file_id: Optional file ID for fallback glob search
        
    Returns:
        Resolved Path object, or None if not found
    """
    if not storage_path_str:
        return None
    
    settings = get_settings()
    storage_dir = Path(settings.storage_dir)
    
    storage_path = Path(storage_path_str)
    
    # If relative, make it absolute relative to storage_dir
    if not storage_path.is_absolute():
        # If storage_path already starts with "storage/", remove the prefix
        # because storage_dir is already "storage"
        if storage_path_str.startswith("storage/"):
            # Remove "storage/" prefix (8 chars) and use storage_dir directly
            relative_path = storage_path_str[8:]
            storage_path = storage_dir / relative_path
        else:
            storage_path = storage_dir / storage_path
    # If absolute but starts with storage_dir, use it as is
    elif str(storage_path).startswith(str(storage_dir)):
        # Already correct absolute path
        pass
    else:
        # Absolute path but not in storage_dir, try to use as is
        pass
    
    # Check if resolved path exists
    if storage_path.exists():
        return storage_path
    
    # Fallback: try to find file by matching file_id in filename
    if file_id:
        import glob
        pattern = str(storage_dir / f"{file_id}_*")
        matches = glob.glob(pattern)
        if matches:
            return Path(matches[0])
    
    logger.warning(f"Storage path not found: {storage_path_str} (resolved to: {storage_path})")
    return None


class BaseProvider(ABC):
    """Base class for LLM providers."""
    
    name: str  # e.g. "openai"
    supports_attachments: bool = False  # Whether this provider supports file/image attachments
    
    @abstractmethod
    async def chat(self, key: str, request: ChatRequest, stored_files: dict = None) -> ChatResponse:
        """
        Send a chat completion request to the provider.
        
        Args:
            key: API key to use for this request
            request: Chat request with messages and parameters
            stored_files: Optional dict mapping file_id -> StoredFile for attachments
            
        Returns:
            ChatResponse with model, message, and usage information
            
        Raises:
            HTTPException: If the request fails
        """
        pass

