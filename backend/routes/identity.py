"""
Identity context routes for downstream apps
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from database import get_db
from models import User, Company, UserRole as UserRoleEnum
from schemas import UserResponse, CompanyResponse, TokenVerifyResponse
from auth import get_current_user, verify_token_external

router = APIRouter(prefix="/identity", tags=["Identity Context"])
security = HTTPBearer(auto_error=False)


@router.get("/context", response_model=TokenVerifyResponse)
async def get_identity_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full identity context from a token or API key.
    Used by downstream apps to get user/company info.
    """
    if not credentials:
        return {"valid": False, "error": "No authentication provided"}
    
    return verify_token_external(credentials.credentials)


@router.get("/user/{user_id}", response_model=UserResponse)
async def get_user_by_id_for_apps(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user info by ID (for downstream apps with valid token/API key).
    Only returns users within the same company for non-sysadmins.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user.role != UserRoleEnum.SYSADMIN:
        if user.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return UserResponse.model_validate(user)


@router.get("/company/{company_id}", response_model=CompanyResponse)
async def get_company_by_id_for_apps(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get company info by ID (for downstream apps with valid token/API key).
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        if current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return CompanyResponse.model_validate(company)
