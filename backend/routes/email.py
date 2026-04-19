"""
Email service routes for Identity & Employee Hub
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import os

from database import get_db
from models import User
from auth import get_admin_user
from email_service import send_email as send_email_service

router = APIRouter(prefix="/email", tags=["Email Service"])


class EmailSendRequest:
    """Email send request model"""
    def __init__(
        self,
        to: List[str],
        subject: str,
        html: Optional[str] = None,
        text: Optional[str] = None,
        template: Optional[str] = None,
        template_data: Optional[dict] = None
    ):
        self.to = to
        self.subject = subject
        self.html = html
        self.text = text
        self.template = template
        self.template_data = template_data


from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class EmailRequest(BaseModel):
    to: List[str]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    template: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None


@router.post("/send")
async def send_email_endpoint(
    request: EmailRequest,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send an email via the central email service.
    
    Can be used by:
    - Identity Hub (password resets, magic links, notifications)
    - Downstream apps via API (requires admin permissions or API key)
    
    Templates available: magic_link, password_reset, welcome, notification
    """
    result = await send_email_service(
        to=request.to,
        subject=request.subject,
        html=request.html,
        text=request.text,
        template=request.template,
        template_data=request.template_data
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return {
        "success": result.success,
        "message": result.message,
        "email_id": result.email_id,
        "mock": result.mock
    }


@router.get("/templates")
async def list_email_templates(
    current_user: User = Depends(get_admin_user)
):
    """List available email templates."""
    return {
        "templates": ["magic_link", "password_reset", "welcome", "notification"],
        "description": {
            "magic_link": "Magic link login email. Data: app_name, magic_link, expires_in",
            "password_reset": "Password reset email. Data: app_name, reset_link, expires_in",
            "welcome": "Welcome email for new users. Data: app_name, first_name, login_url",
            "notification": "Generic notification. Data: app_name, title, message, action_url (optional), action_text (optional)"
        }
    }


@router.get("/status")
async def email_service_status(
    current_user: User = Depends(get_admin_user)
):
    """Check email service configuration status."""
    resend_configured = bool(os.environ.get('RESEND_API_KEY'))
    return {
        "configured": resend_configured,
        "provider": "resend" if resend_configured else "mock",
        "sender_email": os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev'),
        "sender_name": os.environ.get('SENDER_NAME', 'Identity Hub'),
        "message": "Email service is fully configured" if resend_configured else "Running in mock mode - emails will be logged but not sent"
    }
