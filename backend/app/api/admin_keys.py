from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db import get_db
from app.models import ProviderKey, User
from app.schemas import ProviderKeyCreate, ProviderKeyUpdate, ProviderKeyRead
from app.api.auth import get_current_user

router = APIRouter(prefix="/v1/admin/keys", tags=["admin-keys"])


@router.get("", response_model=List[ProviderKeyRead])
def list_keys(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ProviderKeyRead]:
    """
    List all provider keys.
    
    Optional query parameters:
    - provider: Filter by provider name
    - status: Filter by status (active, cooling_down, disabled)
    """
    query = db.query(ProviderKey)
    
    if provider:
        query = query.filter(ProviderKey.provider == provider)
    if status:
        query = query.filter(ProviderKey.status == status)
    
    keys = query.order_by(ProviderKey.priority, ProviderKey.created_at).all()
    return keys


@router.post("", response_model=ProviderKeyRead, status_code=201)
def create_key(
    key_data: ProviderKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ProviderKeyRead:
    """
    Create a new provider key.
    """
    # Create new ProviderKey instance
    db_key = ProviderKey(**key_data.model_dump())
    
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    
    return db_key


@router.patch("/{key_id}", response_model=ProviderKeyRead)
def update_key(
    key_id: UUID,
    key_data: ProviderKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ProviderKeyRead:
    """
    Update a provider key (partial update).
    Only provided fields will be updated.
    """
    db_key = db.query(ProviderKey).filter(ProviderKey.id == key_id).first()
    
    if not db_key:
        raise HTTPException(status_code=404, detail="Provider key not found")
    
    # Update only provided fields
    update_data = key_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_key, field, value)
    
    db.commit()
    db.refresh(db_key)
    
    return db_key


@router.get("/{key_id}", response_model=ProviderKeyRead)
def get_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ProviderKeyRead:
    """
    Get a specific provider key by ID.
    """
    db_key = db.query(ProviderKey).filter(ProviderKey.id == key_id).first()
    
    if not db_key:
        raise HTTPException(status_code=404, detail="Provider key not found")
    
    return db_key


@router.delete("/{key_id}", status_code=204)
def delete_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> None:
    """
    Delete a provider key by ID.
    
    Returns 204 No Content on success.
    """
    db_key = db.query(ProviderKey).filter(ProviderKey.id == key_id).first()
    
    if not db_key:
        raise HTTPException(status_code=404, detail="Provider key not found")
    
    db.delete(db_key)
    db.commit()
    
    return None

