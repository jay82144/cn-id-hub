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
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import uuid
import json

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

app = FastAPI(title="Identity & Employee Hub API", version="3.0.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

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

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password. Sets refresh token as HttpOnly cookie."""
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check if user can use password login
    if user.auth_method == AuthMethod.AZURE_SSO:
        raise HTTPException(status_code=401, detail="This account uses Microsoft SSO. Please use 'Continue with Microsoft' to sign in.")
    
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    # Create access token (15 min)
    access_token = create_access_token(user)
    
    # Create and store refresh token (30 days), set as HttpOnly cookie
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    refresh_token = await create_and_store_refresh_token(db, user, device_info, ip_address)
    set_refresh_token_cookie(response, refresh_token)
    
    branding = await get_user_company_branding(user, db)
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
        must_change_password=user.must_change_password,
        must_change_email=user.must_change_email,
        company=branding
    )


@api_router.post("/auth/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token from HttpOnly cookie."""
    # Get refresh token from cookie
    refresh_token_value = request.cookies.get("refresh_token")
    
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    # Validate refresh token
    token_record = await validate_refresh_token(db, refresh_token_value)
    
    if not token_record:
        clear_refresh_token_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Get user
    result = await db.execute(select(User).where(User.id == token_record.user_id))
    user = result.scalar_one_or_none()
    
    if not user or user.status != UserStatus.ACTIVE:
        clear_refresh_token_cookie(response)
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    # Token rotation: revoke old token and create new one
    await revoke_refresh_token(db, refresh_token_value)
    
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    new_refresh_token = await create_and_store_refresh_token(db, user, device_info, ip_address)
    set_refresh_token_cookie(response, new_refresh_token)
    
    # Create new access token
    access_token = create_access_token(user)
    
    return RefreshTokenResponse(access_token=access_token)


@api_router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Logout - revokes refresh token and clears cookie."""
    refresh_token_value = request.cookies.get("refresh_token")
    
    if refresh_token_value:
        await revoke_refresh_token(db, refresh_token_value)
    
    clear_refresh_token_cookie(response)
    return {"message": "Logged out successfully"}

@api_router.post("/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change password (required on first login for bootstrap admin)"""
    # If forced change, current_password is optional
    if not current_user.must_change_password and request.current_password:
        if not verify_password(request.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    current_user.password_hash = hash_password(request.new_password)
    current_user.must_change_password = False
    
    # Revoke all existing refresh tokens (security: password changed)
    await revoke_all_user_refresh_tokens(db, current_user.id)
    
    await db.commit()
    
    return {"message": "Password changed successfully"}


@api_router.post("/auth/change-credentials", response_model=TokenResponse)
async def change_credentials(
    request_data: ChangeCredentialsRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change both email and password (required for bootstrap admin on first login).
    This endpoint is used when both must_change_email and must_change_password are true.
    """
    if not current_user.must_change_email and not current_user.must_change_password:
        raise HTTPException(status_code=400, detail="Credential change not required")
    
    # Check if new email is already taken
    if request_data.new_email != current_user.email:
        existing = await db.execute(select(User).where(User.email == request_data.new_email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # Update credentials
    current_user.email = request_data.new_email
    current_user.password_hash = hash_password(request_data.new_password)
    current_user.must_change_email = False
    current_user.must_change_password = False
    
    # Revoke all existing refresh tokens
    await revoke_all_user_refresh_tokens(db, current_user.id)
    
    await db.commit()
    await db.refresh(current_user)
    
    # Issue new tokens with updated credentials
    access_token = create_access_token(current_user)
    
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    refresh_token = await create_and_store_refresh_token(db, current_user, device_info, ip_address)
    set_refresh_token_cookie(response, refresh_token)
    
    branding = await get_user_company_branding(current_user, db)
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(current_user),
        must_change_password=False,
        must_change_email=False,
        company=branding
    )

@api_router.post("/auth/magic-link")
async def request_magic_link(request: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    """Request a magic link for passwordless login"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"message": "If the email exists, a magic link has been sent"}
    
    # Check if user can use magic link (not SSO-only)
    if user.auth_method == AuthMethod.AZURE_SSO:
        return {"message": "If the email exists, a magic link has been sent"}
    
    token = generate_magic_link_token()
    user.magic_link_token = token
    user.magic_link_expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRATION_MINUTES)
    await db.commit()
    
    logger.info(f"Magic link token for {request.email}: {token}")
    
    return {"message": "If the email exists, a magic link has been sent", "debug_token": token}

@api_router.post("/auth/magic-link/verify", response_model=TokenResponse)
async def verify_magic_link(
    magic_link: MagicLinkVerify,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Verify magic link and login"""
    result = await db.execute(
        select(User).where(
            User.magic_link_token == magic_link.token,
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
    
    # Create tokens
    access_token = create_access_token(user)
    
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    refresh_token = await create_and_store_refresh_token(db, user, device_info, ip_address)
    set_refresh_token_cookie(response, refresh_token)
    
    branding = await get_user_company_branding(user, db)
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
        must_change_password=user.must_change_password,
        must_change_email=user.must_change_email,
        company=branding
    )

@api_router.get("/auth/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token - for downstream apps"""
    if not credentials:
        return {"valid": False, "error": "No token provided"}
    return verify_token_external(credentials.credentials)

# ==================== AZURE SSO ENDPOINTS ====================

_azure_auth_flows = {}

@api_router.get("/auth/azure/config")
async def get_azure_sso_config(db: AsyncSession = Depends(get_db)):
    """Check if Azure SSO is configured and enabled (global or any company)"""
    # Check global settings first
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
    
    backend_url = os.environ.get('BACKEND_URL', 'https://employee-hub-283.preview.emergentagent.com')
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
    
    backend_url = os.environ.get('BACKEND_URL', 'https://employee-hub-283.preview.emergentagent.com')
    frontend_url = backend_url
    
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
        
        # Find or create user
        user_result = await db.execute(select(User).where(User.azure_id == azure_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            email_result = await db.execute(select(User).where(User.email == email))
            user = email_result.scalar_one_or_none()
            
            if user:
                user.azure_id = azure_id
                user.auth_method = AuthMethod.AZURE_SSO  # Lock to SSO
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
        
        token = create_access_token(user)
        return RedirectResponse(url=f"{frontend_url}/login?token={token}")
        
    except Exception as e:
        logger.error(f"Azure SSO callback error: {str(e)}")
        return RedirectResponse(url=f"{frontend_url}/login?error=SSO authentication failed")

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse.model_validate(current_user)


# ==================== API KEY ENDPOINTS ====================

@api_router.get("/api-keys", response_model=List[APIKeyResponse])
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


@api_router.post("/api-keys", response_model=APIKeyCreatedResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key. The full key is only returned once."""
    # Generate the key
    full_key, prefix = generate_api_key()
    key_hash = hash_token(full_key)
    
    # Calculate expiration if specified
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=key_data.expires_in_days)
    
    # Convert allowed_apps to JSON if provided
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
    
    # Build response manually to include the full key (only shown once)
    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scope=api_key.scope,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        api_key=full_key  # Only returned on creation
    )


@api_router.delete("/api-keys/{key_id}")
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


# ==================== IDENTITY CONTEXT ENDPOINTS (for downstream apps) ====================

@api_router.get("/identity/context", response_model=TokenVerifyResponse)
async def get_identity_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full identity context from a token or API key.
    Used by downstream apps to get user/company info.
    """
    if not credentials:
        # Check for API key
        return {"valid": False, "error": "No authentication provided"}
    
    return verify_token_external(credentials.credentials)


@api_router.get("/identity/user/{user_id}", response_model=UserResponse)
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
    
    # Check access permissions
    if current_user.role != UserRoleEnum.SYSADMIN:
        if user.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return UserResponse.model_validate(user)


@api_router.get("/identity/company/{company_id}", response_model=CompanyResponse)
async def get_company_by_id_for_apps(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get company info by ID (for downstream apps with valid token/API key).
    """
    # Check access permissions
    if current_user.role != UserRoleEnum.SYSADMIN:
        if current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return CompanyResponse.model_validate(company)

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
    
    # Company admins can only update branding, not active status
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
            id=ca.id,
            company_id=ca.company_id,
            app_id=ca.app_id,
            is_active=ca.is_active,
            purchased_at=ca.purchased_at,
            expires_at=ca.expires_at,
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
    # Verify company exists
    company_result = await db.execute(select(Company).where(Company.id == data.company_id))
    if not company_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Verify app exists
    app_result = await db.execute(select(App).where(App.id == data.app_id))
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="App not found")
    
    # Check if allocation already exists
    existing = await db.execute(
        select(CompanyApp).where(
            CompanyApp.company_id == data.company_id,
            CompanyApp.app_id == data.app_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="App is already allocated to this company")
    
    company_app = CompanyApp(
        company_id=data.company_id,
        app_id=data.app_id,
        expires_at=data.expires_at
    )
    db.add(company_app)
    await db.commit()
    await db.refresh(company_app)
    
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
    return {"message": "App allocation removed"}


@api_router.get("/companies/{company_id}/apps", response_model=List[AppResponse])
async def get_company_allocated_apps(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_company_admin_or_above)
):
    """Get apps allocated to a specific company"""
    # Check access
    if admin.role != UserRoleEnum.SYSADMIN and admin.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.execute(
        select(App).join(CompanyApp).where(
            CompanyApp.company_id == company_id,
            CompanyApp.is_active == True,
            App.is_active == True
        )
    )
    apps = result.scalars().all()
    
    # Also include global apps
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
    
    # Get apps allocated to user's company (or global apps)
    company_app_ids = set()
    if current_user.company_id:
        ca_result = await db.execute(
            select(CompanyApp.app_id).where(
                CompanyApp.company_id == current_user.company_id,
                CompanyApp.is_active == True
            )
        )
        company_app_ids = {row[0] for row in ca_result.fetchall()}
    
    # Helper to check if app is accessible to company
    def is_app_accessible(app):
        if app.is_global:
            return True
        return app.id in company_app_ids
    
    # Get user's role assignments
    role_result = await db.execute(
        select(UserRoleAssignment)
        .options(selectinload(UserRoleAssignment.role).selectinload(Role.role_apps).selectinload(RoleApp.app))
        .where(UserRoleAssignment.user_id == current_user.id)
    )
    user_role_assignments = role_result.scalars().all()
    
    role_apps = {}
    for ura in user_role_assignments:
        for ra in ura.role.role_apps:
            if ra.app.is_active and is_app_accessible(ra.app):
                role_apps[ra.app.id] = ra.app
    
    user_app_result = await db.execute(
        select(UserApp).options(selectinload(UserApp.app)).where(UserApp.user_id == current_user.id)
    )
    user_apps = user_app_result.scalars().all()
    
    final_apps = dict(role_apps)
    for ua in user_apps:
        if ua.is_granted and ua.app.is_active and is_app_accessible(ua.app):
            final_apps[ua.app.id] = ua.app
        elif not ua.is_granted and ua.app.id in final_apps:
            del final_apps[ua.app.id]
    
    apps_list = [AppResponse.model_validate(app) for app in final_apps.values()]
    
    # Admins see all apps allocated to their company (or all for sysadmin)
    if current_user.role in [UserRoleEnum.SYSADMIN, UserRoleEnum.COMPANY_ADMIN]:
        if current_user.role == UserRoleEnum.SYSADMIN:
            all_apps_result = await db.execute(select(App).where(App.is_active == True))
        else:
            # Company admin sees global apps + apps allocated to their company
            all_apps_result = await db.execute(
                select(App).where(
                    App.is_active == True,
                    or_(App.is_global == True, App.id.in_(company_app_ids))
                )
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
    
    # Set company_id based on user role
    if admin.role == UserRoleEnum.COMPANY_ADMIN:
        data['company_id'] = admin.company_id
        data['is_global'] = False  # Company admins can't create global apps
    
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
    
    # Check access
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
            continue  # Company admins can't change global flag
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
async def list_users(
    company_id: Optional[uuid.UUID] = Query(None, description="Filter by company (sysadmin only)"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_company_admin_or_above)
):
    """List users (filtered by company for company_admin, with optional filter for sysadmin)"""
    if admin.role == UserRoleEnum.SYSADMIN:
        query = select(User).options(selectinload(User.company))
        if company_id:
            query = query.where(User.company_id == company_id)
        result = await db.execute(query.order_by(User.email))
        users = result.scalars().all()
        # Include company name for sysadmin
        return [
            UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=user.role,
                status=user.status,
                auth_method=user.auth_method,
                must_change_password=user.must_change_password,
                must_change_email=user.must_change_email,
                company_id=user.company_id,
                company_name=user.company.name if user.company else None,
                last_login=user.last_login,
                created_at=user.created_at
            )
            for user in users
        ]
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
    
    # Role restrictions for company_admin
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
    
    # Role restrictions
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

# ==================== USER-APP ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/apps")
async def assign_app_to_user(user_id: uuid.UUID, app_id: uuid.UUID, is_granted: bool = True, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Assign or revoke an app for a user"""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    app_result = await db.execute(select(App).where(App.id == app_id))
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="App not found")
    
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
    """Remove app override from user"""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await db.execute(delete(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == app_id))
    await db.commit()
    return {"message": "App assignment removed"}

# ==================== USER-ROLE ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/roles")
async def assign_role_to_user(user_id: uuid.UUID, role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Assign a role to a user"""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and user.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found")
    
    existing = await db.execute(select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.role_id == role_id))
    if existing.scalar_one_or_none():
        return {"message": "Role already assigned"}
    
    assignment = UserRoleAssignment(user_id=user_id, role_id=role_id)
    db.add(assignment)
    await db.commit()
    return {"message": "Role assigned"}

@api_router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(user_id: uuid.UUID, role_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Remove a role from a user"""
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
    """List roles (filtered by company)"""
    if current_user.role == UserRoleEnum.SYSADMIN:
        result = await db.execute(select(Role).order_by(Role.name))
    else:
        result = await db.execute(
            select(Role).where(or_(Role.company_id == None, Role.company_id == current_user.company_id)).order_by(Role.name)
        )
    return [RoleResponse.model_validate(role) for role in result.scalars().all()]

@api_router.post("/roles", response_model=RoleResponse)
async def create_role(role_data: RoleCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new role"""
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
    """Get role by ID with apps"""
    result = await db.execute(
        select(Role).options(selectinload(Role.role_apps).selectinload(RoleApp.app)).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    apps = [AppResponse.model_validate(ra.app) for ra in role.role_apps]
    role_response = RoleWithApps.model_validate(role)
    role_response.apps = apps
    return role_response

@api_router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(role_id: uuid.UUID, role_data: RoleUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update a role"""
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
    """Delete a role"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and role.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await db.delete(role)
    await db.commit()
    return {"message": "Role deleted"}

# ==================== ROLE-APP ASSIGNMENTS ====================

@api_router.post("/roles/{role_id}/apps")
async def assign_app_to_role(role_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Assign an app to a role"""
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if admin.role != UserRoleEnum.SYSADMIN and role.company_id != admin.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    app_result = await db.execute(select(App).where(App.id == app_id))
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="App not found")
    
    existing = await db.execute(select(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == app_id))
    if existing.scalar_one_or_none():
        return {"message": "App already assigned to role"}
    
    role_app = RoleApp(role_id=role_id, app_id=app_id)
    db.add(role_app)
    await db.commit()
    return {"message": "App assigned to role"}

@api_router.delete("/roles/{role_id}/apps/{app_id}")
async def remove_app_from_role(role_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Remove an app from a role"""
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
async def list_employees(
    emp_status: Optional[EmployeeStatus] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    company_id: Optional[uuid.UUID] = Query(None, description="Filter by company (sysadmin only)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List employees (filtered by company)"""
    query = select(Employee).options(selectinload(Employee.company))
    
    if current_user.role != UserRoleEnum.SYSADMIN:
        query = query.where(Employee.company_id == current_user.company_id)
    elif company_id:
        # Sysadmin can filter by specific company
        query = query.where(Employee.company_id == company_id)
    
    if emp_status:
        query = query.where(Employee.status == emp_status)
    if department:
        query = query.where(Employee.department == department)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(
            Employee.first_name.ilike(search_pattern),
            Employee.last_name.ilike(search_pattern),
            Employee.email.ilike(search_pattern)
        ))
    
    result = await db.execute(query.order_by(Employee.last_name, Employee.first_name))
    employees = result.scalars().all()
    
    # Include company name for sysadmin
    if current_user.role == UserRoleEnum.SYSADMIN:
        return [
            EmployeeResponse(
                id=emp.id,
                company_id=emp.company_id,
                company_name=emp.company.name if emp.company else None,
                user_id=emp.user_id,
                bamboo_id=emp.bamboo_id,
                first_name=emp.first_name,
                last_name=emp.last_name,
                email=emp.email,
                department=emp.department,
                division=emp.division,
                team=emp.team,
                job_title=emp.job_title,
                location=emp.location,
                manager_id=emp.manager_id,
                hire_date=emp.hire_date,
                status=emp.status,
                created_at=emp.created_at
            )
            for emp in employees
        ]
    
    return [EmployeeResponse.model_validate(emp) for emp in employees]

@api_router.post("/employees", response_model=EmployeeResponse)
async def create_employee(emp_data: EmployeeCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Create a new employee"""
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
    """Get employee by ID"""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if current_user.role != UserRoleEnum.SYSADMIN and employee.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return EmployeeResponse.model_validate(employee)

@api_router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(employee_id: uuid.UUID, emp_data: EmployeeUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Update an employee"""
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
    """Delete an employee"""
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
    """List all global settings (sysadmin only)"""
    result = await db.execute(select(Settings).order_by(Settings.key))
    return [SettingResponse.model_validate(s) for s in result.scalars().all()]

@api_router.get("/settings/bamboohr", response_model=BambooHRSettings)
async def get_bamboohr_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_company_admin_or_above)):
    """Get BambooHR settings"""
    settings = {}
    for key in ['bamboohr_api_key', 'bamboohr_company_domain', 'bamboohr_sync_enabled', 'bamboohr_last_sync']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    return BambooHRSettings(
        api_key=settings.get('bamboohr_api_key'),
        company_domain=settings.get('bamboohr_company_domain'),
        sync_enabled=settings.get('bamboohr_sync_enabled', 'false').lower() == 'true',
        last_sync=None
    )

@api_router.put("/settings/bamboohr")
async def update_bamboohr_settings(bamboo_settings: BambooHRSettings, db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Update BambooHR settings (sysadmin only)"""
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
            setting = Settings(key=key, value=value)
            db.add(setting)
    
    await db.commit()
    return {"message": "BambooHR settings updated"}

@api_router.post("/settings/bamboohr/sync")
async def sync_bamboohr(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Trigger BambooHR sync (placeholder)"""
    api_key_result = await db.execute(select(Settings).where(Settings.key == 'bamboohr_api_key'))
    api_key_setting = api_key_result.scalar_one_or_none()
    
    if not api_key_setting or not api_key_setting.value:
        raise HTTPException(status_code=400, detail="BambooHR API key not configured")
    
    logger.info("BambooHR sync triggered (placeholder)")
    
    result = await db.execute(select(Settings).where(Settings.key == 'bamboohr_last_sync'))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = datetime.now(timezone.utc).isoformat()
    else:
        setting = Settings(key='bamboohr_last_sync', value=datetime.now(timezone.utc).isoformat())
        db.add(setting)
    
    await db.commit()
    return {"message": "Sync triggered (mock)", "synced_at": datetime.now(timezone.utc).isoformat()}

@api_router.get("/settings/azure-sso", response_model=AzureSSOSettings)
async def get_azure_settings(db: AsyncSession = Depends(get_db), admin: User = Depends(get_sysadmin)):
    """Get Azure SSO settings (sysadmin only)"""
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
    """Update Azure SSO settings (sysadmin only)"""
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
            setting = Settings(key=key, value=value)
            db.add(setting)
    
    await db.commit()
    return {"message": "Azure SSO settings updated"}

# ==================== EMAIL SERVICE ====================

from email_service import (
    send_email, send_magic_link_email, send_password_reset_email,
    send_welcome_email, send_notification_email, EmailRequest, EmailResponse
)

class EmailSendRequest(BaseModel):
    to: List[str]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    template: Optional[str] = None
    template_data: Optional[dict] = None

class EmailTemplateListResponse(BaseModel):
    templates: List[str]
    description: dict

@api_router.post("/email/send", response_model=dict)
async def send_email_endpoint(
    request: EmailSendRequest,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send an email via the central email service.
    
    Can be used by:
    - Identity Hub (password resets, magic links, notifications)
    - Downstream apps via API (requires admin permissions or API key)
    
    Templates available: magic_link, password_reset, welcome, notification
    """
    result = await send_email(
        to=request.to,
        subject=request.subject,
        html=request.html,
        text=request.text,
        template=request.template,
        template_data=request.template_data
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return {
        "success": result.success,
        "message": result.message,
        "email_id": result.email_id,
        "mock": result.mock
    }

@api_router.get("/email/templates")
async def list_email_templates(
    current_user: User = Depends(get_admin_user)
):
    """List available email templates."""
    return {
        "templates": ["magic_link", "password_reset", "welcome", "notification"],
        "description": {
            "magic_link": "Magic link login email. Data: app_name, magic_link, expires_in",
            "password_reset": "Password reset email. Data: app_name, reset_link, expires_in",
            "welcome": "Welcome email for new users. Data: app_name, first_name, login_url",
            "notification": "Generic notification. Data: app_name, title, message, action_url (optional), action_text (optional)"
        }
    }

@api_router.get("/email/status")
async def email_service_status(
    current_user: User = Depends(get_admin_user)
):
    """Check email service configuration status."""
    resend_configured = bool(os.environ.get('RESEND_API_KEY'))
    return {
        "configured": resend_configured,
        "provider": "resend" if resend_configured else "mock",
        "sender_email": os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev'),
        "sender_name": os.environ.get('SENDER_NAME', 'Identity Hub'),
        "message": "Email service is fully configured" if resend_configured else "Running in mock mode - emails will be logged but not sent"
    }

# ==================== MIGRATION & SCHEMA TRACKING ====================

from migration_service import MigrationService, get_schema_changelog, get_upgrade_instructions

@api_router.get("/admin/migrations")
async def get_migration_status(
    current_user: User = Depends(get_admin_user)
):
    """
    Get current database migration status.
    Shows all migrations and whether they are applied.
    
    Useful for:
    - Checking if production database is up to date
    - Seeing what migrations need to be applied after an upgrade
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view migration status")
    
    service = MigrationService(engine)
    return await service.get_migration_status()

@api_router.get("/admin/migrations/pending")
async def get_pending_migrations(
    current_user: User = Depends(get_admin_user)
):
    """
    Get only pending (not yet applied) migrations.
    
    Returns an empty list if database is up to date.
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view migration status")
    
    service = MigrationService(engine)
    pending = await service.get_pending_migrations()
    return {
        "pending_count": len(pending),
        "is_up_to_date": len(pending) == 0,
        "migrations": [m.to_dict() for m in pending]
    }

@api_router.get("/admin/schema/changelog")
async def get_schema_changelog_endpoint(
    current_user: User = Depends(get_admin_user)
):
    """
    Get the schema version changelog.
    
    Documents all schema changes across versions for production upgrade planning.
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view schema changelog")
    
    return {
        "changelog": get_schema_changelog(),
        "current_version": "3.0.0"
    }

@api_router.get("/admin/schema/upgrade-path")
async def get_upgrade_path(
    from_version: str = Query(..., description="Current version (e.g., '1.0.0')"),
    to_version: str = Query(..., description="Target version (e.g., '3.0.0')"),
    current_user: User = Depends(get_admin_user)
):
    """
    Get upgrade instructions from one version to another.
    
    Returns:
    - All schema changes between versions
    - Required migrations
    - Alembic command to run
    
    Use this to plan production upgrades.
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view upgrade paths")
    
    return get_upgrade_instructions(from_version, to_version)

@api_router.post("/admin/migrations/apply")
async def apply_pending_migrations(
    current_user: User = Depends(get_admin_user)
):
    """
    Apply all pending database migrations.
    
    ⚠️ WARNING: This is a dangerous operation. Only use in development or
    during planned maintenance windows. Always backup your database first.
    
    For production, prefer running Alembic directly:
    ```
    alembic upgrade head
    ```
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can apply migrations")
    
    service = MigrationService(engine)
    result = await service.apply_migrations()
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result

# ==================== HEALTH & ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "Identity & Employee Hub API", "version": "3.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# CORS Configuration - Strict, env-variable driven
cors_origins = os.environ.get('CORS_ORIGINS', '')
if cors_origins == '*':
    logger.warning("CORS_ORIGINS is set to '*' - this is insecure for production!")

# Parse CORS origins properly
allowed_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins if allowed_origins else ["http://localhost:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Bootstrap admin credentials - must change both email AND password on first login
BOOTSTRAP_ADMIN_EMAIL = "admin@bootstrap.hub"
BOOTSTRAP_ADMIN_PASSWORD = "ChangeMeNow!"

# Database initialization function using Alembic
async def init_db_with_alembic():
    """Initialize database using Alembic migrations"""
    import subprocess
    import shutil
    
    # Find alembic in the virtual environment or system path
    alembic_path = shutil.which("alembic") or "/root/.venv/bin/alembic"
    
    try:
        # Run alembic upgrade head from the backend directory
        result = subprocess.run(
            [alembic_path, "upgrade", "head"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            logger.info("Database migrations applied successfully")
            if result.stdout:
                logger.info(f"Migration output: {result.stdout}")
        else:
            logger.warning(f"Alembic migration returned non-zero: {result.stderr}")
            # Fallback to create_all for development if alembic fails
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
        logger.warning("Alembic command not found, using fallback")
        from database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Fallback: Tables created with metadata.create_all")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        # Fallback to create_all
        from database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Fallback: Tables created with metadata.create_all")

# Startup event
@app.on_event("startup")
async def startup():
    logger.info("Starting Identity & Employee Hub v3.0...")
    
    # Initialize database
    await init_db_with_alembic()
    
    # Seed bootstrap admin if not exists
    async with async_session_maker() as session:
        # Check for any sysadmin user
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
                must_change_password=True,  # Force password change
                must_change_email=True       # Force email change
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
