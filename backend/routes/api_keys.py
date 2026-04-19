"""
API Key routes for Identity & Employee Hub
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from typing import List
import uuid
import json

from database import get_db
from models import User, APIKey, APIKeyScope
from schemas import APIKeyCreate, APIKeyResponse, APIKeyCreatedResponse, APIKeyScope as APIKeyScopeSchema
from auth import get_current_user, generate_api_key, hash_token

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys for the current user"""
    result = await db.execute(
        select(APIKey).where(
            APIKey.user_id == current_user.id,
            APIKey.revoked == False
        ).order_by(APIKey.created_at.desc())
    )
    return [APIKeyResponse.model_validate(key) for key in result.scalars().all()]


@router.post("", response_model=APIKeyCreatedResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key. The full key is only returned once."""
    full_key, prefix = generate_api_key()
    key_hash = hash_token(full_key)
    
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=key_data.expires_in_days)
    
    allowed_apps_json = None
    if key_data.scope == APIKeyScopeSchema.APPS_ONLY and key_data.allowed_apps:
        allowed_apps_json = json.dumps([str(app_id) for app_id in key_data.allowed_apps])
    
    api_key = APIKey(
        user_id=current_user.id,
        company_id=current_user.company_id,
        name=key_data.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scope=APIKeyScope(key_data.scope.value),
        allowed_apps=allowed_apps_json,
        expires_at=expires_at
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scope=api_key.scope,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        api_key=full_key
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke an API key"""
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.revoked = True
    api_key.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "API key revoked"}
