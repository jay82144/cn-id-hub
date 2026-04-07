"""
Authentication module for Identity & Employee Hub
Production-ready implementation with:
- Short-lived access tokens (configurable, default 15 min)
- Long-lived refresh tokens (configurable, default 30 days)
- API key authentication for service-to-service calls
- Bcrypt password hashing
"""
import os
import secrets
import hashlib
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import jwt
from fastapi import HTTPException, status, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, RefreshToken, APIKey, APIKeyScope, UserRole as UserRoleEnum

# JWT settings from environment variables
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_MINUTES', '15'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_DAYS', '30'))
MAGIC_LINK_EXPIRATION_MINUTES = int(os.environ.get('MAGIC_LINK_EXPIRATION_MINUTES', '15'))

security = HTTPBearer(auto_error=False)


# ==================== PASSWORD HASHING (BCRYPT) ====================

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash"""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ==================== TOKEN HASHING (FOR DB STORAGE) ====================

def hash_token(token: str) -> str:
    """Hash a token for secure storage (SHA256)"""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_secure_token() -> str:
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(32)


# ==================== ACCESS TOKEN (JWT) ====================

def create_access_token(user: User, company_id: Optional[str] = None) -> str:
    """
    Create a short-lived access token
    JWT payload includes: sub, email, user_id, company_id, roles, permissions, token_type, exp
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    roles = [user.role.value]
    permissions = _get_user_permissions(user)
    
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "user_id": str(user.id),
        "company_id": str(user.company_id) if user.company_id else None,
        "roles": roles,
        "permissions": permissions,
        "token_type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _get_user_permissions(user: User) -> list:
    """Derive permissions from user role"""
    permissions = ["read:profile"]
    
    if user.role == UserRoleEnum.SYSADMIN:
        permissions.extend([
            "admin:system", "manage:companies", "manage:users", 
            "manage:apps", "manage:roles", "manage:settings"
        ])
    elif user.role == UserRoleEnum.COMPANY_ADMIN:
        permissions.extend([
            "admin:company", "manage:users", "manage:apps", 
            "manage:roles", "manage:employees"
        ])
    else:
        permissions.extend(["access:launchpad", "access:apps"])
    
    return permissions


def decode_access_token(token: str) -> dict:
    """Decode and validate access token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        if payload.get("token_type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )


# ==================== REFRESH TOKEN ====================

def create_refresh_token_value() -> str:
    """Generate a random refresh token value"""
    return secrets.token_urlsafe(64)


async def create_and_store_refresh_token(
    db: AsyncSession,
    user: User,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None
) -> str:
    """
    Create a refresh token, hash it, and store in database.
    Returns the raw token value (to be set in HttpOnly cookie).
    """
    raw_token = create_refresh_token_value()
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=expires_at
    )
    db.add(refresh_token)
    await db.commit()
    
    return raw_token


async def validate_refresh_token(
    db: AsyncSession,
    raw_token: str
) -> Optional[RefreshToken]:
    """
    Validate a refresh token by looking up its hash in the database.
    """
    token_hash = hash_token(raw_token)
    
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a refresh token"""
    token_hash = hash_token(raw_token)
    
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_record = result.scalar_one_or_none()
    
    if token_record:
        token_record.revoked = True
        token_record.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        return True
    return False


async def revoke_all_user_refresh_tokens(db: AsyncSession, user_id) -> int:
    """Revoke all refresh tokens for a user"""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        )
    )
    tokens = result.scalars().all()
    
    count = 0
    for token in tokens:
        token.revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        count += 1
    
    await db.commit()
    return count


# ==================== API KEY AUTHENTICATION ====================

def generate_api_key() -> Tuple[str, str]:
    """
    Generate an API key with prefix for identification.
    Returns: (full_key, prefix)
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"idhub_{random_part}"
    prefix = full_key[:10]
    return full_key, prefix


async def validate_api_key(db: AsyncSession, api_key: str) -> Optional[APIKey]:
    """
    Validate an API key by looking up its hash in the database.
    """
    key_hash = hash_token(api_key)
    
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked == False
        )
    )
    api_key_record = result.scalar_one_or_none()
    
    if api_key_record:
        if api_key_record.expires_at and api_key_record.expires_at < datetime.now(timezone.utc):
            return None
        
        api_key_record.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        
        return api_key_record
    
    return None


# ==================== COOKIE HELPERS ====================

def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    """Set refresh token as HttpOnly secure cookie"""
    cookie_secure = os.environ.get('COOKIE_SECURE', 'true').lower() == 'true'
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/"
    )


def clear_refresh_token_cookie(response: Response) -> None:
    """Clear refresh token cookie"""
    response.delete_cookie(key="refresh_token", path="/")


# ==================== AUTHENTICATION DEPENDENCIES ====================

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current user from Bearer token or API key.
    """
    token = None
    if credentials:
        token = credentials.credentials
    
    api_key = request.headers.get("X-API-Key")
    
    if not token and not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Try API key authentication
    if api_key:
        api_key_record = await validate_api_key(db, api_key)
        if api_key_record:
            result = await db.execute(select(User).where(User.id == api_key_record.user_id))
            user = result.scalar_one_or_none()
            if user and user.status.value == "active":
                return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Try Bearer token authentication
    payload = decode_access_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if user.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    
    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require admin role"""
    if current_user.role not in [UserRoleEnum.SYSADMIN, UserRoleEnum.COMPANY_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ==================== MAGIC LINK ====================

def generate_magic_link_token() -> str:
    """Generate a secure magic link token"""
    return secrets.token_urlsafe(32)


# ==================== EXTERNAL TOKEN VERIFICATION ====================

def verify_token_external(token: str) -> dict:
    """
    Endpoint for downstream apps to verify tokens.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "valid": True,
            "sub": payload.get("sub"),
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "company_id": payload.get("company_id"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", []),
            "token_type": payload.get("token_type"),
            "exp": payload.get("exp")
        }
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token expired"}
    except jwt.InvalidTokenError as e:
        return {"valid": False, "error": str(e)}
