"""
Shared dependencies and helper functions for route modules
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from database import get_db
from models import User, Company, UserRole as UserRoleEnum
from schemas import CompanyBranding

security = HTTPBearer(auto_error=False)


def get_company_filter(user: User, model):
    """Get appropriate company filter based on user role"""
    if user.role == UserRoleEnum.SYSADMIN:
        return True  # No filter for sysadmin
    elif user.company_id:
        return model.company_id == user.company_id
    return False


async def get_company_admin_or_above(
    current_user: User = Depends(lambda: None)  # Will be injected properly
) -> User:
    """Require company_admin or sysadmin role"""
    if current_user.role not in [UserRoleEnum.SYSADMIN, UserRoleEnum.COMPANY_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_sysadmin(
    current_user: User = Depends(lambda: None)  # Will be injected properly
) -> User:
    """Require sysadmin role"""
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="System admin access required")
    return current_user


async def get_user_company_branding(user: User, db: AsyncSession) -> Optional[CompanyBranding]:
    """Get company branding for a user"""
    if not user.company_id:
        return None
    result = await db.execute(select(Company).where(Company.id == user.company_id))
    company = result.scalar_one_or_none()
    if company:
        return CompanyBranding(
            name=company.name,
            logo_url=company.logo_url,
            primary_color=company.primary_color,
            secondary_color=company.secondary_color
        )
    return None
