from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

# Enums
class UserRole(str, Enum):
    SYSADMIN = "sysadmin"
    COMPANY_ADMIN = "company_admin"
    USER = "user"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class AuthMethod(str, Enum):
    PASSWORD = "password"
    AZURE_SSO = "azure_sso"
    ANY = "any"

class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

# Company Schemas
class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9-]+$')
    logo_url: Optional[str] = None
    primary_color: str = "#0A0A0A"
    secondary_color: str = "#0047FF"

class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    is_active: Optional[bool] = None

class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    slug: str
    logo_url: Optional[str]
    primary_color: str
    secondary_color: str
    is_active: bool
    created_at: datetime

class CompanyBranding(BaseModel):
    """Minimal branding info for login/UI"""
    name: str
    logo_url: Optional[str]
    primary_color: str
    secondary_color: str

# Auth Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None  # Not required for forced change
    new_password: str = Field(..., min_length=8)

class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str = Field(..., min_length=1)  # Required for security

class ChangeCredentialsRequest(BaseModel):
    """For forced email + password change on first login"""
    new_email: EmailStr
    new_password: str = Field(..., min_length=8)

class MagicLinkRequest(BaseModel):
    email: EmailStr

class MagicLinkVerify(BaseModel):
    token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"
    must_change_password: bool = False
    must_change_email: bool = False
    company: Optional[CompanyBranding] = None

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AzureSSOCallback(BaseModel):
    code: str
    state: Optional[str] = None

# User Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.USER
    auth_method: AuthMethod = AuthMethod.PASSWORD
    company_id: Optional[UUID] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    auth_method: Optional[AuthMethod] = None
    must_change_password: Optional[bool] = None
    company_id: Optional[UUID] = None

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: UserRole
    status: UserStatus
    auth_method: AuthMethod
    must_change_password: bool
    must_change_email: bool = False
    company_id: Optional[UUID]
    company_name: Optional[str] = None  # For sysadmin views
    last_login: Optional[datetime]
    created_at: datetime

class UserWithApps(UserResponse):
    apps: List["AppResponse"] = []
    roles: List["RoleResponse"] = []
    company: Optional[CompanyResponse] = None

# Role Schemas
class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    company_id: Optional[UUID] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str]
    company_id: Optional[UUID]
    created_at: datetime

class RoleWithApps(RoleResponse):
    apps: List["AppResponse"] = []

# App Schemas
class AppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=500)
    icon: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    is_global: bool = False
    company_id: Optional[UUID] = None

class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    icon: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_global: Optional[bool] = None

class AppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    url: str
    icon: Optional[str]
    description: Optional[str]
    is_active: bool
    is_global: bool
    company_id: Optional[UUID]
    created_at: datetime

# Employee Schemas
class EmployeeCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    department: Optional[str] = None
    division: Optional[str] = None
    team: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    manager_id: Optional[UUID] = None
    hire_date: Optional[datetime] = None
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    company_id: Optional[UUID] = None  # Set by backend if not sysadmin

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    division: Optional[str] = None
    team: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    manager_id: Optional[UUID] = None
    hire_date: Optional[datetime] = None
    status: Optional[EmployeeStatus] = None

class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    company_id: UUID
    company_name: Optional[str] = None  # For sysadmin views
    user_id: Optional[UUID]
    bamboo_id: Optional[str]
    first_name: str
    last_name: str
    email: str
    department: Optional[str]
    division: Optional[str]
    team: Optional[str]
    job_title: Optional[str]
    location: Optional[str]
    manager_id: Optional[UUID]
    hire_date: Optional[datetime]
    status: EmployeeStatus
    created_at: datetime

# Settings Schemas
class SettingUpdate(BaseModel):
    value: Optional[str] = None

class SettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    key: str
    value: Optional[str]
    description: Optional[str]
    updated_at: datetime

class BambooHRSettings(BaseModel):
    api_key: Optional[str] = None
    subdomain: Optional[str] = None
    enabled: bool = False
    last_sync: Optional[datetime] = None

class AzureSSOSettings(BaseModel):
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    enabled: bool = False

# Assignment Schemas
class RoleAppAssignment(BaseModel):
    role_id: UUID
    app_id: UUID

class UserAppAssignment(BaseModel):
    user_id: UUID
    app_id: UUID
    is_granted: bool = True

class UserRoleAssignmentSchema(BaseModel):
    user_id: UUID
    role_id: UUID

# Launchpad response
class LaunchpadResponse(BaseModel):
    user: UserResponse
    apps: List[AppResponse]
    should_redirect: bool
    redirect_url: Optional[str] = None
    company: Optional[CompanyBranding] = None

# Update forward refs
UserWithApps.model_rebuild()
RoleWithApps.model_rebuild()
TokenResponse.model_rebuild()


# API Key Schemas
class APIKeyScope(str, Enum):
    GLOBAL = "global"
    READ_ONLY = "read_only"
    APPS_ONLY = "apps_only"
    VERIFY_ONLY = "verify_only"

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scope: APIKeyScope = APIKeyScope.VERIFY_ONLY
    allowed_apps: Optional[List[UUID]] = None  # Only for APPS_ONLY scope
    expires_in_days: Optional[int] = None  # Null = never expires

class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    key_prefix: str
    scope: APIKeyScope
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

class APIKeyCreatedResponse(APIKeyResponse):
    """Response when creating a new API key - includes the full key (only shown once)"""
    api_key: str  # Full key, only returned on creation

class TokenVerifyResponse(BaseModel):
    valid: bool
    sub: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None
    company_id: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    token_type: Optional[str] = None
    exp: Optional[int] = None
    error: Optional[str] = None


# Company App Schemas (Apps purchased/allocated to companies)
class CompanyAppCreate(BaseModel):
    company_id: UUID
    app_id: UUID
    expires_at: Optional[datetime] = None

class CompanyAppUpdate(BaseModel):
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

class CompanyAppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    company_id: UUID
    app_id: UUID
    is_active: bool
    purchased_at: datetime
    expires_at: Optional[datetime]

class CompanyAppWithDetails(CompanyAppResponse):
    """Company app with expanded company and app details"""
    company_name: Optional[str] = None
    app_name: Optional[str] = None
    app_icon: Optional[str] = None


# Company Branding Update (for company admins)
class CompanyBrandingUpdate(BaseModel):
    logo_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
