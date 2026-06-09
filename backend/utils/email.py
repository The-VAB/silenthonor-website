# Email utilities using Resend API for Silent Honor Foundation
import os
import httpx
from middleware.logging_middleware import logger

# Resend API configuration
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "Silent Honor <noreply@silenthonor.org>")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@silenthonor.org")

async def send_email(to: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """Send email using Resend API"""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set - email not sent")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": FROM_EMAIL,
                    "to": [to],
                    "subject": subject,
                    "html": html_content,
                    "text": text_content or ""
                }
            )

            if response.status_code == 200:
                logger.info(f"Email sent to {to}: {subject}")
                return True
            else:
                logger.error(f"Failed to send email: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False

async def send_welcome_email(to: str, first_name: str) -> bool:
    """Send welcome email to new member"""
    subject = "Welcome to Silent Honor Foundation"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>Welcome, {first_name}!</h1>
            <p>Thank you for joining the Silent Honor Foundation. We're honored to serve those who have served our nation.</p>
            <p>Here's what you can do next:</p>
            <ul style="color: #9CA3AF; line-height: 2;">
                <li>Upload your DD-214 to verify your veteran status</li>
                <li>Access free financial education courses</li>
                <li>Connect with a certified financial counselor</li>
                <li>Track your credit repair progress</li>
            </ul>
            <p style="text-align: center;">
                <a href="https://silenthonor.org/dashboard.html" class="btn">Access Your Dashboard</a>
            </p>
            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
                <p>If you have any questions, contact us at support@silenthonor.org</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    Welcome to Silent Honor Foundation, {first_name}!

    Thank you for joining. We're honored to serve those who have served our nation.

    Here's what you can do next:
    - Upload your DD-214 to verify your veteran status
    - Access free financial education courses
    - Connect with a certified financial counselor
    - Track your credit repair progress

    Visit your dashboard: https://silenthonor.org/dashboard.html

    Silent Honor Foundation | Veterans Helping Veterans
    """
    return await send_email(to, subject, html_content, text_content)

async def send_password_reset_email(to: str, first_name: str, reset_token: str) -> bool:
    """Send password reset email"""
    reset_url = f"https://silenthonor.org/reset-password.html?token={reset_token}"
    subject = "Reset Your Password - Silent Honor Foundation"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
            .warning {{ color: #F97316; font-size: 13px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>Password Reset Request</h1>
            <p>Hi {first_name},</p>
            <p>We received a request to reset your password. Click the button below to create a new password:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="btn">Reset Password</a>
            </p>
            <p class="warning">This link will expire in 1 hour. If you didn't request this reset, please ignore this email.</p>
            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    Password Reset Request

    Hi {first_name},

    We received a request to reset your password. Visit the link below to create a new password:

    {reset_url}

    This link will expire in 1 hour. If you didn't request this reset, please ignore this email.

    Silent Honor Foundation | Veterans Helping Veterans
    """
    return await send_email(to, subject, html_content, text_content)

async def send_dd214_approved_email(to: str, first_name: str) -> bool:
    """Send DD-214 approval notification"""
    subject = "Your Veteran Status Has Been Verified - Silent Honor Foundation"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #22C55E; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
            .checkmark {{ font-size: 48px; text-align: center; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <div class="checkmark">&#10004;</div>
            <h1 style="text-align: center;">Verified!</h1>
            <p>Great news, {first_name}! Your DD-214 has been reviewed and your veteran status has been verified.</p>
            <p>You now have full access to all Silent Honor Foundation services:</p>
            <ul style="color: #9CA3AF; line-height: 2;">
                <li>All financial education courses</li>
                <li>One-on-one financial counseling</li>
                <li>Credit repair guidance</li>
                <li>Dispute tracking tools</li>
            </ul>
            <p style="text-align: center;">
                <a href="https://silenthonor.org/dashboard.html" class="btn">Go to Dashboard</a>
            </p>
            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    Your Veteran Status Has Been Verified!

    Great news, {first_name}! Your DD-214 has been reviewed and your veteran status has been verified.

    You now have full access to all Silent Honor Foundation services:
    - All financial education courses
    - One-on-one financial counseling
    - Credit repair guidance
    - Dispute tracking tools

    Visit your dashboard: https://silenthonor.org/dashboard.html

    Silent Honor Foundation | Veterans Helping Veterans
    """
    return await send_email(to, subject, html_content, text_content)

async def send_counselor_assigned_email(to: str, first_name: str, counselor_name: str) -> bool:
    """Send counselor assignment notification"""
    subject = "You've Been Assigned a Financial Counselor - Silent Honor Foundation"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #C9952A; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
            .counselor {{ background: rgba(201, 149, 42, 0.1); border: 1px solid #C9952A; padding: 20px; margin: 20px 0; text-align: center; }}
            .counselor-name {{ font-size: 20px; color: #ffffff; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>Your Counselor is Ready!</h1>
            <p>Hi {first_name},</p>
            <p>You've been assigned a certified financial counselor who will guide you on your journey to financial wellness.</p>
            <div class="counselor">
                <p style="color: #C9952A; margin-bottom: 10px;">Your Counselor</p>
                <p class="counselor-name">{counselor_name}</p>
            </div>
            <p>Your counselor will reach out soon to schedule your first session. You can also message them directly through your dashboard.</p>
            <p style="text-align: center;">
                <a href="https://silenthonor.org/counselor.html" class="btn">View Counselor</a>
            </p>
            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    You've Been Assigned a Financial Counselor!

    Hi {first_name},

    You've been assigned a certified financial counselor who will guide you on your journey to financial wellness.

    Your Counselor: {counselor_name}

    Your counselor will reach out soon to schedule your first session. You can also message them directly through your dashboard.

    View your counselor: https://silenthonor.org/counselor.html

    Silent Honor Foundation | Veterans Helping Veterans
    """
    return await send_email(to, subject, html_content, text_content)

async def send_new_message_notification(to: str, first_name: str, sender_name: str) -> bool:
    """Send new message notification"""
    subject = f"New Message from {sender_name} - Silent Honor Foundation"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>New Message</h1>
            <p>Hi {first_name},</p>
            <p>You have a new message from <strong style="color: #ffffff;">{sender_name}</strong>.</p>
            <p style="text-align: center;">
                <a href="https://silenthonor.org/messages.html" class="btn">View Message</a>
            </p>
            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""
    New Message

    Hi {first_name},

    You have a new message from {sender_name}.

    View your messages: https://silenthonor.org/messages.html

    Silent Honor Foundation | Veterans Helping Veterans
    """
    return await send_email(to, subject, html_content, text_content)

async def send_admin_notification(subject: str, message: str) -> bool:
    """Send notification to admin"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span> Admin</div>
            </div>
            <h1>{subject}</h1>
            <p>{message}</p>
            <p style="text-align: center;">
                <a href="https://silenthonor.org/admin.html" class="btn">Go to Admin Panel</a>
            </p>
        </div>
    </body>
    </html>
    """
    return await send_email(ADMIN_EMAIL, f"[Admin] {subject}", html_content, message)

async def send_new_membership_notification(member_data: dict) -> bool:
    """Send new membership application notification to admin (m.lugenbell@silenthonor.org)"""
    admin_email = "m.lugenbell@silenthonor.org"
    first_name = member_data.get("first_name", "")
    last_name = member_data.get("last_name", "")
    subject = f"New Membership Application - {first_name} {last_name}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #C9952A; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .info-table td {{ padding: 10px 0; border-bottom: 1px solid #374151; }}
            .info-table td:first-child {{ color: #6B7280; width: 40%; }}
            .info-table td:last-child {{ color: #ffffff; }}
            .notes {{ background: rgba(201, 149, 42, 0.1); border: 1px solid #C9952A; padding: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>New Membership Application</h1>
            <p>A new veteran has submitted a membership application and is awaiting DD-214 review.</p>

            <table class="info-table">
                <tr><td>Name</td><td><strong>{first_name} {last_name}</strong></td></tr>
                <tr><td>Email</td><td>{member_data.get('email', 'N/A')}</td></tr>
                <tr><td>Phone</td><td>{member_data.get('phone', 'N/A')}</td></tr>
                <tr><td>Branch</td><td>{member_data.get('branch', 'N/A')}</td></tr>
                <tr><td>Service Status</td><td>{member_data.get('service_status', 'N/A')}</td></tr>
                <tr><td>State</td><td>{member_data.get('state', 'N/A')}</td></tr>
            </table>

            <div class="notes"><strong>What they need help with:</strong><br>{member_data.get('challenges', 'Not specified')}</div>

            <p style="text-align: center;">
                <a href="https://silenthonor.org/admin.html" class="btn">Review Application</a>
            </p>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    New Membership Application - {first_name} {last_name}

    A new veteran has submitted a membership application.

    Name: {first_name} {last_name}
    Email: {member_data.get('email', 'N/A')}
    Phone: {member_data.get('phone', 'N/A')}
    Branch: {member_data.get('branch', 'N/A')}
    Service Status: {member_data.get('service_status', 'N/A')}

    What they need help with:
    {member_data.get('challenges', 'Not specified')}

    Review application: https://silenthonor.org/admin.html
    """

    return await send_email(admin_email, subject, html_content, text_content)

async def send_staff_welcome_email(to: str, first_name: str, role: str, temp_password: str) -> bool:
    """Send welcome email to new staff member with login credentials"""
    subject = f"Welcome to Silent Honor Foundation - Your {role.title()} Account"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #C9952A; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
            .credentials {{ background: rgba(185, 28, 28, 0.1); border: 1px solid #B91C1C; padding: 20px; margin: 20px 0; }}
            .credentials p {{ margin: 5px 0; }}
            .warning {{ color: #F97316; font-size: 13px; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>Welcome to the Team!</h1>
            <p>Hi {first_name},</p>
            <p>Your {role} account has been created for the Silent Honor Foundation portal. You can now log in and start helping our veteran members.</p>

            <div class="credentials">
                <p><strong style="color: #ffffff;">Your Login Credentials:</strong></p>
                <p>Email: <strong style="color: #ffffff;">{to}</strong></p>
                <p>Temporary Password: <strong style="color: #ffffff;">{temp_password}</strong></p>
                <p class="warning">Please change your password after your first login for security.</p>
            </div>

            <p style="text-align: center;">
                <a href="https://silenthonor.org/login.html" class="btn">Log In Now</a>
            </p>

            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
                <p>If you have questions, contact m.lugenbell@silenthonor.org</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Welcome to Silent Honor Foundation!

    Hi {first_name},

    Your {role} account has been created for the Silent Honor Foundation portal.

    Your Login Credentials:
    Email: {to}
    Temporary Password: {temp_password}

    IMPORTANT: Please change your password after your first login for security.

    Log in at: https://silenthonor.org/login.html

    Silent Honor Foundation | Veterans Helping Veterans
    """

    return await send_email(to, subject, html_content, text_content)

async def send_staff_invite_email(to: str, first_name: str, role: str, reset_token: str) -> bool:
    """Send portal invitation email to new counselor/staff with password setup link"""
    setup_url = f"https://silenthonor.org/reset-password.html?token={reset_token}"
    role_label = role.capitalize()
    portal_url = "https://silenthonor.org/counselor-portal.html" if role == "counselor" else "https://silenthonor.org/admin.html"
    subject = "You've Been Invited to the Silent Honor Staff Portal"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
            .logo-accent {{ color: #B91C1C; }}
            h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
            p {{ color: #9CA3AF; line-height: 1.8; }}
            .btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
            .info-box {{ background: #1F2937; border: 1px solid #374151; padding: 20px; margin: 20px 0; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
            .warning {{ color: #F97316; font-size: 13px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
            </div>
            <h1>Welcome to the Team, {first_name}!</h1>
            <p>You have been added as a <strong>{role_label}</strong> at Silent Honor Foundation. Please set up your password to access the staff portal.</p>
            <div class="info-box">
                <p><strong>Your portal:</strong> <a href="{portal_url}" style="color:#C9952A;">{portal_url}</a></p>
                <p>Once your password is set, log in with your email address at the link above.</p>
            </div>
            <p style="text-align: center;">
                <a href="{setup_url}" class="btn">Set Up My Password</a>
            </p>
            <p class="warning">This link will expire in 24 hours. Contact your administrator if it has expired.</p>
            <div class="footer">
                <p>Silent Honor Foundation | Veterans Helping Veterans</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"""Welcome to Silent Honor Foundation, {first_name}!

You have been added as a {role_label}. Set up your password here:
{setup_url}

Your portal: {portal_url}

This link expires in 24 hours.

Silent Honor Foundation | Veterans Helping Veterans
    """
    return await send_email(to, subject, html_content, text_content)
