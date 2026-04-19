"""
Admin routes for Identity & Employee Hub
Includes migrations, schema tracking, and audit logging
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

from database import get_db, engine
from models import User, UserRole as UserRoleEnum
from auth import get_current_user
from migration_service import MigrationService, get_schema_changelog, get_upgrade_instructions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


# ==================== AUDIT LOG MODEL ====================

from sqlalchemy import Column, String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from database import Base
import enum


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ROLE_CHANGE = "role_change"
    APP_ACCESS = "app_access"
    SETTINGS_CHANGE = "settings_change"


# Audit log will be stored in-memory for now (can be moved to DB later)
_audit_logs: List[dict] = []


async def log_audit_event(
    action: AuditAction,
    user_id: Optional[uuid.UUID],
    user_email: Optional[str],
    resource_type: str,
    resource_id: Optional[str],
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    company_id: Optional[uuid.UUID] = None
):
    """Log an audit event"""
    event = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action.value,
        "user_id": str(user_id) if user_id else None,
        "user_email": user_email,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
        "company_id": str(company_id) if company_id else None
    }
    _audit_logs.append(event)
    
    # Keep only last 10000 events in memory
    if len(_audit_logs) > 10000:
        _audit_logs.pop(0)
    
    logger.info(f"AUDIT: {action.value} on {resource_type}/{resource_id} by {user_email}")
    return event


# ==================== AUDIT LOG ENDPOINTS ====================

@router.get("/audit-logs")
async def get_audit_logs(
    action: Optional[AuditAction] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """
    Get audit logs (sysadmin only).
    Supports filtering by action, resource_type, and user_id.
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view audit logs")
    
    filtered_logs = _audit_logs.copy()
    
    if action:
        filtered_logs = [log for log in filtered_logs if log["action"] == action.value]
    if resource_type:
        filtered_logs = [log for log in filtered_logs if log["resource_type"] == resource_type]
    if user_id:
        filtered_logs = [log for log in filtered_logs if log["user_id"] == str(user_id)]
    
    # Sort by timestamp descending (most recent first)
    filtered_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    total = len(filtered_logs)
    paginated = filtered_logs[offset:offset + limit]
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": paginated
    }


@router.get("/audit-logs/actions")
async def get_audit_actions(
    current_user: User = Depends(get_current_user)
):
    """Get list of audit action types"""
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view audit logs")
    
    return {
        "actions": [action.value for action in AuditAction],
        "resource_types": ["user", "company", "app", "role", "employee", "settings", "api_key", "company_app"]
    }


# ==================== MIGRATION ENDPOINTS ====================

@router.get("/migrations")
async def get_migration_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current database migration status.
    Shows all migrations and whether they are applied.
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view migration status")
    
    service = MigrationService(engine)
    return await service.get_migration_status()


@router.get("/migrations/pending")
async def get_pending_migrations(
    current_user: User = Depends(get_current_user)
):
    """Get only pending (not yet applied) migrations."""
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view migration status")
    
    service = MigrationService(engine)
    pending = await service.get_pending_migrations()
    return {
        "pending_count": len(pending),
        "is_up_to_date": len(pending) == 0,
        "migrations": [m.to_dict() for m in pending]
    }


@router.get("/schema/changelog")
async def get_schema_changelog_endpoint(
    current_user: User = Depends(get_current_user)
):
    """Get the schema version changelog."""
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view schema changelog")
    
    return {
        "changelog": get_schema_changelog(),
        "current_version": "3.0.0"
    }


@router.get("/schema/upgrade-path")
async def get_upgrade_path(
    from_version: str = Query(..., description="Current version (e.g., '1.0.0')"),
    to_version: str = Query(..., description="Target version (e.g., '3.0.0')"),
    current_user: User = Depends(get_current_user)
):
    """Get upgrade instructions from one version to another."""
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can view upgrade paths")
    
    return get_upgrade_instructions(from_version, to_version)


@router.post("/migrations/apply")
async def apply_pending_migrations(
    current_user: User = Depends(get_current_user)
):
    """
    Apply all pending database migrations.
    
    ⚠️ WARNING: This is a dangerous operation. Only use in development or
    during planned maintenance windows. Always backup your database first.
    """
    if current_user.role != UserRoleEnum.SYSADMIN:
        raise HTTPException(status_code=403, detail="Only sysadmins can apply migrations")
    
    service = MigrationService(engine)
    result = await service.apply_migrations()
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    # Log audit event
    await log_audit_event(
        action=AuditAction.SETTINGS_CHANGE,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="migrations",
        resource_id="apply",
        details=f"Applied {result.get('applied_count', 0)} migrations"
    )
    
    return result


# Export the audit function for use in other modules
__all__ = ['router', 'log_audit_event', 'AuditAction']
