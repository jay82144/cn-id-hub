from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_, and_
from sqlalchemy.orm import selectinload
import os
import logging
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid

from database import get_db, init_db, engine, async_session_maker
from models import (
    User, Role, App, RoleApp, UserApp, UserRoleAssignment, Employee, Settings, CompanySettings, Company,
    UserRole as UserRoleEnum, UserStatus, EmployeeStatus, AuthMethod
)
from schemas import (
    LoginRequest, MagicLinkRequest, MagicLinkVerify, TokenResponse, ChangePasswordRequest,
    UserCreate, UserUpdate, UserResponse, UserWithApps,
    RoleCreate, RoleUpdate, RoleResponse, RoleWithApps,
    AppCreate, AppUpdate, AppResponse,
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    SettingUpdate, SettingResponse, BambooHRSettings, AzureSSOSettings,
    RoleAppAssignment, UserAppAssignment, UserRoleAssignmentSchema,
    LaunchpadResponse, CompanyCreate, CompanyUpdate, CompanyResponse, CompanyBranding
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_admin_user, generate_magic_link_token,
    verify_token_external, MAGIC_LINK_EXPIRATION_MINUTES
)

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging to stdout/stderr for Docker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Identity & Employee Hub API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# ==================== MIDDLEWARE ====================

# CORS
cors_origins = os.environ.get('CORS_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Trusted hosts (optional)
trusted_hosts = os.environ.get('TRUSTED_HOSTS', '*')
if trusted_hosts != '*':
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in trusted_hosts.split(',')]
    )

# ==================== HELPER FUNCTIONS ====================

def get_company_filter(user: User, model):
    """Get appropriate company filter based on user role"""
    if user.role == UserRoleEnum.SYSADMIN:
        return True
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

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.auth_method == AuthMethod.AZURE_SSO:
        raise HTTPException(status_code=401, detail="This account uses Microsoft SSO. Please use 'Continue with Microsoft' to sign in.")
    
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    token = create_access_token(str(user.id), user.email, user.role.value)
    branding = await get_user_company_branding(user, db)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        must_change_password=user.must_change_password,
        company=branding
    )

@api_router.post("/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change password"""
    if not current_user.must_change_password and request.current_password:
        if not verify_password(request.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    current_user.password_hash = hash_password(request.new_password)
    current_user.must_change_password = False
    await db.commit()
    
    return {"message": "Password changed successfully"}

@api_router.post("/auth/magic-link")
async def request_magic_link(request: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    """Request a magic link for passwordless login"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or user.auth_method == AuthMethod.AZURE_SSO:
        return {"message": "If the email exists, a magic link has been sent"}
    
    token = generate_magic_link_token()
    user.magic_link_token = token
    user.magic_link_expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRATION_MINUTES)
    await db.commit()
    
    logger.info(f"Magic link token generated for {request.email}")
    
    return {"message": "If the email exists, a magic link has been sent", "debug_token": token}

@api_router.post("/auth/magic-link/verify", response_model=TokenResponse)
async def verify_magic_link(request: MagicLinkVerify, db: AsyncSession = Depends(get_db)):
    """Verify magic link and login"""
    result = await db.execute(
        select(User).where(
            User.magic_link_token == request.token,
            User.magic_link_expires > datetime.now(timezone.utc)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")
    
    user.magic_link_token = None
    user.magic_link_expires = None
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    token = create_access_token(str(user.id), user.email, user.role.value)
    branding = await get_user_company_branding(user, db)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        must_change_password=user.must_change_password,
        company=branding
    )

@api_router.get("/auth/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token - for downstream apps"""
    if not credentials:
        return {"valid": False, "error": "No token provided"}
    return verify_token_external(credentials.credentials)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse.model_validate(current_user)

# ==================== AZURE SSO ENDPOINTS ====================

_azure_auth_flows = {}

@api_router.get("/auth/azure/config")
async def get_azure_sso_config(db: AsyncSession = Depends(get_db)):
    """Check if Azure SSO is configured and enabled"""
    settings = {}
    for key in ['azure_tenant_id', 'azure_client_id', 'azure_sso_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    is_enabled = settings.get('azure_sso_enabled', 'false').lower() == 'true'
    is_configured = bool(settings.get('azure_tenant_id')) and bool(settings.get('azure_client_id'))
    
    return {"enabled": is_enabled, "configured": is_configured}

@api_router.get("/auth/azure/login")
async def azure_sso_login(db: AsyncSession = Depends(get_db)):
    """Initiate Azure AD SSO login flow"""
    from msal import ConfidentialClientApplication
    
    settings = {}
    for key in ['azure_tenant_id', 'azure_client_id', 'azure_client_secret', 'azure_sso_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    if settings.get('azure_sso_enabled', 'false').lower() != 'true':
        raise HTTPException(status_code=400, detail="Azure SSO is not enabled")
    
    tenant_id = settings.get('azure_tenant_id')
    client_id = settings.get('azure_client_id')
    client_secret = settings.get('azure_client_secret')
    
    if not all([tenant_id, client_id, client_secret]):
        raise HTTPException(status_code=400, detail="Azure SSO is not fully configured")
    
    backend_url = os.environ.get('BACKEND_URL', '').rstrip('/')
    redirect_uri = f"{backend_url}/api/auth/azure/callback"
    
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        msal_app = ConfidentialClientApplication(client_id=client_id, authority=authority, client_credential=client_secret)
        
        flow = msal_app.initiate_auth_code_flow(
            scopes=["https://graph.microsoft.com/User.Read"],
            redirect_uri=redirect_uri,
        )
        
        if "error" in flow:
            raise HTTPException(status_code=500, detail=f"Failed to initiate SSO: {flow.get('error_description', 'Unknown error')}")
        
        state = flow.get("state")
        _azure_auth_flows[state] = {
            "flow": flow, "tenant_id": tenant_id, "client_id": client_id,
            "client_secret": client_secret, "redirect_uri": redirect_uri,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {"auth_url": flow["auth_uri"], "state": state}
    except Exception as e:
        logger.error(f"Error initiating Azure SSO: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate Azure SSO: {str(e)}")

@api_router.get("/auth/azure/callback")
async def azure_sso_callback(
    code: str = None, state: str = None, error: str = None, error_description: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Azure AD SSO callback"""
    from msal import ConfidentialClientApplication
    from fastapi.responses import RedirectResponse
    import requests
    
    # Get frontend URL from CORS origins (first one)
    cors_origins = os.environ.get('CORS_ORIGINS', '').split(',')
    frontend_url = cors_origins[0].strip() if cors_origins else ''
    
    if error:
        return RedirectResponse(url=f"{frontend_url}/login?error={error_description or error}")
    
    if not code or not state:
        return RedirectResponse(url=f"{frontend_url}/login?error=Missing authorization code or state")
    
    flow_data = _azure_auth_flows.pop(state, None)
    if not flow_data:
        return RedirectResponse(url=f"{frontend_url}/login?error=Invalid or expired SSO session")
    
    try:
        authority = f"https://login.microsoftonline.com/{flow_data['tenant_id']}"
        msal_app = ConfidentialClientApplication(
            client_id=flow_data['client_id'], authority=authority, client_credential=flow_data['client_secret']
        )
        
        result = msal_app.acquire_token_by_auth_code_flow(flow_data['flow'], {"code": code, "state": state})
        
        if "error" in result:
            return RedirectResponse(url=f"{frontend_url}/login?error={result.get('error_description', 'Token acquisition failed')}")
        
        if "access_token" not in result:
            return RedirectResponse(url=f"{frontend_url}/login?error=No access token received")
        
        graph_response = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {result['access_token']}"}, timeout=10
        )
        
        if graph_response.status_code != 200:
            return RedirectResponse(url=f"{frontend_url}/login?error=Failed to get user info from Microsoft")
        
        user_info = graph_response.json()
        email = user_info.get("mail") or user_info.get("userPrincipalName", "").lower()
        azure_id = user_info.get("id")
        first_name = user_info.get("givenName", "")
        last_name = user_info.get("surname", "")
        
        if not email:
            return RedirectResponse(url=f"{frontend_url}/login?error=No email found in Azure profile")
        
        user_result = await db.execute(select(User).where(User.azure_id == azure_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            email_result = await db.execute(select(User).where(User.email == email))
            user = email_result.scalar_one_or_none()
            
            if user:
                user.azure_id = azure_id
                user.auth_method = AuthMethod.AZURE_SSO
                if not user.first_name:
                    user.first_name = first_name
                if not user.last_name:
                    user.last_name = last_name
            else:
                user = User(
                    email=email, azure_id=azure_id, first_name=first_name, last_name=last_name,
                    role=UserRoleEnum.USER, status=UserStatus.ACTIVE, auth_method=AuthMethod.AZURE_SSO
                )
                db.add(user)
        
        user.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        
        token = create_access_token(str(user.id), user.email, user.role.value)
        return RedirectResponse(url=f"{frontend_url}/login?token={token}")
        
    except Exception as e:
        logger.error(f"Azure SSO callback error: {str(e)}")
        return RedirectResponse(url=f"{frontend_url}/login?error=SSO authentication failed")

# ==================== COMPANIES ====================

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
    return CompanyResponse.model_validate(company)

@api_router.delete("/companies/{company_id}")
async def delete_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Delete a company (sysadmin only)"""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    await db.delete(company)
    await db.commit()
    return {"message": "Company deleted"}

@api_router.get("/companies/{company_id}/branding", response_model=CompanyBranding)
async def get_company_branding(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get company branding (public endpoint)"""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyBranding(name=company.name, logo_url=company.logo_url, primary_color=company.primary_color, secondary_color=company.secondary_color)

# ==================== LAUNCHPAD ====================

@api_router.get("/launchpad", response_model=LaunchpadResponse)
async def get_launchpad(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get user's launchpad with accessible apps"""
    role_result = await db.execute(
        select(UserRoleAssignment)
        .options(selectinload(UserRoleAssignment.role).selectinload(Role.role_apps).selectinload(RoleApp.app))
        .where(UserRoleAssignment.user_id == current_user.id)
    )
    user_role_assignments = role_result.scalars().all()
    
    role_apps = {}
    for ura in user_role_assignments:
        for ra in ura.role.role_apps:
            if ra.app.is_active and (ra.app.is_global or ra.app.company_id == current_user.company_id):
                role_apps[ra.app.id] = ra.app
    
    user_app_result = await db.execute(
        select(UserApp).options(selectinload(UserApp.app)).where(UserApp.user_id == current_user.id)
    )
    user_apps = user_app_result.scalars().all()
    
    final_apps = dict(role_apps)
    for ua in user_apps:
        if ua.is_granted and ua.app.is_active and (ua.app.is_global or ua.app.company_id == current_user.company_id):
            final_apps[ua.app.id] = ua.app
        elif not ua.is_granted and ua.app.id in final_apps:
            del final_apps[ua.app.id]
    
    apps_list = [AppResponse.model_validate(app) for app in final_apps.values()]
    
    if current_user.role in [UserRoleEnum.SYSADMIN, UserRoleEnum.COMPANY_ADMIN]:
        if current_user.role == UserRoleEnum.SYSADMIN:
            all_apps_result = await db.execute(select(App).where(App.is_active == True))
        else:
            all_apps_result = await db.execute(
                select(App).where(App.is_active == True, or_(App.is_global == True, App.company_id == current_user.company_id))
            )
        all_apps = all_apps_result.scalars().all()
        apps_list = [AppResponse.model_validate(app) for app in all_apps]
    
    should_redirect = len(apps_list) == 1
    redirect_url = apps_list[0].url if should_redirect else None
    branding = await get_user_company_branding(current_user, db)
    
    return LaunchpadResponse(
        user=UserResponse.model_validate(current_user),
        apps=apps_list, should_redirect=should_redirect, redirect_url=redirect_url, company=branding
    )

# ==================== APPS CRUD ====================

@api_router.get("/apps", response_model=List[AppResponse])
async def list_apps(include_inactive: bool = False, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List apps (filtered by company)"""
    query = select(App)
    
    if current_user.role == UserRoleEnum.SYSADMIN:
        if not include_inactive:
            query = query.where(App.is_active == True)
    else:
        query = query.where(or_(App.is_global == True, App.company_id == current_user.company_id))
        if not include_inactive:
            query = query.where(App.is_active == True)
    
    result = await db.execute(query.order_by(App.name))
    return [AppResponse.model_validate(app) for app in result.scalars().all()]

@api_router.post("/apps", response_model=AppResponse)
async def create_app(app_data: AppCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new app"""
    data = app_data.model_dump()
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        data['company_id'] = admin.company_id
        data['is_global'] = False
    
    app = App(**data)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return AppResponse.model_validate(app)

@api_router.get("/apps/{app_id}", response_model=AppResponse)
async def get_app(app_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get app by ID"""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    if current_user.role != UserRoleEnum.SYSADMIN:
        if not app.is_global and app.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return AppResponse.model_validate(app)

@api_router.put("/apps/{app_id}", response_model=AppResponse)
async def update_app(app_id: uuid.UUID, app_data: AppUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update an app"""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and app.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    for field, value in app_data.model_dump(exclude_unset=True).items():
        if admin.role == UserRoleEnum.COMPANY_ADMIN and field == 'is_global':
            continue
        setattr(app, field, value)
    
    await db.commit()
    await db.refresh(app)
    return AppResponse.model_validate(app)

@api_router.delete("/apps/{app_id}")
async def delete_app(app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Delete an app"""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and app.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await db.delete(app)
    await db.commit()
    return {"message": "App deleted"}

# ==================== USERS CRUD ====================

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """List users (filtered by company for company_admin)"""
    if admin.role == UserRoleEnum.SYSADMIN:
        result = await db.execute(select(User).order_by(User.email))
    else:
        result = await db.execute(select(User).where(User.company_id == admin.company_id).order_by(User.email))
    return [UserResponse.model_validate(user) for user in result.scalars().all()]

@api_router.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new user"""
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user_data.model_dump()
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        user_dict['company_id'] = admin.company_id
        if user_dict.get('role') == UserRoleEnum.SYSADMIN:
            raise HTTPException(status_code=403, detail="Cannot create sysadmin users")
    
    if user_dict.get('password'):
        user_dict['password_hash'] = hash_password(user_dict.pop('password'))
    else:
        user_dict.pop('password', None)
    
    user = User(**user_dict)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

@api_router.get("/users/{user_id}", response_model=UserWithApps)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Get user by ID with apps and roles"""
    result = await db.execute(
        select(User).options(
            selectinload(User.user_apps).selectinload(UserApp.app),
            selectinload(User.user_roles).selectinload(UserRoleAssignment.role),
            selectinload(User.company)
        ).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    role_result = await db.execute(
        select(UserRoleAssignment)
        .options(selectinload(UserRoleAssignment.role).selectinload(Role.role_apps).selectinload(RoleApp.app))
        .where(UserRoleAssignment.user_id == user_id)
    )
    user_role_assignments = role_result.scalars().all()
    
    apps_dict = {}
    for ura in user_role_assignments:
        for ra in ura.role.role_apps:
            apps_dict[ra.app.id] = ra.app
    
    for ua in user.user_apps:
        if ua.is_granted:
            apps_dict[ua.app.id] = ua.app
        elif ua.app.id in apps_dict:
            del apps_dict[ua.app.id]
    
    roles = [RoleResponse.model_validate(ura.role) for ura in user_role_assignments]
    apps = [AppResponse.model_validate(app) for app in apps_dict.values()]
    
    user_response = UserWithApps.model_validate(user)
    user_response.apps = apps
    user_response.roles = roles
    if user.company:
        user_response.company = CompanyResponse.model_validate(user.company)
    return user_response

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: uuid.UUID, user_data: UserUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if admin.role == UserRoleEnum.COMPANY_ADMIN and user_data.role == UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Cannot assign sysadmin role")
    
    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Delete a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted"}

# ==================== USER-APP/ROLE ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/apps")
async def assign_app_to_user(user_id: uuid.UUID, app_id: uuid.UUID, is_granted: bool = True, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    existing = await db.execute(select(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == app_id))
    user_app = existing.scalar_one_or_none()
    if user_app:
        user_app.is_granted = is_granted
    else:
        user_app = UserApp(user_id=user_id, app_id=app_id, is_granted=is_granted)
        db.add(user_app)
    await db.commit()
    return {"message": "App assignment updated"}

@api_router.delete("/users/{user_id}/apps/{app_id}")
async def remove_app_from_user(user_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.execute(delete(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == app_id))
    await db.commit()
    return {"message": "App assignment removed"}

@api_router.post("/users/{user_id}/roles")
async def assign_role_to_user(user_id: uuid.UUID, role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    existing = await db.execute(select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.role_id == role_id))
    if existing.scalar_one_or_none():
        return {"message": "Role already assigned"}
    
    assignment = UserRoleAssignment(user_id=user_id, role_id=role_id)
    db.add(assignment)
    await db.commit()
    return {"message": "Role assigned"}

@api_router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(user_id: uuid.UUID, role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.role_id == role_id))
    await db.commit()
    return {"message": "Role removed"}

# ==================== ROLES CRUD ====================

@api_router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRoleEnum.SYSADMIN:
        result = await db.execute(select(Role).order_by(Role.name))
    else:
        result = await db.execute(select(Role).where(or_(Role.company_id == None, Role.company_id == current_user.company_id)).order_by(Role.name))
    return [RoleResponse.model_validate(role) for role in result.scalars().all()]

@api_router.post("/roles", response_model=RoleResponse)
async def create_role(role_data: RoleCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    data = role_data.model_dump()
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        data['company_id'] = admin.company_id
    role = Role(**data)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)

@api_router.get("/roles/{role_id}", response_model=RoleWithApps)
async def get_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Role).options(selectinload(Role.role_apps).selectinload(RoleApp.app)).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    apps = [AppResponse.model_validate(ra.app) for ra in role.role_apps]
    role_response = RoleWithApps.model_validate(role)
    role_response.apps = apps
    return role_response

@api_router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(role_id: uuid.UUID, role_data: RoleUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if admin.role != UserRoleEnum.SYSADMIN and role.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    for field, value in role_data.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)

@api_router.delete("/roles/{role_id}")
async def delete_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if admin.role != UserRoleEnum.SYSADMIN and role.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.delete(role)
    await db.commit()
    return {"message": "Role deleted"}

@api_router.post("/roles/{role_id}/apps")
async def assign_app_to_role(role_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if admin.role != UserRoleEnum.SYSADMIN and role.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    existing = await db.execute(select(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == app_id))
    if existing.scalar_one_or_none():
        return {"message": "App already assigned"}
    
    role_app = RoleApp(role_id=role_id, app_id=app_id)
    db.add(role_app)
    await db.commit()
    return {"message": "App assigned to role"}

@api_router.delete("/roles/{role_id}/apps/{app_id}")
async def remove_app_from_role(role_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if admin.role != UserRoleEnum.SYSADMIN and role.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.execute(delete(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == app_id))
    await db.commit()
    return {"message": "App removed from role"}

# ==================== EMPLOYEES CRUD ====================

@api_router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(status: Optional[EmployeeStatus] = None, department: Optional[str] = None, search: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(Employee)
    if current_user.role != UserRoleEnum.SYSADMIN:
        query = query.where(Employee.company_id == current_user.company_id)
    if status:
        query = query.where(Employee.status == status)
    if department:
        query = query.where(Employee.department == department)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Employee.first_name.ilike(pattern), Employee.last_name.ilike(pattern), Employee.email.ilike(pattern)))
    result = await db.execute(query.order_by(Employee.last_name, Employee.first_name))
    return [EmployeeResponse.model_validate(emp) for emp in result.scalars().all()]

@api_router.post("/employees", response_model=EmployeeResponse)
async def create_employee(emp_data: EmployeeCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    data = emp_data.model_dump()
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        data['company_id'] = admin.company_id
    elif not data.get('company_id'):
        raise HTTPException(status_code=400, detail="company_id is required")
    employee = Employee(**data)
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)

@api_router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if current_user.role != UserRoleEnum.SYSADMIN and employee.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return EmployeeResponse.model_validate(employee)

@api_router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(employee_id: uuid.UUID, emp_data: EmployeeUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if admin.role != UserRoleEnum.SYSADMIN and employee.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    for field, value in emp_data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    await db.commit()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)

@api_router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if admin.role != UserRoleEnum.SYSADMIN and employee.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.delete(employee)
    await db.commit()
    return {"message": "Employee deleted"}

# ==================== SETTINGS ====================

@api_router.get("/settings", response_model=List[SettingResponse])
async def list_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    result = await db.execute(select(Settings).order_by(Settings.key))
    return [SettingResponse.model_validate(s) for s in result.scalars().all()]

@api_router.get("/settings/bamboohr", response_model=BambooHRSettings)
async def get_bamboohr_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    settings = {}
    for key in ['bamboohr_api_key', 'bamboohr_company_domain', 'bamboohr_sync_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    return BambooHRSettings(
        api_key=settings.get('bamboohr_api_key'),
        company_domain=settings.get('bamboohr_company_domain'),
        sync_enabled=settings.get('bamboohr_sync_enabled', 'false').lower() == 'true'
    )

@api_router.put("/settings/bamboohr")
async def update_bamboohr_settings(bamboo_settings: BambooHRSettings, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    settings_map = {
        'bamboohr_api_key': bamboo_settings.api_key,
        'bamboohr_company_domain': bamboo_settings.company_domain,
        'bamboohr_sync_enabled': str(bamboo_settings.sync_enabled).lower()
    }
    for key, value in settings_map.items():
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(Settings(key=key, value=value))
    await db.commit()
    return {"message": "BambooHR settings updated"}

@api_router.post("/settings/bamboohr/sync")
async def sync_bamboohr(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    api_key_result = await db.execute(select(Settings).where(Settings.key == 'bamboohr_api_key'))
    if not (api_key_result.scalar_one_or_none() and api_key_result.scalar_one_or_none().value):
        raise HTTPException(status_code=400, detail="BambooHR API key not configured")
    logger.info("BambooHR sync triggered (placeholder)")
    return {"message": "Sync triggered (mock)", "synced_at": datetime.now(timezone.utc).isoformat()}

@api_router.get("/settings/azure-sso", response_model=AzureSSOSettings)
async def get_azure_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    settings = {}
    for key in ['azure_tenant_id', 'azure_client_id', 'azure_client_secret', 'azure_sso_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    return AzureSSOSettings(
        tenant_id=settings.get('azure_tenant_id'),
        client_id=settings.get('azure_client_id'),
        client_secret=settings.get('azure_client_secret'),
        enabled=settings.get('azure_sso_enabled', 'false').lower() == 'true'
    )

@api_router.put("/settings/azure-sso")
async def update_azure_settings(azure_settings: AzureSSOSettings, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    settings_map = {
        'azure_tenant_id': azure_settings.tenant_id,
        'azure_client_id': azure_settings.client_id,
        'azure_client_secret': azure_settings.client_secret,
        'azure_sso_enabled': str(azure_settings.enabled).lower()
    }
    for key, value in settings_map.items():
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(Settings(key=key, value=value))
    await db.commit()
    return {"message": "Azure SSO settings updated"}

# ==================== HEALTH & ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "Identity & Employee Hub API", "version": "2.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup():
    logger.info("Starting Identity & Employee Hub...")
    await init_db()
    
    # Create default admin from environment variables
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'ChangeMeOnFirstLogin!')
    admin_first_name = os.environ.get('ADMIN_FIRST_NAME', 'Admin')
    admin_last_name = os.environ.get('ADMIN_LAST_NAME', 'User')
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == admin_email))
        admin_exists = result.scalar_one_or_none()
        
        if not admin_exists:
            logger.info(f"Creating seed sysadmin user: {admin_email}")
            admin_user = User(
                email=admin_email,
                password_hash=hash_password(admin_password),
                first_name=admin_first_name,
                last_name=admin_last_name,
                role=UserRoleEnum.SYSADMIN,
                status=UserStatus.ACTIVE,
                auth_method=AuthMethod.PASSWORD,
                must_change_password=True
            )
            session.add(admin_user)
            await session.commit()
            logger.info("Sysadmin user created (password change required on first login)")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down...")
