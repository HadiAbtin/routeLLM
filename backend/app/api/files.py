from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import uuid
import os
from pathlib import Path
import shutil
import logging

from app.db import get_db
from app.models import StoredFile, User
from app.config import get_settings
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/files", tags=["files"])

settings = get_settings()


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload one or more files.
    
    Returns metadata for each uploaded file including:
    - id: unique file identifier
    - filename: original filename
    - mime_type: MIME type
    - size_bytes: file size
    - url: URL to access the file
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    storage_dir = Path(settings.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        # Generate unique ID
        file_id = uuid.uuid4()
        
        # Sanitize filename (remove path components for security)
        safe_filename = os.path.basename(file.filename)
        if not safe_filename:
            safe_filename = f"file_{file_id}"
        
        # Create storage path
        storage_path = storage_dir / f"{file_id}_{safe_filename}"
        
        # Read file content and write to disk
        try:
            content = await file.read()
            size_bytes = len(content)
            
            # Write file
            with open(storage_path, "wb") as f:
                f.write(content)
            
            # Create database record
            db_file = StoredFile(
                id=file_id,
                filename=safe_filename,
                mime_type=file.content_type or "application/octet-stream",
                size_bytes=size_bytes,
                storage_path=str(storage_path)
            )
            
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            
            # Generate public URL
            public_url = f"{settings.public_base_url}/v1/files/{file_id}"
            
            uploaded_files.append({
                "id": str(file_id),
                "filename": safe_filename,
                "mime_type": file.content_type or "application/octet-stream",
                "size_bytes": size_bytes,
                "url": public_url
            })
            
        except Exception as e:
            # Clean up file if DB insert fails
            if storage_path.exists():
                storage_path.unlink()
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    return {"files": uploaded_files}


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a file by its ID.
    
    Returns the file with appropriate Content-Type header.
    """
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    db_file = db.query(StoredFile).filter(StoredFile.id == file_uuid).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    storage_path = Path(db_file.storage_path)
    
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=str(storage_path),
        filename=db_file.filename,
        media_type=db_file.mime_type
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a file by its ID.
    
    Removes both the database record and the physical file from disk.
    """
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    db_file = db.query(StoredFile).filter(StoredFile.id == file_uuid).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    storage_path = Path(db_file.storage_path)
    
    # Delete physical file
    if storage_path.exists():
        try:
            storage_path.unlink()
            logger.info(f"Deleted file from disk: {storage_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file from disk: {storage_path}, error: {str(e)}")
            # Continue with DB deletion even if file deletion fails
    
    # Delete database record
    db.delete(db_file)
    db.commit()
    
    return {"message": "File deleted successfully", "file_id": str(file_id)}


@router.delete("/")
async def delete_files(
    file_ids: List[str] = Query(..., description="List of file IDs to delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete multiple files by their IDs.
    
    Accepts a list of file IDs and deletes all of them.
    Returns information about successfully deleted files and any errors.
    """
    if not file_ids:
        raise HTTPException(status_code=400, detail="No file IDs provided")
    
    deleted_files = []
    not_found_files = []
    errors = []
    
    # Convert string IDs to UUIDs and validate
    file_uuids = []
    id_mapping = {}
    for file_id_str in file_ids:
        try:
            file_uuid = uuid.UUID(file_id_str)
            file_uuids.append(file_uuid)
            id_mapping[file_uuid] = file_id_str
        except ValueError:
            errors.append({"file_id": file_id_str, "error": "Invalid file ID format"})
    
    if not file_uuids:
        return {
            "deleted": [],
            "not_found": [],
            "errors": errors
        }
    
    # Query all files at once
    db_files = db.query(StoredFile).filter(StoredFile.id.in_(file_uuids)).all()
    found_uuids = {file.id for file in db_files}
    
    # Process found files
    for db_file in db_files:
        storage_path = Path(db_file.storage_path)
        
        # Delete physical file
        if storage_path.exists():
            try:
                storage_path.unlink()
                logger.info(f"Deleted file from disk: {storage_path}")
            except Exception as e:
                logger.warning(f"Failed to delete file from disk: {storage_path}, error: {str(e)}")
                errors.append({
                    "file_id": str(db_file.id),
                    "error": f"Failed to delete file from disk: {str(e)}"
                })
        
        # Delete database record
        try:
            db.delete(db_file)
            deleted_files.append(str(db_file.id))
        except Exception as e:
            logger.error(f"Failed to delete file record from database: {db_file.id}, error: {str(e)}")
            errors.append({
                "file_id": str(db_file.id),
                "error": f"Failed to delete database record: {str(e)}"
            })
    
    # Find not found files
    for file_uuid in file_uuids:
        if file_uuid not in found_uuids:
            not_found_files.append(id_mapping[file_uuid])
    
    # Commit all deletions
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to commit file deletions: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to commit deletions: {str(e)}")
    
    return {
        "deleted": deleted_files,
        "not_found": not_found_files,
        "errors": errors,
        "summary": {
            "total_requested": len(file_ids),
            "deleted": len(deleted_files),
            "not_found": len(not_found_files),
            "errors": len(errors)
        }
    }

