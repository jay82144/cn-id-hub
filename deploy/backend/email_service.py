"""
Central Email Service for Identity & Employee Hub

This service provides email functionality that can be used by:
1. The Identity Hub itself (password resets, magic links, notifications)
2. Downstream apps via the /api/email/send endpoint

Supports:
- Transactional emails (password reset, magic links)
- Notification emails
- Custom emails via API (for downstream apps)
- Email templates
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import resend
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

# Initialize Resend
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
SENDER_NAME = os.environ.get('SENDER_NAME', 'Identity Hub')

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    logger.info("Email service initialized with Resend")
else:
    logger.warning("RESEND_API_KEY not set - email service will operate in mock mode")


# Pydantic models for API
class EmailRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    template: Optional[str] = None  # Template name
    template_data: Optional[Dict[str, Any]] = None  # Data for template


class EmailResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[str] = None
    mock: bool = False


# Email templates
TEMPLATES = {
    "magic_link": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 40px 20px; background-color: #f5f5f5; margin: 0;">
    <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <h1 style="color: #0A0A0A; font-size: 24px; margin: 0 0 24px 0;">Sign in to {app_name}</h1>
        <p style="color: #525252; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
            Click the button below to sign in. This link will expire in {expires_in}.
        </p>
        <a href="{magic_link}" style="display: inline-block; background: #0A0A0A; color: white; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 500; font-size: 16px;">
            Sign in
        </a>
        <p style="color: #737373; font-size: 14px; line-height: 1.5; margin: 24px 0 0 0;">
            If you didn't request this email, you can safely ignore it.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0;">
        <p style="color: #a3a3a3; font-size: 12px; margin: 0;">
            This link can only be used once and expires in {expires_in}.
        </p>
    </div>
</body>
</html>
""",
    "password_reset": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 40px 20px; background-color: #f5f5f5; margin: 0;">
    <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <h1 style="color: #0A0A0A; font-size: 24px; margin: 0 0 24px 0;">Reset your password</h1>
        <p style="color: #525252; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
            We received a request to reset your password for your {app_name} account. Click the button below to choose a new password.
        </p>
        <a href="{reset_link}" style="display: inline-block; background: #0A0A0A; color: white; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 500; font-size: 16px;">
            Reset password
        </a>
        <p style="color: #737373; font-size: 14px; line-height: 1.5; margin: 24px 0 0 0;">
            If you didn't request a password reset, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0;">
        <p style="color: #a3a3a3; font-size: 12px; margin: 0;">
            This link expires in {expires_in}.
        </p>
    </div>
</body>
</html>
""",
    "welcome": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 40px 20px; background-color: #f5f5f5; margin: 0;">
    <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <h1 style="color: #0A0A0A; font-size: 24px; margin: 0 0 24px 0;">Welcome to {app_name}!</h1>
        <p style="color: #525252; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
            Hi {first_name},
        </p>
        <p style="color: #525252; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
            Your account has been created successfully. You can now sign in and start using our platform.
        </p>
        <a href="{login_url}" style="display: inline-block; background: #0A0A0A; color: white; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 500; font-size: 16px;">
            Go to Dashboard
        </a>
        <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0;">
        <p style="color: #a3a3a3; font-size: 12px; margin: 0;">
            Need help? Contact us at support@example.com
        </p>
    </div>
</body>
</html>
""",
    "notification": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 40px 20px; background-color: #f5f5f5; margin: 0;">
    <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <h1 style="color: #0A0A0A; font-size: 24px; margin: 0 0 24px 0;">{title}</h1>
        <p style="color: #525252; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
            {message}
        </p>
        {action_button}
        <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0;">
        <p style="color: #a3a3a3; font-size: 12px; margin: 0;">
            Sent from {app_name}
        </p>
    </div>
</body>
</html>
"""
}


def render_template(template_name: str, data: Dict[str, Any]) -> str:
    """Render an email template with the given data."""
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")
    
    template = TEMPLATES[template_name]
    
    # Handle optional action button for notifications
    if template_name == "notification":
        if data.get("action_url") and data.get("action_text"):
            action_button = f'''
            <a href="{data['action_url']}" style="display: inline-block; background: #0A0A0A; color: white; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 500; font-size: 16px;">
                {data['action_text']}
            </a>
            '''
        else:
            action_button = ""
        data["action_button"] = action_button
    
    # Replace placeholders
    for key, value in data.items():
        template = template.replace("{" + key + "}", str(value))
    
    return template


async def send_email(
    to: List[str],
    subject: str,
    html: Optional[str] = None,
    text: Optional[str] = None,
    template: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
    reply_to: Optional[str] = None
) -> EmailResponse:
    """
    Send an email using Resend.
    
    Args:
        to: List of recipient email addresses
        subject: Email subject
        html: HTML content (optional if using template)
        text: Plain text content (optional)
        template: Template name to use
        template_data: Data to fill in template placeholders
        reply_to: Reply-to email address (optional)
    
    Returns:
        EmailResponse with success status and email ID
    """
    # Build HTML content
    if template and template_data:
        try:
            html = render_template(template, template_data)
        except ValueError as e:
            return EmailResponse(success=False, message=str(e))
    
    if not html and not text:
        return EmailResponse(success=False, message="Email must have html or text content")
    
    # Mock mode if no API key
    if not RESEND_API_KEY:
        logger.info(f"[MOCK EMAIL] To: {to}, Subject: {subject}")
        logger.info(f"[MOCK EMAIL] Content preview: {(html or text)[:200]}...")
        return EmailResponse(
            success=True,
            message=f"Mock email sent to {', '.join(to)}",
            email_id=f"mock_{datetime.utcnow().timestamp()}",
            mock=True
        )
    
    # Build params
    params: Dict[str, Any] = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": to,
        "subject": subject,
    }
    
    if html:
        params["html"] = html
    if text:
        params["text"] = text
    if reply_to:
        params["reply_to"] = reply_to
    
    try:
        # Run sync SDK in thread to keep FastAPI non-blocking
        result = await asyncio.to_thread(resend.Emails.send, params)
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, 'id', None)
        
        logger.info(f"Email sent successfully to {to}, ID: {email_id}")
        return EmailResponse(
            success=True,
            message=f"Email sent to {', '.join(to)}",
            email_id=email_id
        )
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {str(e)}")
        return EmailResponse(success=False, message=f"Failed to send email: {str(e)}")


# Convenience functions for common email types

async def send_magic_link_email(
    to: str,
    magic_link: str,
    app_name: str = "Identity Hub",
    expires_in: str = "15 minutes"
) -> EmailResponse:
    """Send a magic link login email."""
    return await send_email(
        to=[to],
        subject=f"Sign in to {app_name}",
        template="magic_link",
        template_data={
            "app_name": app_name,
            "magic_link": magic_link,
            "expires_in": expires_in
        }
    )


async def send_password_reset_email(
    to: str,
    reset_link: str,
    app_name: str = "Identity Hub",
    expires_in: str = "1 hour"
) -> EmailResponse:
    """Send a password reset email."""
    return await send_email(
        to=[to],
        subject=f"Reset your {app_name} password",
        template="password_reset",
        template_data={
            "app_name": app_name,
            "reset_link": reset_link,
            "expires_in": expires_in
        }
    )


async def send_welcome_email(
    to: str,
    first_name: str,
    login_url: str,
    app_name: str = "Identity Hub"
) -> EmailResponse:
    """Send a welcome email to new users."""
    return await send_email(
        to=[to],
        subject=f"Welcome to {app_name}!",
        template="welcome",
        template_data={
            "app_name": app_name,
            "first_name": first_name,
            "login_url": login_url
        }
    )


async def send_notification_email(
    to: str,
    title: str,
    message: str,
    app_name: str = "Identity Hub",
    action_url: Optional[str] = None,
    action_text: Optional[str] = None
) -> EmailResponse:
    """Send a notification email."""
    return await send_email(
        to=[to],
        subject=title,
        template="notification",
        template_data={
            "app_name": app_name,
            "title": title,
            "message": message,
            "action_url": action_url or "",
            "action_text": action_text or ""
        }
    )
