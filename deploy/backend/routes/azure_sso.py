"""
Azure SSO routes for Identity & Employee Hub
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import os
import logging

from database import get_db
from models import User, Settings, UserRole as UserRoleEnum, UserStatus, AuthMethod
from schemas import UserResponse
from auth import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/azure", tags=["Azure SSO"])

# Store auth flows in memory (should use Redis in production)
_azure_auth_flows = {}


@router.get("/config")
async def get_azure_sso_config(db: AsyncSession = Depends(get_db)):
    """Check if Azure SSO is configured and enabled"""
    settings = {}
    for key in ['azure_tenant_id', 'azure_client_id', 'azure_sso_enabled']:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            settings[key] = setting.value
    
    is_enabled = settings.get('azure_sso_enabled', 'false').lower() == 'true'
    is_configured = bool(settings.get('azure_tenant_id')) and bool(settings.get('azure_client_id'))
    
    return {"enabled": is_enabled, "configured": is_configured}


@router.get("/login")
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
    
    backend_url = os.environ.get('BACKEND_URL', 'http://localhost:8000')
    redirect_uri = f"{backend_url}/api/auth/azure/callback"
    
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        msal_app = ConfidentialClientApplication(
            client_id=client_id, authority=authority, client_credential=client_secret
        )
        
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


@router.get("/callback")
async def azure_sso_callback(
    code: str = None, state: str = None, error: str = None, error_description: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Azure AD SSO callback"""
    from msal import ConfidentialClientApplication
    import requests
    
    backend_url = os.environ.get('BACKEND_URL', 'http://localhost:8000')
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
                user.auth_method = AuthMethod.AZURE_SSO
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
