"""
Schema Migration Service for Identity & Employee Hub

Provides:
1. Tracking of applied migrations
2. API endpoint to check pending migrations
3. Upgrade route for production deployments

Usage:
- GET /api/admin/migrations - List all migrations and their status
- GET /api/admin/migrations/pending - Get only pending migrations
- POST /api/admin/migrations/apply - Apply pending migrations (dangerous, requires sysadmin)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

ALEMBIC_INI_PATH = Path(__file__).parent / "alembic.ini"


class MigrationInfo:
    """Information about a single migration."""
    def __init__(
        self,
        revision: str,
        down_revision: Optional[str],
        description: str,
        is_applied: bool,
        branch_labels: Optional[tuple] = None,
        created_date: Optional[str] = None
    ):
        self.revision = revision
        self.down_revision = down_revision
        self.description = description
        self.is_applied = is_applied
        self.branch_labels = branch_labels
        self.created_date = created_date

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision": self.revision,
            "down_revision": self.down_revision,
            "description": self.description,
            "is_applied": self.is_applied,
            "branch_labels": list(self.branch_labels) if self.branch_labels else [],
            "created_date": self.created_date
        }


class MigrationService:
    """Service for tracking and managing database migrations."""
    
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._alembic_cfg = None
        self._script_dir = None
    
    def _get_alembic_config(self) -> Config:
        """Get Alembic configuration."""
        if self._alembic_cfg is None:
            self._alembic_cfg = Config(str(ALEMBIC_INI_PATH))
        return self._alembic_cfg
    
    def _get_script_directory(self) -> ScriptDirectory:
        """Get Alembic script directory."""
        if self._script_dir is None:
            self._script_dir = ScriptDirectory.from_config(self._get_alembic_config())
        return self._script_dir
    
    async def get_current_revision(self) -> Optional[str]:
        """Get the current database revision."""
        async with self.engine.connect() as conn:
            def get_revision(sync_conn):
                context = MigrationContext.configure(sync_conn)
                return context.get_current_revision()
            
            return await conn.run_sync(get_revision)
    
    async def get_all_migrations(self) -> List[MigrationInfo]:
        """Get all migrations with their applied status."""
        script_dir = self._get_script_directory()
        current_rev = await self.get_current_revision()
        
        # Get all applied revisions (walk up from current)
        applied_revisions = set()
        if current_rev:
            # Get all revisions that are ancestors of current (including current)
            for rev in script_dir.walk_revisions():
                if rev.revision == current_rev:
                    applied_revisions.add(rev.revision)
                    # Add all ancestors
                    revision = rev
                    while revision.down_revision:
                        if isinstance(revision.down_revision, tuple):
                            for dr in revision.down_revision:
                                applied_revisions.add(dr)
                        else:
                            applied_revisions.add(revision.down_revision)
                        # Try to get the parent revision
                        try:
                            revision = script_dir.get_revision(revision.down_revision if isinstance(revision.down_revision, str) else revision.down_revision[0])
                            if revision:
                                applied_revisions.add(revision.revision)
                        except:
                            break
                    break
        
        migrations = []
        for rev in script_dir.walk_revisions():
            # Parse the doc string for description
            doc = rev.doc or rev.revision
            
            migration = MigrationInfo(
                revision=rev.revision,
                down_revision=rev.down_revision if isinstance(rev.down_revision, str) else (rev.down_revision[0] if rev.down_revision else None),
                description=doc,
                is_applied=rev.revision in applied_revisions,
                branch_labels=rev.branch_labels
            )
            migrations.append(migration)
        
        # Reverse to show oldest first
        migrations.reverse()
        return migrations
    
    async def get_pending_migrations(self) -> List[MigrationInfo]:
        """Get only pending (not yet applied) migrations."""
        all_migrations = await self.get_all_migrations()
        return [m for m in all_migrations if not m.is_applied]
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """Get a summary of migration status."""
        all_migrations = await self.get_all_migrations()
        pending = [m for m in all_migrations if not m.is_applied]
        applied = [m for m in all_migrations if m.is_applied]
        current_rev = await self.get_current_revision()
        
        return {
            "current_revision": current_rev,
            "total_migrations": len(all_migrations),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "is_up_to_date": len(pending) == 0,
            "pending_migrations": [m.to_dict() for m in pending],
            "applied_migrations": [m.to_dict() for m in applied],
            "last_check": datetime.utcnow().isoformat() + "Z"
        }
    
    async def apply_migrations(self) -> Dict[str, Any]:
        """
        Apply all pending migrations.
        WARNING: This should only be called by sysadmins and with caution.
        """
        from alembic import command
        
        pending_before = await self.get_pending_migrations()
        if not pending_before:
            return {
                "success": True,
                "message": "No pending migrations to apply",
                "applied_count": 0
            }
        
        try:
            # Run alembic upgrade head
            config = self._get_alembic_config()
            
            async with self.engine.connect() as conn:
                def run_upgrade(sync_conn):
                    config.attributes['connection'] = sync_conn
                    command.upgrade(config, "head")
                
                await conn.run_sync(run_upgrade)
                await conn.commit()
            
            pending_after = await self.get_pending_migrations()
            applied_count = len(pending_before) - len(pending_after)
            
            return {
                "success": True,
                "message": f"Successfully applied {applied_count} migration(s)",
                "applied_count": applied_count,
                "applied_revisions": [m.revision for m in pending_before if m.revision not in [p.revision for p in pending_after]]
            }
        except Exception as e:
            logger.error(f"Failed to apply migrations: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to apply migrations: {str(e)}",
                "applied_count": 0
            }


# Schema change tracking for documentation
SCHEMA_CHANGELOG = [
    {
        "version": "1.0.0",
        "date": "2026-04-01",
        "changes": [
            "Initial schema: users, companies, apps, roles, employees, settings tables",
            "Added UserApp, RoleApp, UserRoleAssignment junction tables"
        ],
        "migration_revision": "001"
    },
    {
        "version": "2.0.0", 
        "date": "2026-04-15",
        "changes": [
            "Added refresh_tokens table for JWT refresh token storage",
            "Added api_keys table for service-to-service authentication",
            "Added must_change_email field to users table"
        ],
        "migration_revision": "002"
    },
    {
        "version": "3.0.0",
        "date": "2026-04-19",
        "changes": [
            "Added company_apps table for multi-tenant app allocation",
            "Added branding fields to companies (logo_url, primary_color, secondary_color)",
            "Added email_logs table for email service tracking"
        ],
        "migration_revision": "003"
    }
]


def get_schema_changelog() -> List[Dict[str, Any]]:
    """Get the schema changelog for documentation."""
    return SCHEMA_CHANGELOG


def get_upgrade_instructions(from_version: str, to_version: str) -> Dict[str, Any]:
    """
    Get upgrade instructions between versions.
    This is useful for production deployments where you need to know what changed.
    """
    versions = [entry["version"] for entry in SCHEMA_CHANGELOG]
    
    if from_version not in versions:
        return {"error": f"Unknown version: {from_version}"}
    if to_version not in versions:
        return {"error": f"Unknown version: {to_version}"}
    
    from_idx = versions.index(from_version)
    to_idx = versions.index(to_version)
    
    if from_idx >= to_idx:
        return {"error": "from_version must be older than to_version"}
    
    changes_to_apply = SCHEMA_CHANGELOG[from_idx + 1:to_idx + 1]
    
    all_changes = []
    migrations_needed = []
    for entry in changes_to_apply:
        all_changes.extend(entry["changes"])
        migrations_needed.append(entry["migration_revision"])
    
    return {
        "from_version": from_version,
        "to_version": to_version,
        "changes": all_changes,
        "migrations_needed": migrations_needed,
        "alembic_command": f"alembic upgrade {migrations_needed[-1]}" if migrations_needed else None,
        "recommendation": "Always backup your database before applying migrations in production"
    }
