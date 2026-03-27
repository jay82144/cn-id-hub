from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

# Auth Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MagicLinkRequest(BaseModel):
    email: EmailStr

class MagicLinkVerify(BaseModel):
    token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

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

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: UserRole
    status: UserStatus
    last_login: Optional[datetime]
    created_at: datetime

class UserWithApps(UserResponse):
    apps: List["AppResponse"] = []
    roles: List["RoleResponse"] = []

# Role Schemas
class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str]
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

class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    icon: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class AppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    url: str
    icon: Optional[str]
    description: Optional[str]
    is_active: bool
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
    company_domain: Optional[str] = None
    sync_enabled: bool = False
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

class UserRoleAssignment(BaseModel):
    user_id: UUID
    role_id: UUID

# Launchpad response
class LaunchpadResponse(BaseModel):
    user: UserResponse
    apps: List[AppResponse]
    should_redirect: bool
    redirect_url: Optional[str] = None

# Update forward refs
UserWithApps.model_rebuild()
RoleWithApps.model_rebuild()
TokenResponse.model_rebuild()
