"""
Identity & Employee Hub API Server
Version 3.1.0 - Modular Architecture

Routes are organized into separate modules in /routes/:
- auth.py: Authentication (login, logout, password change, magic links)
- azure_sso.py: Azure AD SSO integration
- api_keys.py: API key management
- identity.py: Identity context for downstream apps
- email.py: Central email service
- admin.py: Migrations, audit logs, admin functions

Remaining routes in this file (to be modularized later):
- Companies, Apps, Users, Roles, Employees, Settings, Launchpad
"""

from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_, and_
from sqlalchemy.orm import selectinload
import os
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid

# Load environment before other imports
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from database import get_db, engine, async_session_maker
from models import (
    User, Role, App, RoleApp, UserApp, UserRoleAssignment, Employee, Settings, CompanySettings, Company,
    UserRole as UserRoleEnum, UserStatus, EmployeeStatus, AuthMethod, RefreshToken, APIKey, APIKeyScope,
    CompanyApp
)
from schemas import (
    LoginRequest, MagicLinkRequest, MagicLinkVerify, TokenResponse, ChangePasswordRequest,
    ChangeEmailRequest, ChangeCredentialsRequest, RefreshTokenResponse,
    UserCreate, UserUpdate, UserResponse, UserWithApps,
    RoleCreate, RoleUpdate, RoleResponse, RoleWithApps,
    AppCreate, AppUpdate, AppResponse,
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    SettingUpdate, SettingResponse, BambooHRSettings, AzureSSOSettings,
    RoleAppAssignment, UserAppAssignment, UserRoleAssignmentSchema,
    LaunchpadResponse, CompanyCreate, CompanyUpdate, CompanyResponse, CompanyBranding,
    APIKeyCreate, APIKeyResponse, APIKeyCreatedResponse, TokenVerifyResponse,
    APIKeyScope as APIKeyScopeSchema,
    CompanyAppCreate, CompanyAppUpdate, CompanyAppResponse, CompanyAppWithDetails, CompanyBrandingUpdate
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_admin_user, generate_magic_link_token,
    verify_token_external, MAGIC_LINK_EXPIRATION_MINUTES,
    create_and_store_refresh_token, validate_refresh_token, revoke_refresh_token,
    revoke_all_user_refresh_tokens, set_refresh_token_cookie, clear_refresh_token_cookie,
    generate_api_key, validate_api_key, hash_token
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Identity & Employee Hub API", version="3.2.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# ==================== IMPORT ROUTE MODULES ====================

from routes.auth import router as auth_router
from routes.azure_sso import router as azure_sso_router
from routes.api_keys import router as api_keys_router
from routes.identity import router as identity_router
from routes.email import router as email_router
from routes.admin import router as admin_router, log_audit_event, AuditAction

# Include route modules
api_router.include_router(auth_router)
api_router.include_router(azure_sso_router)
api_router.include_router(api_keys_router)
api_router.include_router(identity_router)
api_router.include_router(email_router)
api_router.include_router(admin_router)

# ==================== HELPER FUNCTIONS ====================

def get_company_filter(user: User, model):
    """Get appropriate company filter based on user role"""
    if user.role == UserRoleEnum.SYSADMIN:
        return True  # No filter for sysadmin
    elif user.company_id:
        return model.company_id == user.company_id
    return False

async def get_company_admin_or_above(current_user: User = Depends(get_current_user)) -> User:
    """Require company_admin or sysadmin role"""
    if current_user.role not in [UserRoleEnum.SYSADMIN, UserRoleEnum.COMPANY_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

async def get_sysadmin(current_user: User = Depends(get_current_user)) -> User:
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

# ==================== COMPANIES (SYSADMIN ONLY) ====================

@api_router.get("/companies", response_model=List[CompanyResponse])
async def list_companies(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """List all companies (sysadmin only)"""
    result = await db.execute(select(Company).order_by(Company.name))
    return [CompanyResponse.model_validate(c) for c in result.scalars().all()]

@api_router.post("/companies", response_model=CompanyResponse)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Create a new company (sysadmin only)"""
    existing = await db.execute(select(Company).where(Company.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Company slug already exists")
    
    company = Company(**data.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    
    await log_audit_event(AuditAction.CREATE, admin.id, admin.email, "company", str(company.id), f"Created company: {company.name}")
    return CompanyResponse.model_validate(company)

@api_router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Get company by ID"""
    if admin.role != UserRoleEnum.SYSADMIN and admin.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)

@api_router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: uuid.UUID, data: CompanyUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update a company"""
    if admin.role != UserRoleEnum.SYSADMIN and admin.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and data.is_active is not None:
        raise HTTPException(status_code=403, detail="Only sysadmin can change active status")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    
    await db.commit()
    await db.refresh(company)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "company", str(company.id), f"Updated company: {company.name}")
    return CompanyResponse.model_validate(company)

@api_router.delete("/companies/{company_id}")
async def delete_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Delete a company (sysadmin only)"""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company_name = company.name
    await db.delete(company)
    await db.commit()
    
    await log_audit_event(AuditAction.DELETE, admin.id, admin.email, "company", str(company_id), f"Deleted company: {company_name}")
    return {"message": "Company deleted"}

@api_router.get("/companies/{company_id}/branding", response_model=CompanyBranding)
async def get_company_branding(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get company branding (public endpoint for login page)"""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyBranding(name=company.name, logo_url=company.logo_url, primary_color=company.primary_color, secondary_color=company.secondary_color)

@api_router.put("/companies/my/branding", response_model=CompanyResponse)
async def update_my_company_branding(
    data: CompanyBrandingUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_company_admin_or_above)
):
    """Company admin can update their own company's branding (logo, colors)"""
    if not admin.company_id:
        raise HTTPException(status_code=400, detail="You are not associated with a company")
    
    result = await db.execute(select(Company).where(Company.id == admin.company_id))
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if data.logo_url is not None:
        company.logo_url = data.logo_url
    if data.primary_color is not None:
        company.primary_color = data.primary_color
    if data.secondary_color is not None:
        company.secondary_color = data.secondary_color
    
    await db.commit()
    await db.refresh(company)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "company", str(company.id), "Updated company branding")
    return CompanyResponse.model_validate(company)

# ==================== COMPANY APPS (Apps allocated to companies) ====================

@api_router.get("/company-apps", response_model=List[CompanyAppWithDetails])
async def list_company_apps(
    company_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_sysadmin)
):
    """List all company-app allocations (sysadmin only)"""
    query = select(CompanyApp).options(
        selectinload(CompanyApp.company),
        selectinload(CompanyApp.app)
    )
    
    if company_id:
        query = query.where(CompanyApp.company_id == company_id)
    
    result = await db.execute(query.order_by(CompanyApp.purchased_at.desc()))
    company_apps = result.scalars().all()
    
    return [
        CompanyAppWithDetails(
            id=ca.id, company_id=ca.company_id, app_id=ca.app_id,
            is_active=ca.is_active, purchased_at=ca.purchased_at, expires_at=ca.expires_at,
            company_name=ca.company.name if ca.company else None,
            app_name=ca.app.name if ca.app else None,
            app_icon=ca.app.icon if ca.app else None
        )
        for ca in company_apps
    ]

@api_router.post("/company-apps", response_model=CompanyAppResponse)
async def allocate_app_to_company(
    data: CompanyAppCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_sysadmin)
):
    """Allocate an app to a company (sysadmin only)"""
    company_result = await db.execute(select(Company).where(Company.id == data.company_id))
    if not company_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")
    
    app_result = await db.execute(select(App).where(App.id == data.app_id))
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="App not found")
    
    existing = await db.execute(
        select(CompanyApp).where(CompanyApp.company_id == data.company_id, CompanyApp.app_id == data.app_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="App is already allocated to this company")
    
    company_app = CompanyApp(company_id=data.company_id, app_id=data.app_id, expires_at=data.expires_at)
    db.add(company_app)
    await db.commit()
    await db.refresh(company_app)
    
    await log_audit_event(AuditAction.CREATE, admin.id, admin.email, "company_app", str(company_app.id), f"Allocated app to company")
    return CompanyAppResponse.model_validate(company_app)

@api_router.put("/company-apps/{allocation_id}", response_model=CompanyAppResponse)
async def update_company_app_allocation(
    allocation_id: uuid.UUID,
    data: CompanyAppUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_sysadmin)
):
    """Update a company-app allocation (sysadmin only)"""
    result = await db.execute(select(CompanyApp).where(CompanyApp.id == allocation_id))
    company_app = result.scalar_one_or_none()
    
    if not company_app:
        raise HTTPException(status_code=404, detail="Allocation not found")
    
    if data.is_active is not None:
        company_app.is_active = data.is_active
    if data.expires_at is not None:
        company_app.expires_at = data.expires_at
    
    await db.commit()
    await db.refresh(company_app)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "company_app", str(allocation_id), "Updated allocation")
    return CompanyAppResponse.model_validate(company_app)

@api_router.delete("/company-apps/{allocation_id}")
async def remove_app_from_company(
    allocation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_sysadmin)
):
    """Remove an app allocation from a company (sysadmin only)"""
    result = await db.execute(select(CompanyApp).where(CompanyApp.id == allocation_id))
    company_app = result.scalar_one_or_none()
    
    if not company_app:
        raise HTTPException(status_code=404, detail="Allocation not found")
    
    await db.delete(company_app)
    await db.commit()
    
    await log_audit_event(AuditAction.DELETE, admin.id, admin.email, "company_app", str(allocation_id), "Removed allocation")
    return {"message": "App allocation removed"}

@api_router.get("/companies/{company_id}/apps", response_model=List[AppResponse])
async def get_company_allocated_apps(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_company_admin_or_above)
):
    """Get apps allocated to a specific company"""
    if admin.role != UserRoleEnum.SYSADMIN and admin.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(
        select(App).join(CompanyApp).where(CompanyApp.company_id == company_id, CompanyApp.is_active == True, App.is_active == True)
    )
    apps = result.scalars().all()
    
    global_result = await db.execute(select(App).where(App.is_global == True, App.is_active == True))
    global_apps = global_result.scalars().all()
    
    all_apps = {app.id: app for app in apps}
    for app in global_apps:
        all_apps[app.id] = app
    
    return [AppResponse.model_validate(app) for app in all_apps.values()]

# ==================== LAUNCHPAD ENDPOINT ====================

@api_router.get("/launchpad", response_model=LaunchpadResponse)
async def get_launchpad(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get user's launchpad with accessible apps"""
    
    company_app_ids = set()
    if current_user.company_id:
        company_apps_result = await db.execute(
            select(CompanyApp.app_id).where(
                CompanyApp.company_id == current_user.company_id,
                CompanyApp.is_active == True
            )
        )
        company_app_ids = set(r[0] for r in company_apps_result.all())
    
    if current_user.role == UserRoleEnum.SYSADMIN:
        result = await db.execute(select(App).where(App.is_active == True))
        accessible_apps = result.scalars().all()
    else:
        role_assignments = await db.execute(
            select(UserRoleAssignment.role_id).where(UserRoleAssignment.user_id == current_user.id)
        )
        user_role_ids = [r[0] for r in role_assignments.all()]
        
        role_apps_result = await db.execute(
            select(RoleApp.app_id).where(RoleApp.role_id.in_(user_role_ids), RoleApp.is_default == True)
        ) if user_role_ids else None
        role_app_ids = set(r[0] for r in role_apps_result.all()) if role_apps_result else set()
        
        user_apps_result = await db.execute(
            select(UserApp.app_id, UserApp.is_enabled).where(UserApp.user_id == current_user.id)
        )
        user_app_overrides = {r[0]: r[1] for r in user_apps_result.all()}
        
        global_apps_result = await db.execute(select(App.id).where(App.is_global == True, App.is_active == True))
        global_app_ids = set(r[0] for r in global_apps_result.all())
        
        allowed_app_ids = (role_app_ids | global_app_ids | company_app_ids)
        
        for app_id, is_enabled in user_app_overrides.items():
            if is_enabled:
                allowed_app_ids.add(app_id)
            else:
                allowed_app_ids.discard(app_id)
        
        if allowed_app_ids:
            result = await db.execute(select(App).where(App.id.in_(allowed_app_ids), App.is_active == True))
            accessible_apps = result.scalars().all()
        else:
            accessible_apps = []
    
    branding = await get_user_company_branding(current_user, db)
    
    return LaunchpadResponse(
        user=UserResponse.model_validate(current_user),
        apps=[AppResponse.model_validate(app) for app in accessible_apps],
        company=branding,
        should_redirect=False,
        redirect_url=None
    )

# ==================== APPS CRUD ====================

@api_router.get("/apps", response_model=List[AppResponse])
async def list_apps(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all apps (admins only)"""
    if current_user.role not in [UserRoleEnum.SYSADMIN, UserRoleEnum.COMPANY_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.execute(select(App).order_by(App.name))
    return [AppResponse.model_validate(app) for app in result.scalars().all()]

@api_router.post("/apps", response_model=AppResponse)
async def create_app(data: AppCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Create a new app (sysadmin only)"""
    app_obj = App(**data.model_dump())
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)
    
    await log_audit_event(AuditAction.CREATE, admin.id, admin.email, "app", str(app_obj.id), f"Created app: {app_obj.name}")
    return AppResponse.model_validate(app_obj)

@api_router.get("/apps/{app_id}", response_model=AppResponse)
async def get_app(app_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get app by ID"""
    result = await db.execute(select(App).where(App.id == app_id))
    app_obj = result.scalar_one_or_none()
    if not app_obj:
        raise HTTPException(status_code=404, detail="App not found")
    return AppResponse.model_validate(app_obj)

@api_router.put("/apps/{app_id}", response_model=AppResponse)
async def update_app(app_id: uuid.UUID, data: AppUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Update an app (sysadmin only)"""
    result = await db.execute(select(App).where(App.id == app_id))
    app_obj = result.scalar_one_or_none()
    if not app_obj:
        raise HTTPException(status_code=404, detail="App not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(app_obj, field, value)
    
    await db.commit()
    await db.refresh(app_obj)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "app", str(app_id), f"Updated app: {app_obj.name}")
    return AppResponse.model_validate(app_obj)

@api_router.delete("/apps/{app_id}")
async def delete_app(app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Delete an app (sysadmin only)"""
    result = await db.execute(select(App).where(App.id == app_id))
    app_obj = result.scalar_one_or_none()
    if not app_obj:
        raise HTTPException(status_code=404, detail="App not found")
    
    app_name = app_obj.name
    await db.delete(app_obj)
    await db.commit()
    
    await log_audit_event(AuditAction.DELETE, admin.id, admin.email, "app", str(app_id), f"Deleted app: {app_name}")
    return {"message": "App deleted"}

# ==================== USERS CRUD ====================

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(
    company_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_company_admin_or_above)
):
    """List users (filtered by company for company admins)"""
    query = select(User).options(selectinload(User.company))
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        query = query.where(User.company_id == admin.company_id)
    elif company_id:
        query = query.where(User.company_id == company_id)
    
    result = await db.execute(query.order_by(User.email))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new user"""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_data = data.model_dump(exclude={'password'})
    if data.password:
        user_data['password_hash'] = hash_password(data.password)
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        user_data['company_id'] = admin.company_id
        if data.role not in [UserRoleEnum.USER, UserRoleEnum.COMPANY_ADMIN]:
            raise HTTPException(status_code=403, detail="Cannot assign this role")
    
    user = User(**user_data)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    await log_audit_event(AuditAction.CREATE, admin.id, admin.email, "user", str(user.id), f"Created user: {user.email}")
    return UserResponse.model_validate(user)

@api_router.get("/users/{user_id}", response_model=UserWithApps)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Get user with their app assignments"""
    result = await db.execute(
        select(User).options(
            selectinload(User.user_apps).selectinload(UserApp.app),
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.role)
        ).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    apps = []
    for ua in user.user_apps:
        if ua.app:
            app_data = AppResponse.model_validate(ua.app).model_dump()
            app_data['is_enabled'] = ua.is_enabled
            apps.append(app_data)
    
    roles = [RoleResponse.model_validate(ra.role) for ra in user.role_assignments if ra.role]
    
    return UserWithApps(
        **UserResponse.model_validate(user).model_dump(),
        apps=apps,
        roles=roles
    )

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        if user.company_id != admin.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        if data.role and data.role not in [UserRoleEnum.USER, UserRoleEnum.COMPANY_ADMIN]:
            raise HTTPException(status_code=403, detail="Cannot assign this role")
    
    for field, value in data.model_dump(exclude_unset=True, exclude={'password'}).items():
        setattr(user, field, value)
    
    if data.password:
        user.password_hash = hash_password(data.password)
    
    await db.commit()
    await db.refresh(user)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "user", str(user_id), f"Updated user: {user.email}")
    return UserResponse.model_validate(user)

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Delete a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user_email = user.email
    await db.delete(user)
    await db.commit()
    
    await log_audit_event(AuditAction.DELETE, admin.id, admin.email, "user", str(user_id), f"Deleted user: {user_email}")
    return {"message": "User deleted"}

# ==================== USER-APP ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/apps")
async def assign_app_to_user(user_id: uuid.UUID, data: UserAppAssignment, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Assign or update an app for a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    existing = await db.execute(select(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == data.app_id))
    user_app = existing.scalar_one_or_none()
    
    if user_app:
        user_app.is_enabled = data.is_enabled
    else:
        user_app = UserApp(user_id=user_id, app_id=data.app_id, is_enabled=data.is_enabled)
        db.add(user_app)
    
    await db.commit()
    
    await log_audit_event(AuditAction.APP_ACCESS, admin.id, admin.email, "user_app", str(user_id), f"{'Enabled' if data.is_enabled else 'Disabled'} app for user")
    return {"message": "App assignment updated"}

@api_router.delete("/users/{user_id}/apps/{app_id}")
async def remove_app_from_user(user_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Remove an app assignment from a user"""
    result = await db.execute(select(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == app_id))
    user_app = result.scalar_one_or_none()
    if not user_app:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await db.delete(user_app)
    await db.commit()
    
    await log_audit_event(AuditAction.APP_ACCESS, admin.id, admin.email, "user_app", str(user_id), "Removed app from user")
    return {"message": "App removed from user"}

# ==================== USER-ROLE ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/roles")
async def assign_role_to_user(user_id: uuid.UUID, data: UserRoleAssignmentSchema, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Assign a role to a user"""
    existing = await db.execute(select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.role_id == data.role_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role already assigned")
    
    assignment = UserRoleAssignment(user_id=user_id, role_id=data.role_id)
    db.add(assignment)
    await db.commit()
    
    await log_audit_event(AuditAction.ROLE_CHANGE, admin.id, admin.email, "user_role", str(user_id), "Assigned role to user")
    return {"message": "Role assigned"}

@api_router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(user_id: uuid.UUID, role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Remove a role from a user"""
    result = await db.execute(select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.role_id == role_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await db.delete(assignment)
    await db.commit()
    
    await log_audit_event(AuditAction.ROLE_CHANGE, admin.id, admin.email, "user_role", str(user_id), "Removed role from user")
    return {"message": "Role removed"}

# ==================== ROLES CRUD ====================

@api_router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """List all roles"""
    query = select(Role)
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        query = query.where(or_(Role.company_id == admin.company_id, Role.company_id == None))
    result = await db.execute(query.order_by(Role.name))
    return [RoleResponse.model_validate(r) for r in result.scalars().all()]

@api_router.post("/roles", response_model=RoleResponse)
async def create_role(data: RoleCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new role"""
    role_data = data.model_dump()
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        role_data['company_id'] = admin.company_id
    
    role = Role(**role_data)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    await log_audit_event(AuditAction.CREATE, admin.id, admin.email, "role", str(role.id), f"Created role: {role.name}")
    return RoleResponse.model_validate(role)

@api_router.get("/roles/{role_id}", response_model=RoleWithApps)
async def get_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Get role with its app assignments"""
    result = await db.execute(select(Role).options(selectinload(Role.role_apps).selectinload(RoleApp.app)).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    apps = [AppResponse.model_validate(ra.app) for ra in role.role_apps if ra.app]
    return RoleWithApps(**RoleResponse.model_validate(role).model_dump(), apps=apps)

@api_router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(role_id: uuid.UUID, data: RoleUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update a role"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    
    await db.commit()
    await db.refresh(role)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "role", str(role_id), f"Updated role: {role.name}")
    return RoleResponse.model_validate(role)

@api_router.delete("/roles/{role_id}")
async def delete_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Delete a role"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    role_name = role.name
    await db.delete(role)
    await db.commit()
    
    await log_audit_event(AuditAction.DELETE, admin.id, admin.email, "role", str(role_id), f"Deleted role: {role_name}")
    return {"message": "Role deleted"}

# ==================== ROLE-APP ASSIGNMENTS ====================

@api_router.post("/roles/{role_id}/apps")
async def assign_app_to_role(role_id: uuid.UUID, data: RoleAppAssignment, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Assign an app to a role"""
    existing = await db.execute(select(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == data.app_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="App already assigned to role")
    
    role_app = RoleApp(role_id=role_id, app_id=data.app_id, is_default=data.is_default)
    db.add(role_app)
    await db.commit()
    return {"message": "App assigned to role"}

@api_router.delete("/roles/{role_id}/apps/{app_id}")
async def remove_app_from_role(role_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Remove an app from a role"""
    result = await db.execute(select(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == app_id))
    role_app = result.scalar_one_or_none()
    if not role_app:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await db.delete(role_app)
    await db.commit()
    return {"message": "App removed from role"}

# ==================== EMPLOYEES CRUD ====================

@api_router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(
    search: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[EmployeeStatus] = None,
    company_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List employees with optional filters"""
    query = select(Employee).options(selectinload(Employee.company))
    
    # Filter by company for non-sysadmins
    if current_user.role != UserRoleEnum.SYSADMIN:
        if current_user.company_id:
            query = query.where(Employee.company_id == current_user.company_id)
        else:
            return []
    elif company_id:
        query = query.where(Employee.company_id == company_id)
    
    if search:
        search_filter = or_(
            Employee.first_name.ilike(f"%{search}%"),
            Employee.last_name.ilike(f"%{search}%"),
            Employee.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if department:
        query = query.where(Employee.department == department)
    if status:
        query = query.where(Employee.status == status)
    
    result = await db.execute(query.order_by(Employee.last_name, Employee.first_name))
    return [EmployeeResponse.model_validate(e) for e in result.scalars().all()]

@api_router.post("/employees", response_model=EmployeeResponse)
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new employee"""
    employee_data = data.model_dump()
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        employee_data['company_id'] = admin.company_id
    
    employee = Employee(**employee_data)
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    
    await log_audit_event(AuditAction.CREATE, admin.id, admin.email, "employee", str(employee.id), f"Created employee: {employee.email}")
    return EmployeeResponse.model_validate(employee)

@api_router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get employee by ID"""
    result = await db.execute(select(Employee).options(selectinload(Employee.company)).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if current_user.role != UserRoleEnum.SYSADMIN and employee.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return EmployeeResponse.model_validate(employee)

@api_router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(employee_id: uuid.UUID, data: EmployeeUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update an employee"""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and employee.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    
    await db.commit()
    await db.refresh(employee)
    
    await log_audit_event(AuditAction.UPDATE, admin.id, admin.email, "employee", str(employee_id), f"Updated employee: {employee.email}")
    return EmployeeResponse.model_validate(employee)

@api_router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Delete an employee"""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and employee.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    employee_email = employee.email
    await db.delete(employee)
    await db.commit()
    
    await log_audit_event(AuditAction.DELETE, admin.id, admin.email, "employee", str(employee_id), f"Deleted employee: {employee_email}")
    return {"message": "Employee deleted"}

# ==================== SETTINGS ====================

@api_router.get("/settings", response_model=List[SettingResponse])
async def list_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """List all settings (sysadmin only)"""
    result = await db.execute(select(Settings))
    return [SettingResponse.model_validate(s) for s in result.scalars().all()]

@api_router.get("/settings/bamboohr", response_model=BambooHRSettings)
async def get_bamboohr_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Get BambooHR integration settings"""
    settings = {}
    for key in ['bamboohr_api_key', 'bamboohr_subdomain', 'bamboohr_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    return BambooHRSettings(
        api_key=settings.get('bamboohr_api_key', ''),
        subdomain=settings.get('bamboohr_subdomain', ''),
        enabled=settings.get('bamboohr_enabled', 'false').lower() == 'true'
    )

@api_router.put("/settings/bamboohr")
async def update_bamboohr_settings(data: BambooHRSettings, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Update BambooHR settings"""
    settings_map = {
        'bamboohr_api_key': data.api_key,
        'bamboohr_subdomain': data.subdomain,
        'bamboohr_enabled': str(data.enabled).lower()
    }
    
    for key, value in settings_map.items():
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.add(setting)
    
    await db.commit()
    
    await log_audit_event(AuditAction.SETTINGS_CHANGE, admin.id, admin.email, "settings", "bamboohr", "Updated BambooHR settings")
    return {"message": "BambooHR settings updated"}

@api_router.post("/settings/bamboohr/sync")
async def sync_bamboohr(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Trigger BambooHR employee sync"""
    from bamboohr_service import BambooHRConfig, sync_bamboohr_employees
    
    # Get BambooHR settings
    settings = {}
    for key in ['bamboohr_api_key', 'bamboohr_subdomain', 'bamboohr_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    if settings.get('bamboohr_enabled', 'false').lower() != 'true':
        raise HTTPException(status_code=400, detail="BambooHR sync is not enabled")
    
    if not settings.get('bamboohr_api_key') or not settings.get('bamboohr_subdomain'):
        raise HTTPException(status_code=400, detail="BambooHR is not configured. Please set API key and subdomain.")
    
    # Determine company to sync to
    company_id = admin.company_id
    if not company_id:
        # For sysadmin without company, get the first company or create default
        company_result = await db.execute(select(Company).limit(1))
        company = company_result.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=400, detail="No company found. Create a company first.")
        company_id = company.id
    
    config = BambooHRConfig(
        subdomain=settings['bamboohr_subdomain'],
        api_key=settings['bamboohr_api_key']
    )
    
    result = await sync_bamboohr_employees(config, db, str(company_id))
    
    await log_audit_event(
        AuditAction.SETTINGS_CHANGE, 
        admin.id, 
        admin.email, 
        "settings", 
        "bamboohr_sync", 
        f"BambooHR sync: {result.created} created, {result.updated} updated"
    )
    
    return {
        "success": result.success,
        "message": result.message,
        "total_fetched": result.total_fetched,
        "created": result.created,
        "updated": result.updated,
        "errors": result.errors[:5] if result.errors else [],  # Return first 5 errors
        "sync_time": result.sync_time
    }

@api_router.post("/settings/bamboohr/test")
async def test_bamboohr_connection(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Test BambooHR API connection"""
    from bamboohr_service import BambooHRConfig, BambooHRService
    
    # Get BambooHR settings
    settings = {}
    for key in ['bamboohr_api_key', 'bamboohr_subdomain']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    if not settings.get('bamboohr_api_key') or not settings.get('bamboohr_subdomain'):
        return {"success": False, "message": "BambooHR is not configured. Please set API key and subdomain."}
    
    config = BambooHRConfig(
        subdomain=settings['bamboohr_subdomain'],
        api_key=settings['bamboohr_api_key']
    )
    
    service = BambooHRService(config)
    result = await service.test_connection()
    
    return result

@api_router.get("/settings/azure-sso", response_model=AzureSSOSettings)
async def get_azure_sso_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Get Azure SSO settings"""
    settings = {}
    for key in ['azure_tenant_id', 'azure_client_id', 'azure_client_secret', 'azure_sso_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    return AzureSSOSettings(
        tenant_id=settings.get('azure_tenant_id', ''),
        client_id=settings.get('azure_client_id', ''),
        client_secret='***' if settings.get('azure_client_secret') else '',
        enabled=settings.get('azure_sso_enabled', 'false').lower() == 'true'
    )

@api_router.put("/settings/azure-sso")
async def update_azure_sso_settings(data: AzureSSOSettings, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Update Azure SSO settings"""
    settings_map = {
        'azure_tenant_id': data.tenant_id,
        'azure_client_id': data.client_id,
        'azure_sso_enabled': str(data.enabled).lower()
    }
    
    if data.client_secret and data.client_secret != '***':
        settings_map['azure_client_secret'] = data.client_secret
    
    for key, value in settings_map.items():
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.add(setting)
    
    await db.commit()
    
    await log_audit_event(AuditAction.SETTINGS_CHANGE, admin.id, admin.email, "settings", "azure_sso", "Updated Azure SSO settings")
    return {"message": "Azure SSO settings updated"}

# ==================== HEALTH & ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "Identity & Employee Hub API", "version": "3.2.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# CORS Configuration
cors_origins = os.environ.get('CORS_ORIGINS', '')
if cors_origins == '*':
    logger.warning("CORS_ORIGINS is set to '*' - this is insecure for production!")

allowed_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins if allowed_origins else ["http://localhost:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Bootstrap admin credentials
BOOTSTRAP_ADMIN_EMAIL = "admin@bootstrap.hub"
BOOTSTRAP_ADMIN_PASSWORD = "ChangeMeNow!"

# Database initialization
async def init_db_with_alembic():
    """Initialize database using Alembic migrations"""
    import subprocess
    import shutil
    
    alembic_path = shutil.which("alembic") or "/root/.venv/bin/alembic"
    
    try:
        # First check current revision
        check_result = subprocess.run(
            [alembic_path, "current"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=15
        )
        current_rev = check_result.stdout.strip() if check_result.returncode == 0 else "unknown"
        logger.info(f"Current Alembic revision: {current_rev}")
        
        # Run upgrade
        result = subprocess.run(
            [alembic_path, "upgrade", "head"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            logger.info(f"Database migrations applied successfully")
            if result.stdout:
                logger.info(f"Alembic output: {result.stdout.strip()}")
        else:
            logger.warning(f"Alembic migration failed: {result.stderr}")
            # Fallback to create_all only if Alembic truly failed
            logger.info("Falling back to metadata.create_all()...")
            from database import Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Fallback: Tables created with metadata.create_all")
            
    except subprocess.TimeoutExpired:
        logger.error("Alembic migration timed out")
        from database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Fallback: Tables created with metadata.create_all")
    except FileNotFoundError:
        logger.error(f"Alembic not found at {alembic_path}")
        from database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Fallback: Tables created with metadata.create_all")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        from database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Fallback: Tables created with metadata.create_all")

@app.on_event("startup")
async def startup():
    logger.info("Starting Identity & Employee Hub v3.1.0...")
    
    await init_db_with_alembic()
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.role == UserRoleEnum.SYSADMIN))
        existing_admin = result.scalar_one_or_none()
        
        if not existing_admin:
            logger.info(f"Creating bootstrap sysadmin: {BOOTSTRAP_ADMIN_EMAIL}")
            admin_user = User(
                email=BOOTSTRAP_ADMIN_EMAIL,
                password_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
                first_name='Admin',
                last_name='User',
                role=UserRoleEnum.SYSADMIN,
                status=UserStatus.ACTIVE,
                auth_method=AuthMethod.PASSWORD,
                must_change_password=True,
                must_change_email=True
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Bootstrap sysadmin created: {BOOTSTRAP_ADMIN_EMAIL}")
            logger.info("*** IMPORTANT: Admin must change BOTH email and password on first login ***")
        else:
            logger.info(f"Existing sysadmin found: {existing_admin.email}")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down...")
