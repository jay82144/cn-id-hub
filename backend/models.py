from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import uuid
from datetime import datetime, timezone
import enum

class UserRole(str, enum.Enum):
    SYSADMIN = "sysadmin"      # Can manage all companies and system settings
    COMPANY_ADMIN = "company_admin"  # Can manage users/settings within their company
    USER = "user"              # Regular user, can only access assigned apps

class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class AuthMethod(str, enum.Enum):
    PASSWORD = "password"      # Can only use password login
    AZURE_SSO = "azure_sso"    # Can only use Azure SSO
    ANY = "any"                # Can use any method

class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

class Company(Base):
    """Multi-tenant company/organization"""
    __tablename__ = "companies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)  # URL-friendly identifier
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#0A0A0A", nullable=False)  # Hex color
    secondary_color = Column(String(7), default="#0047FF", nullable=False)  # Hex color
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="company", cascade="all, delete-orphan")
    roles = relationship("Role", back_populates="company", cascade="all, delete-orphan")
    apps = relationship("App", back_populates="company")
    settings = relationship("CompanySettings", back_populates="company", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)  # Null for sysadmins
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for SSO-only users
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    auth_method = Column(SQLEnum(AuthMethod), default=AuthMethod.PASSWORD, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)  # Force password change on next login
    must_change_email = Column(Boolean, default=False, nullable=False)  # Force email change on next login (bootstrap admin)
    azure_id = Column(String(255), unique=True, nullable=True)  # For Azure SSO
    magic_link_token = Column(String(255), nullable=True)
    magic_link_expires = Column(DateTime(timezone=True), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    company = relationship("Company", back_populates="users")
    user_apps = relationship("UserApp", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRoleAssignment", back_populates="user", cascade="all, delete-orphan")
    employee = relationship("Employee", back_populates="user", uselist=False)

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)  # Null for global roles
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Unique constraint: name unique within company (or globally if company_id is null)
    __table_args__ = (
        UniqueConstraint('company_id', 'name', name='uq_role_company_name'),
    )
    
    # Relationships
    company = relationship("Company", back_populates="roles")
    role_apps = relationship("RoleApp", back_populates="role", cascade="all, delete-orphan")
    user_assignments = relationship("UserRoleAssignment", back_populates="role", cascade="all, delete-orphan")

class App(Base):
    __tablename__ = "apps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)  # Null for global apps
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    icon = Column(String(100), nullable=True)  # Lucide icon name or URL
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_global = Column(Boolean, default=False, nullable=False)  # Available to all companies
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    company = relationship("Company", back_populates="apps")
    role_apps = relationship("RoleApp", back_populates="app", cascade="all, delete-orphan")
    user_apps = relationship("UserApp", back_populates="app", cascade="all, delete-orphan")

class RoleApp(Base):
    """Default apps assigned to a role"""
    __tablename__ = "role_apps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    role = relationship("Role", back_populates="role_apps")
    app = relationship("App", back_populates="role_apps")

class UserApp(Base):
    """Per-user app overrides (additions or removals from role defaults)"""
    __tablename__ = "user_apps"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    is_granted = Column(Boolean, default=True, nullable=False)  # True = explicitly granted, False = explicitly revoked
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_apps")
    app = relationship("App", back_populates="user_apps")

class UserRoleAssignment(Base):
    """Assigns roles to users"""
    __tablename__ = "user_role_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_assignments")

class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    bamboo_id = Column(String(100), nullable=True)  # External BambooHR ID
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=True)
    division = Column(String(100), nullable=True)
    team = Column(String(100), nullable=True)
    job_title = Column(String(150), nullable=True)
    location = Column(String(150), nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    hire_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(SQLEnum(EmployeeStatus), default=EmployeeStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Unique constraint: email unique within company
    __table_args__ = (
        UniqueConstraint('company_id', 'email', name='uq_employee_company_email'),
    )
    
    # Relationships
    company = relationship("Company", back_populates="employees")
    user = relationship("User", back_populates="employee")
    manager = relationship("Employee", remote_side=[id], backref="direct_reports")

class Settings(Base):
    """Global system settings"""
    __tablename__ = "settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class CompanySettings(Base):
    """Per-company settings (Azure SSO, BambooHR, etc.)"""
    __tablename__ = "company_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'key', name='uq_company_settings_key'),
    )
    
    # Relationships
    company = relationship("Company", back_populates="settings")


class RefreshToken(Base):
    """Refresh tokens for JWT authentication (30 day expiry, stored for revocation)"""
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)  # Hashed token for lookup
    device_info = Column(String(500), nullable=True)  # User agent / device info
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", backref="refresh_tokens")


class APIKeyScope(str, enum.Enum):
    """API key permission scopes"""
    GLOBAL = "global"           # Full access like the user who created it
    READ_ONLY = "read_only"     # Read-only access to user's resources
    APPS_ONLY = "apps_only"     # Can only access specific apps
    VERIFY_ONLY = "verify_only" # Can only verify tokens and get user info


class APIKey(Base):
    """API keys for service-to-service authentication"""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)  # Descriptive name for the key
    key_prefix = Column(String(10), nullable=False)  # First 8 chars for identification (e.g., "idhub_xx")
    key_hash = Column(String(255), unique=True, nullable=False, index=True)  # Hashed full key
    scope = Column(SQLEnum(APIKeyScope), default=APIKeyScope.VERIFY_ONLY, nullable=False)
    allowed_apps = Column(Text, nullable=True)  # JSON array of app IDs if scope is APPS_ONLY
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Null = never expires
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", backref="api_keys")
    company = relationship("Company", backref="api_keys")
