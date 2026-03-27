from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_
from sqlalchemy.orm import selectinload
import os
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import json

from database import get_db, init_db, engine, async_session_maker
from models import (
    User, Role, App, RoleApp, UserApp, UserRoleAssignment, Employee, Settings,
    UserRole as UserRoleEnum, UserStatus, EmployeeStatus
)
from schemas import (
    LoginRequest, MagicLinkRequest, MagicLinkVerify, TokenResponse,
    UserCreate, UserUpdate, UserResponse, UserWithApps,
    RoleCreate, RoleUpdate, RoleResponse, RoleWithApps,
    AppCreate, AppUpdate, AppResponse,
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    SettingUpdate, SettingResponse, BambooHRSettings, AzureSSOSettings,
    RoleAppAssignment, UserAppAssignment, UserRoleAssignment as UserRoleAssignmentSchema,
    LaunchpadResponse
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_admin_user, generate_magic_link_token,
    verify_token_external, MAGIC_LINK_EXPIRATION_MINUTES
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Identity & Employee Hub API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    token = create_access_token(str(user.id), user.email, user.role.value)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )

@api_router.post("/auth/magic-link")
async def request_magic_link(request: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    """Request a magic link for passwordless login"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if user exists
        return {"message": "If the email exists, a magic link has been sent"}
    
    # Generate magic link token
    token = generate_magic_link_token()
    user.magic_link_token = token
    user.magic_link_expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRATION_MINUTES)
    await db.commit()
    
    # In production, send email here
    # For now, return the token (remove in production)
    logger.info(f"Magic link token for {request.email}: {token}")
    
    return {
        "message": "If the email exists, a magic link has been sent",
        "debug_token": token  # Remove in production
    }

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
    
    # Clear magic link
    user.magic_link_token = None
    user.magic_link_expires = None
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    token = create_access_token(str(user.id), user.email, user.role.value)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
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

# ==================== LAUNCHPAD ENDPOINT ====================

@api_router.get("/launchpad", response_model=LaunchpadResponse)
async def get_launchpad(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's launchpad with accessible apps"""
    # Get user's role assignments
    role_result = await db.execute(
        select(UserRoleAssignment)
        .options(selectinload(UserRoleAssignment.role).selectinload(Role.role_apps).selectinload(RoleApp.app))
        .where(UserRoleAssignment.user_id == current_user.id)
    )
    user_role_assignments = role_result.scalars().all()
    
    # Collect apps from roles
    role_apps = {}
    for ura in user_role_assignments:
        for ra in ura.role.role_apps:
            if ra.app.is_active:
                role_apps[ra.app.id] = ra.app
    
    # Get user-specific app overrides
    user_app_result = await db.execute(
        select(UserApp)
        .options(selectinload(UserApp.app))
        .where(UserApp.user_id == current_user.id)
    )
    user_apps = user_app_result.scalars().all()
    
    # Apply overrides
    final_apps = dict(role_apps)
    for ua in user_apps:
        if ua.is_granted and ua.app.is_active:
            final_apps[ua.app.id] = ua.app
        elif not ua.is_granted and ua.app.id in final_apps:
            del final_apps[ua.app.id]
    
    apps_list = [AppResponse.model_validate(app) for app in final_apps.values()]
    
    # If admin, they can always access all active apps
    if current_user.role == UserRoleEnum.ADMIN:
        all_apps_result = await db.execute(select(App).where(App.is_active == True))
        all_apps = all_apps_result.scalars().all()
        apps_list = [AppResponse.model_validate(app) for app in all_apps]
    
    should_redirect = len(apps_list) == 1
    redirect_url = apps_list[0].url if should_redirect else None
    
    return LaunchpadResponse(
        user=UserResponse.model_validate(current_user),
        apps=apps_list,
        should_redirect=should_redirect,
        redirect_url=redirect_url
    )

# ==================== APPS CRUD ====================

@api_router.get("/apps", response_model=List[AppResponse])
async def list_apps(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all apps (admin can see inactive)"""
    query = select(App)
    if not include_inactive or current_user.role != UserRoleEnum.ADMIN:
        query = query.where(App.is_active == True)
    
    result = await db.execute(query.order_by(App.name))
    apps = result.scalars().all()
    return [AppResponse.model_validate(app) for app in apps]

@api_router.post("/apps", response_model=AppResponse)
async def create_app(
    app_data: AppCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create a new app"""
    app = App(**app_data.model_dump())
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return AppResponse.model_validate(app)

@api_router.get("/apps/{app_id}", response_model=AppResponse)
async def get_app(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get app by ID"""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return AppResponse.model_validate(app)

@api_router.put("/apps/{app_id}", response_model=AppResponse)
async def update_app(
    app_id: uuid.UUID,
    app_data: AppUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update an app"""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    for field, value in app_data.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    
    await db.commit()
    await db.refresh(app)
    return AppResponse.model_validate(app)

@api_router.delete("/apps/{app_id}")
async def delete_app(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete an app"""
    result = await db.execute(select(App).where(App.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    await db.delete(app)
    await db.commit()
    return {"message": "App deleted"}

# ==================== USERS CRUD ====================

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """List all users (admin only)"""
    result = await db.execute(select(User).order_by(User.email))
    users = result.scalars().all()
    return [UserResponse.model_validate(user) for user in users]

@api_router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create a new user"""
    # Check if email exists
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user_data.model_dump()
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
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Get user by ID with apps and roles"""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.user_apps).selectinload(UserApp.app),
            selectinload(User.user_roles).selectinload(UserRoleAssignment.role)
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get effective apps (from roles + overrides)
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
    return user_response

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

@api_router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted"}

# ==================== USER-APP ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/apps")
async def assign_app_to_user(
    user_id: uuid.UUID,
    app_id: uuid.UUID,
    is_granted: bool = True,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Assign or revoke an app for a user"""
    # Check user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check app exists
    app_result = await db.execute(select(App).where(App.id == app_id))
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="App not found")
    
    # Check if assignment exists
    existing = await db.execute(
        select(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == app_id)
    )
    user_app = existing.scalar_one_or_none()
    
    if user_app:
        user_app.is_granted = is_granted
    else:
        user_app = UserApp(user_id=user_id, app_id=app_id, is_granted=is_granted)
        db.add(user_app)
    
    await db.commit()
    return {"message": "App assignment updated"}

@api_router.delete("/users/{user_id}/apps/{app_id}")
async def remove_app_from_user(
    user_id: uuid.UUID,
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Remove app override from user"""
    await db.execute(
        delete(UserApp).where(UserApp.user_id == user_id, UserApp.app_id == app_id)
    )
    await db.commit()
    return {"message": "App assignment removed"}

# ==================== USER-ROLE ASSIGNMENTS ====================

@api_router.post("/users/{user_id}/roles")
async def assign_role_to_user(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Assign a role to a user"""
    # Check user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check role exists
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if assignment exists
    existing = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Role already assigned"}
    
    assignment = UserRoleAssignment(user_id=user_id, role_id=role_id)
    db.add(assignment)
    await db.commit()
    return {"message": "Role assigned"}

@api_router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Remove a role from a user"""
    await db.execute(
        delete(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id
        )
    )
    await db.commit()
    return {"message": "Role removed"}

# ==================== ROLES CRUD ====================

@api_router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all roles"""
    result = await db.execute(select(Role).order_by(Role.name))
    roles = result.scalars().all()
    return [RoleResponse.model_validate(role) for role in roles]

@api_router.post("/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create a new role"""
    existing = await db.execute(select(Role).where(Role.name == role_data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role name already exists")
    
    role = Role(**role_data.model_dump())
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)

@api_router.get("/roles/{role_id}", response_model=RoleWithApps)
async def get_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get role by ID with apps"""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.role_apps).selectinload(RoleApp.app))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    apps = [AppResponse.model_validate(ra.app) for ra in role.role_apps]
    role_response = RoleWithApps.model_validate(role)
    role_response.apps = apps
    return role_response

@api_router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    role_data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update a role"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    for field, value in role_data.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    
    await db.commit()
    await db.refresh(role)
    return RoleResponse.model_validate(role)

@api_router.delete("/roles/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete a role"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    await db.delete(role)
    await db.commit()
    return {"message": "Role deleted"}

# ==================== ROLE-APP ASSIGNMENTS ====================

@api_router.post("/roles/{role_id}/apps")
async def assign_app_to_role(
    role_id: uuid.UUID,
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Assign an app to a role"""
    # Check role exists
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check app exists
    app_result = await db.execute(select(App).where(App.id == app_id))
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="App not found")
    
    # Check if assignment exists
    existing = await db.execute(
        select(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == app_id)
    )
    if existing.scalar_one_or_none():
        return {"message": "App already assigned to role"}
    
    role_app = RoleApp(role_id=role_id, app_id=app_id)
    db.add(role_app)
    await db.commit()
    return {"message": "App assigned to role"}

@api_router.delete("/roles/{role_id}/apps/{app_id}")
async def remove_app_from_role(
    role_id: uuid.UUID,
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Remove an app from a role"""
    await db.execute(
        delete(RoleApp).where(RoleApp.role_id == role_id, RoleApp.app_id == app_id)
    )
    await db.commit()
    return {"message": "App removed from role"}

# ==================== EMPLOYEES CRUD ====================

@api_router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(
    status: Optional[EmployeeStatus] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List employees (can filter by status, department, search)"""
    query = select(Employee)
    
    if status:
        query = query.where(Employee.status == status)
    if department:
        query = query.where(Employee.department == department)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Employee.first_name.ilike(search_pattern),
                Employee.last_name.ilike(search_pattern),
                Employee.email.ilike(search_pattern)
            )
        )
    
    result = await db.execute(query.order_by(Employee.last_name, Employee.first_name))
    employees = result.scalars().all()
    return [EmployeeResponse.model_validate(emp) for emp in employees]

@api_router.post("/employees", response_model=EmployeeResponse)
async def create_employee(
    emp_data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create a new employee"""
    existing = await db.execute(select(Employee).where(Employee.email == emp_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Employee email already exists")
    
    employee = Employee(**emp_data.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)

@api_router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get employee by ID"""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeResponse.model_validate(employee)

@api_router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    emp_data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update an employee"""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    for field, value in emp_data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    
    await db.commit()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)

@api_router.delete("/employees/{employee_id}")
async def delete_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete an employee"""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    await db.delete(employee)
    await db.commit()
    return {"message": "Employee deleted"}

# ==================== SETTINGS ====================

@api_router.get("/settings", response_model=List[SettingResponse])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """List all settings"""
    result = await db.execute(select(Settings).order_by(Settings.key))
    settings = result.scalars().all()
    return [SettingResponse.model_validate(s) for s in settings]

@api_router.get("/settings/bamboohr", response_model=BambooHRSettings)
async def get_bamboohr_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
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
        last_sync=None  # Parse from settings if needed
    )

@api_router.put("/settings/bamboohr")
async def update_bamboohr_settings(
    bamboo_settings: BambooHRSettings,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update BambooHR settings"""
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
async def sync_bamboohr(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Trigger BambooHR sync (placeholder)"""
    # Check if credentials are configured
    api_key_result = await db.execute(select(Settings).where(Settings.key == 'bamboohr_api_key'))
    api_key_setting = api_key_result.scalar_one_or_none()
    
    if not api_key_setting or not api_key_setting.value:
        raise HTTPException(status_code=400, detail="BambooHR API key not configured")
    
    # Placeholder - actual sync logic would go here
    logger.info("BambooHR sync triggered (placeholder)")
    
    # Update last sync time
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
async def get_azure_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Get Azure SSO settings"""
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
async def update_azure_settings(
    azure_settings: AzureSSOSettings,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update Azure SSO settings"""
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

# ==================== HEALTH & ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "Identity & Employee Hub API", "version": "1.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
async def startup():
    logger.info("Starting Identity & Employee Hub...")
    await init_db()
    
    # Seed admin user if not exists
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == 'steve.harding@me.com'))
        admin_exists = result.scalar_one_or_none()
        
        if not admin_exists:
            logger.info("Creating seed admin user...")
            admin_user = User(
                email='steve.harding@me.com',
                password_hash=hash_password("ChangeMeNow!"),
                first_name='Steve',
                last_name='Harding',
                role=UserRoleEnum.ADMIN,
                status=UserStatus.ACTIVE
            )
            session.add(admin_user)
            await session.commit()
            logger.info("Admin user created: steve.harding@me.com")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down...")
