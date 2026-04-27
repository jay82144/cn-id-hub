"""
Authentication routes for Identity & Employee Hub
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
import logging

from database import get_db
from models import User, UserStatus, AuthMethod
from schemas import (
    LoginRequest, MagicLinkRequest, MagicLinkVerify, TokenResponse,
    ChangePasswordRequest, ChangeCredentialsRequest, RefreshTokenResponse,
    UserResponse
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, generate_magic_link_token,
    verify_token_external, MAGIC_LINK_EXPIRATION_MINUTES,
    create_and_store_refresh_token, validate_refresh_token, revoke_refresh_token,
    revoke_all_user_refresh_tokens, set_refresh_token_cookie, clear_refresh_token_cookie
)
from routes.dependencies import get_user_company_branding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
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


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token from HttpOnly cookie."""
    refresh_token_value = request.cookies.get("refresh_token")
    
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    token_record = await validate_refresh_token(db, refresh_token_value)
    
    if not token_record:
        clear_refresh_token_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
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
    
    access_token = create_access_token(user)
    
    return RefreshTokenResponse(access_token=access_token)


@router.post("/logout")
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


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change password (required on first login for bootstrap admin)"""
    if not current_user.must_change_password and request.current_password:
        if not verify_password(request.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    current_user.password_hash = hash_password(request.new_password)
    current_user.must_change_password = False
    
    # Revoke all existing refresh tokens (security: password changed)
    await revoke_all_user_refresh_tokens(db, current_user.id)
    
    await db.commit()
    
    return {"message": "Password changed successfully"}


@router.post("/change-credentials", response_model=TokenResponse)
async def change_credentials(
    request_data: ChangeCredentialsRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change both email and password (required for bootstrap admin on first login).
    """
    if not current_user.must_change_email and not current_user.must_change_password:
        raise HTTPException(status_code=400, detail="Credential change not required")
    
    # Check if new email is already taken
    if request_data.new_email != current_user.email:
        existing = await db.execute(select(User).where(User.email == request_data.new_email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
    
    current_user.email = request_data.new_email
    current_user.password_hash = hash_password(request_data.new_password)
    current_user.must_change_email = False
    current_user.must_change_password = False
    
    await revoke_all_user_refresh_tokens(db, current_user.id)
    
    await db.commit()
    await db.refresh(current_user)
    
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


@router.post("/magic-link")
async def request_magic_link(request: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    """Request a magic link for passwordless login"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"message": "If the email exists, a magic link has been sent"}
    
    if user.auth_method == AuthMethod.AZURE_SSO:
        return {"message": "If the email exists, a magic link has been sent"}
    
    token = generate_magic_link_token()
    user.magic_link_token = token
    user.magic_link_expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRATION_MINUTES)
    await db.commit()
    
    logger.info(f"Magic link token for {request.email}: {token}")
    
    return {"message": "If the email exists, a magic link has been sent", "debug_token": token}


@router.post("/magic-link/verify", response_model=TokenResponse)
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


@router.get("/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token - for downstream apps"""
    if not credentials:
        return {"valid": False, "error": "No token provided"}
    return verify_token_external(credentials.credentials)


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user info"""
    return UserResponse.model_validate(current_user)


# ==================== SSO REDIRECT VALIDATION ====================

from pydantic import BaseModel
from models import App, Settings

class RedirectValidationRequest(BaseModel):
    redirect_url: str

class RedirectValidationResponse(BaseModel):
    allowed: bool
    reason: str = None


def extract_origin(url: str) -> str:
    """Extract origin (scheme + host + port) from URL"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin


@router.post("/validate-redirect", response_model=RedirectValidationResponse)
async def validate_redirect_url(
    request: RedirectValidationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate if a redirect URL is allowed for SSO.
    
    Validation rules:
    1. URL must be well-formed
    2. Must be HTTPS in production (or HTTP for localhost)
    3. Must match an allowed callback URL:
       - From registered apps in the database
       - From Settings (allowed_sso_callbacks)
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(request.redirect_url)
        
        # Basic URL validation
        if not parsed.scheme or not parsed.netloc:
            return RedirectValidationResponse(allowed=False, reason="Invalid URL format")
        
        # Require HTTPS except for localhost
        is_localhost = parsed.netloc.startswith('localhost') or parsed.netloc.startswith('127.0.0.1')
        if not is_localhost and parsed.scheme != 'https':
            return RedirectValidationResponse(allowed=False, reason="HTTPS required for non-localhost URLs")
        
        origin = extract_origin(request.redirect_url)
        
        # Check against registered apps
        result = await db.execute(select(App).where(App.is_active == True))
        apps = result.scalars().all()
        
        for app in apps:
            if app.url:
                app_origin = extract_origin(app.url)
                if origin == app_origin:
                    logger.info(f"Redirect allowed: {origin} matches app '{app.name}'")
                    return RedirectValidationResponse(allowed=True)
        
        # Check against allowed_sso_callbacks setting
        settings_result = await db.execute(
            select(Settings).where(Settings.key == 'allowed_sso_callbacks')
        )
        setting = settings_result.scalar_one_or_none()
        
        if setting and setting.value:
            allowed_callbacks = [cb.strip() for cb in setting.value.split(',')]
            for callback in allowed_callbacks:
                if callback and (origin == callback or origin.startswith(callback)):
                    logger.info(f"Redirect allowed: {origin} matches allowed callback '{callback}'")
                    return RedirectValidationResponse(allowed=True)
        
        logger.warning(f"Redirect denied: {origin} not in allowed list")
        return RedirectValidationResponse(
            allowed=False, 
            reason="This application is not registered for SSO. Contact your administrator."
        )
        
    except Exception as e:
        logger.error(f"Error validating redirect: {e}")
        return RedirectValidationResponse(allowed=False, reason="Validation error")

