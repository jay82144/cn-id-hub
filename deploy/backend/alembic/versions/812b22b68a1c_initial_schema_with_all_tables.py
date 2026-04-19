"""Initial schema with all tables

Revision ID: 812b22b68a1c
Revises: 
Create Date: 2026-04-07 21:36:47.725590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '812b22b68a1c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for Identity & Employee Hub."""
    
    # Create enum types
    op.execute("CREATE TYPE userrole AS ENUM ('sysadmin', 'company_admin', 'user')")
    op.execute("CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'pending')")
    op.execute("CREATE TYPE authmethod AS ENUM ('password', 'azure_sso', 'any')")
    op.execute("CREATE TYPE employeestatus AS ENUM ('active', 'archived')")
    op.execute("CREATE TYPE apikeyscope AS ENUM ('global', 'read_only', 'apps_only', 'verify_only')")
    
    # Companies table
    op.create_table(
        'companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), nullable=False, server_default='#0A0A0A'),
        sa.Column('secondary_color', sa.String(7), nullable=False, server_default='#0047FF'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('role', postgresql.ENUM('sysadmin', 'company_admin', 'user', name='userrole', create_type=False), nullable=False, server_default='user'),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'pending', name='userstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('auth_method', postgresql.ENUM('password', 'azure_sso', 'any', name='authmethod', create_type=False), nullable=False, server_default='password'),
        sa.Column('must_change_password', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('must_change_email', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('azure_id', sa.String(255), unique=True, nullable=True),
        sa.Column('magic_link_token', sa.String(255), nullable=True),
        sa.Column('magic_link_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'name', name='uq_role_company_name'),
    )
    
    # Apps table
    op.create_table(
        'apps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('icon', sa.String(100), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_global', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Role Apps junction table
    op.create_table(
        'role_apps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('apps.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # User Apps junction table (overrides)
    op.create_table(
        'user_apps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('apps.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # User Role Assignments junction table
    op.create_table(
        'user_role_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Company Apps junction table (app allocation to companies)
    op.create_table(
        'company_apps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('app_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('apps.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('company_id', 'app_id', name='uq_company_app'),
    )
    
    # Employees table
    op.create_table(
        'employees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('bamboo_id', sa.String(100), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('division', sa.String(100), nullable=True),
        sa.Column('team', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(150), nullable=True),
        sa.Column('location', sa.String(150), nullable=True),
        sa.Column('manager_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True),
        sa.Column('hire_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'archived', name='employeestatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'email', name='uq_employee_company_email'),
    )
    
    # Settings table (global)
    op.create_table(
        'settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(100), unique=True, nullable=False),
        sa.Column('value', sa.Text, nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Company Settings table
    op.create_table(
        'company_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text, nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'key', name='uq_company_settings_key'),
    )
    
    # Refresh Tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token_hash', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('device_info', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_prefix', sa.String(10), nullable=False),
        sa.Column('key_hash', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('scope', postgresql.ENUM('global', 'read_only', 'apps_only', 'verify_only', name='apikeyscope', create_type=False), nullable=False, server_default='verify_only'),
        sa.Column('allowed_apps', sa.Text, nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('api_keys')
    op.drop_table('refresh_tokens')
    op.drop_table('company_settings')
    op.drop_table('settings')
    op.drop_table('employees')
    op.drop_table('company_apps')
    op.drop_table('user_role_assignments')
    op.drop_table('user_apps')
    op.drop_table('role_apps')
    op.drop_table('apps')
    op.drop_table('roles')
    op.drop_table('users')
    op.drop_table('companies')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS apikeyscope")
    op.execute("DROP TYPE IF EXISTS employeestatus")
    op.execute("DROP TYPE IF EXISTS authmethod")
    op.execute("DROP TYPE IF EXISTS userstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
