//! Transactional email via Amazon SES v2 -- a faithful port of the Python
//! backend's utils/email.py (same subjects, same HTML/text bodies) so the two
//! services send identical mail during the migration.
//!
//! Sends are fire-and-forget: handlers spawn these on a background task and never
//! block the response on email delivery (mirrors `asyncio.create_task(...)`).
//! Requires `ses:SendEmail` on the Lambda role and FROM_EMAIL/ADMIN_EMAIL in env
//! (see infra/aws/lambda-api.tf).

use aws_config::BehaviorVersion;
use aws_sdk_sesv2::types::{Body, Content, Destination, EmailContent, Message};
use aws_sdk_sesv2::Client;
use once_cell::sync::OnceCell;

static FROM: OnceCell<String> = OnceCell::new();

// Emails are low-frequency (signup, resets), so build a client per send rather
// than caching it -- keeps sh-core off a direct tokio dependency.
async fn client() -> Client {
    let cfg = aws_config::defaults(BehaviorVersion::latest()).load().await;
    Client::new(&cfg)
}

fn from_addr() -> &'static str {
    FROM.get_or_init(|| {
        std::env::var("FROM_EMAIL")
            .unwrap_or_else(|_| "Silent Honor <no-reply@silenthonorfoundation.org>".to_string())
    })
}

fn admin_addr() -> String {
    // The Python backend hard-codes this recipient for new-membership alerts.
    "m.lugenbell@silenthonor.org".to_string()
}

/// Low-level send. Logs and swallows errors. Returns whether the send succeeded
/// (most callers are fire-and-forget and ignore this; the staff-invite flow awaits
/// it and gates its response on delivery, matching the Python backend).
pub async fn send_email(to: &str, subject: &str, html: &str, text: &str) -> bool {
    let content = |data: &str| {
        Content::builder()
            .data(data)
            .charset("UTF-8")
            .build()
            .ok()
    };
    let body = Body::builder()
        .set_html(content(html))
        .set_text(content(if text.is_empty() { " " } else { text }))
        .build();
    let subj = match content(subject) {
        Some(s) => s,
        None => return false,
    };
    let msg = Message::builder().subject(subj).body(body).build();
    let email = EmailContent::builder().simple(msg).build();
    let dest = Destination::builder().to_addresses(to).build();

    let ses = client().await;
    match ses
        .send_email()
        .from_email_address(from_addr())
        .destination(dest)
        .content(email)
        .send()
        .await
    {
        Ok(_) => {
            tracing::info!("email sent to {to}: {subject}");
            true
        }
        Err(e) => {
            tracing::error!("SES email error to {to}: {e}");
            false
        }
    }
}

/// Welcome email to a newly registered member (port of send_welcome_email).
pub async fn send_welcome_email(to: &str, first_name: &str) {
    let subject = "Welcome to Silent Honor Foundation";
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
.container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
.header {{ text-align: center; margin-bottom: 30px; }}
.logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; }}
.logo-accent {{ color: #B91C1C; }}
h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
p {{ color: #9CA3AF; line-height: 1.8; }}
.btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
.footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
</style></head><body>
<div class="container">
<div class="header"><div class="logo">SILENT<span class="logo-accent">HONOR</span></div></div>
<h1>Welcome, {first_name}!</h1>
<p>Thank you for joining the Silent Honor Foundation. We're honored to serve those who have served our nation.</p>
<p>Here's what you can do next:</p>
<ul style="color: #9CA3AF; line-height: 2;">
<li>Upload your DD-214 to verify your veteran status</li>
<li>Access free financial education courses</li>
<li>Connect with a certified financial counselor</li>
<li>Track your credit repair progress</li>
</ul>
<p style="text-align: center;"><a href="https://silenthonor.org/dashboard.html" class="btn">Access Your Dashboard</a></p>
<div class="footer">
<p>Silent Honor Foundation | Veterans Helping Veterans</p>
<p>If you have any questions, contact us at support@silenthonor.org</p>
</div></div></body></html>"#
    );
    let text = format!(
        "Welcome to Silent Honor Foundation, {first_name}!\n\nThank you for joining. We're honored to serve those who have served our nation.\n\nHere's what you can do next:\n- Upload your DD-214 to verify your veteran status\n- Access free financial education courses\n- Connect with a certified financial counselor\n- Track your credit repair progress\n\nVisit your dashboard: https://silenthonor.org/dashboard.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, subject, &html, &text).await;
}

/// Password-reset email (port of send_password_reset_email).
pub async fn send_password_reset_email(to: &str, first_name: &str, reset_token: &str) {
    let reset_url = format!("https://silenthonor.org/reset-password.html?token={reset_token}");
    let subject = "Reset Your Password - Silent Honor Foundation";
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
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
</style></head><body>
<div class="container">
<div class="header"><div class="logo">SILENT<span class="logo-accent">HONOR</span></div></div>
<h1>Password Reset Request</h1>
<p>Hi {first_name},</p>
<p>We received a request to reset your password. Click the button below to create a new password:</p>
<p style="text-align: center;"><a href="{reset_url}" class="btn">Reset Password</a></p>
<p class="warning">This link will expire in 1 hour. If you didn't request this reset, please ignore this email.</p>
<div class="footer"><p>Silent Honor Foundation | Veterans Helping Veterans</p></div>
</div></body></html>"#
    );
    let text = format!(
        "Password Reset Request\n\nHi {first_name},\n\nWe received a request to reset your password. Visit the link below to create a new password:\n\n{reset_url}\n\nThis link will expire in 1 hour. If you didn't request this reset, please ignore this email.\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, subject, &html, &text).await;
}

/// DD-214 approval notification (port of send_dd214_approved_email).
pub async fn send_dd214_approved_email(to: &str, first_name: &str) {
    let subject = "Your Veteran Status Has Been Verified - Silent Honor Foundation";
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
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
</style></head><body>
<div class="container">
<div class="header"><div class="logo">SILENT<span class="logo-accent">HONOR</span></div></div>
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
<p style="text-align: center;"><a href="https://silenthonor.org/dashboard.html" class="btn">Go to Dashboard</a></p>
<div class="footer"><p>Silent Honor Foundation | Veterans Helping Veterans</p></div>
</div></body></html>"#
    );
    let text = format!(
        "Your Veteran Status Has Been Verified!\n\nGreat news, {first_name}! Your DD-214 has been reviewed and your veteran status has been verified.\n\nYou now have full access to all Silent Honor Foundation services:\n- All financial education courses\n- One-on-one financial counseling\n- Credit repair guidance\n- Dispute tracking tools\n\nVisit your dashboard: https://silenthonor.org/dashboard.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, subject, &html, &text).await;
}

/// Counselor-assignment notification (port of send_counselor_assigned_email).
pub async fn send_counselor_assigned_email(to: &str, first_name: &str, counselor_name: &str) {
    let subject = "You've Been Assigned a Financial Counselor - Silent Honor Foundation";
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
.container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
.logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; text-align:center; margin-bottom:30px; }}
.logo-accent {{ color: #B91C1C; }}
h1 {{ font-family: Oswald, sans-serif; color: #C9952A; margin-bottom: 20px; }}
p {{ color: #9CA3AF; line-height: 1.8; }}
.btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
.footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151; text-align: center; font-size: 12px; color: #6B7280; }}
.counselor {{ background: rgba(201, 149, 42, 0.1); border: 1px solid #C9952A; padding: 20px; margin: 20px 0; text-align: center; }}
.counselor-name {{ font-size: 20px; color: #ffffff; font-weight: 600; }}
</style></head><body>
<div class="container">
<div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
<h1>Your Counselor is Ready!</h1>
<p>Hi {first_name},</p>
<p>You've been assigned a certified financial counselor who will guide you on your journey to financial wellness.</p>
<div class="counselor"><p style="color: #C9952A; margin-bottom: 10px;">Your Counselor</p><p class="counselor-name">{counselor_name}</p></div>
<p>Your counselor will reach out soon to schedule your first session. You can also message them directly through your dashboard.</p>
<p style="text-align: center;"><a href="https://silenthonor.org/counselor.html" class="btn">View Counselor</a></p>
<div class="footer"><p>Silent Honor Foundation | Veterans Helping Veterans</p></div>
</div></body></html>"#
    );
    let text = format!(
        "You've Been Assigned a Financial Counselor!\n\nHi {first_name},\n\nYou've been assigned a certified financial counselor: {counselor_name}. They'll reach out soon to schedule your first session.\n\nView your counselor: https://silenthonor.org/counselor.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, subject, &html, &text).await;
}

/// Dispute status-change notification (port of send_dispute_update_email).
pub async fn send_dispute_update_email(
    to: &str,
    first_name: &str,
    account_name: &str,
    bureau: &str,
    status: &str,
) {
    let (label, color) = match status {
        "sent" => ("Sent to Bureau", "#3B82F6"),
        "responded" => ("Bureau Responded", "#C9952A"),
        "resolved" => ("Resolved", "#22C55E"),
        "rejected" => ("Rejected by Bureau", "#EF4444"),
        _ => (status, "#9CA3AF"),
    };
    let subject = format!("Dispute Update: {account_name} — {label}");
    let html = format!(
        r#"<!DOCTYPE html><html><head><style>
body{{font-family:Arial,sans-serif;background:#0B1220;color:#fff;padding:40px;}}
.container{{max-width:600px;margin:0 auto;background:#111827;padding:40px;border:1px solid #374151;}}
.logo{{font-family:Oswald,sans-serif;font-size:28px;font-weight:700;text-align:center;margin-bottom:30px;}}
.logo-accent{{color:#B91C1C;}}
h1{{font-family:Oswald,sans-serif;color:#ffffff;}}
.status-badge{{display:inline-block;background:{color};color:#fff;padding:6px 16px;font-weight:700;font-size:14px;}}
.btn{{display:inline-block;background:#B91C1C;color:#fff;padding:14px 28px;text-decoration:none;font-weight:600;margin-top:20px;}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #374151;text-align:center;font-size:12px;color:#6B7280;}}
</style></head><body>
<div class="container">
<div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
<h1>Dispute Update</h1>
<p style="color:#9CA3AF;">Hi {first_name},</p>
<p style="color:#9CA3AF;">Your dispute for <strong style="color:#fff;">{account_name}</strong> with <strong style="color:#fff;">{bureau}</strong> has been updated.</p>
<p>New status: <span class="status-badge">{label}</span></p>
<p style="text-align:center;"><a href="https://silenthonor.org/dispute-tracker.html" class="btn">View Disputes</a></p>
<div class="footer"><p>Silent Honor Foundation | Veterans Helping Veterans</p></div>
</div></body></html>"#
    );
    let text =
        format!("Dispute update for {account_name} ({bureau}): {label}. View at https://silenthonor.org/dispute-tracker.html");
    send_email(to, &subject, &html, &text).await;
}

/// Generic admin notification (port of send_admin_notification). Sends to ADMIN_EMAIL.
pub async fn send_admin_notification(subject: &str, message: &str) {
    let admin = std::env::var("ADMIN_EMAIL").unwrap_or_else(|_| "admin@silenthonorfoundation.org".to_string());
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
body {{ font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px; }}
.container {{ max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151; }}
.logo {{ font-family: Oswald, sans-serif; font-size: 28px; font-weight: 700; text-align:center; margin-bottom:30px; }}
.logo-accent {{ color: #B91C1C; }}
h1 {{ font-family: Oswald, sans-serif; color: #ffffff; margin-bottom: 20px; }}
p {{ color: #9CA3AF; line-height: 1.8; }}
.btn {{ display: inline-block; background: #B91C1C; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
</style></head><body>
<div class="container">
<div class="logo">SILENT<span class="logo-accent">HONOR</span> Admin</div>
<h1>{subject}</h1>
<p>{message}</p>
<p style="text-align: center;"><a href="https://silenthonor.org/admin.html" class="btn">Go to Admin Panel</a></p>
</div></body></html>"#
    );
    send_email(&admin, &format!("[Admin] {subject}"), &html, message).await;
}

/// New-membership notification to the admin (port of send_new_membership_notification).
#[allow(clippy::too_many_arguments)]
pub async fn send_new_membership_notification(
    first_name: &str,
    last_name: &str,
    email: &str,
    phone: &str,
    branch: &str,
    service_status: &str,
    state: &str,
    challenges: &str,
) {
    let subject = format!("New Membership Application - {first_name} {last_name}");
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
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
</style></head><body>
<div class="container">
<div class="header"><div class="logo">SILENT<span class="logo-accent">HONOR</span></div></div>
<h1>New Membership Application</h1>
<p>A new veteran has submitted a membership application and is awaiting DD-214 review.</p>
<table class="info-table">
<tr><td>Name</td><td><strong>{first_name} {last_name}</strong></td></tr>
<tr><td>Email</td><td>{email}</td></tr>
<tr><td>Phone</td><td>{phone}</td></tr>
<tr><td>Branch</td><td>{branch}</td></tr>
<tr><td>Service Status</td><td>{service_status}</td></tr>
<tr><td>State</td><td>{state}</td></tr>
</table>
<div class="notes"><strong>What they need help with:</strong><br>{challenges}</div>
<p style="text-align: center;"><a href="https://silenthonor.org/admin.html" class="btn">Review Application</a></p>
</div></body></html>"#
    );
    let text = format!(
        "New Membership Application - {first_name} {last_name}\n\nA new veteran has submitted a membership application.\n\nName: {first_name} {last_name}\nEmail: {email}\nPhone: {phone}\nBranch: {branch}\nService Status: {service_status}\n\nWhat they need help with:\n{challenges}\n\nReview application: https://silenthonor.org/admin.html"
    );
    send_email(&admin_addr(), &subject, &html, &text).await;
}

/// Program-approval notification to a member (port of send_program_approved_email).
/// `counselor_name` is Some only when a counselor was assigned at approval time.
pub async fn send_program_approved_email(
    to: &str,
    first_name: &str,
    program_name: &str,
    has_counselor: bool,
    counselor_name: Option<&str>,
) {
    let subject =
        format!("Your {program_name} Application Has Been Approved — Silent Honor Foundation");
    let counselor_block = match (has_counselor, counselor_name) {
        (true, Some(name)) if !name.is_empty() => format!(
            r#"
        <div style="background:rgba(201,149,42,0.1);border:1px solid #C9952A;padding:20px;margin:20px 0;text-align:center;">
            <p style="color:#C9952A;margin-bottom:8px;">Your Assigned Counselor</p>
            <p style="font-size:18px;color:#ffffff;font-weight:600;">{name}</p>
        </div>
        <p style="color:#9CA3AF;">Your counselor will reach out soon to schedule your first session.</p>
    "#
        ),
        _ => r#"
        <p style="color:#9CA3AF;">A counselor will be assigned to you shortly. You'll receive another email once that happens.</p>
    "#
        .to_string(),
    };
    let html = format!(
        r#"
    <!DOCTYPE html><html><head><style>
        body{{font-family:Arial,sans-serif;background:#0B1220;color:#fff;padding:40px;}}
        .container{{max-width:600px;margin:0 auto;background:#111827;padding:40px;border:1px solid #374151;}}
        .logo{{font-family:Oswald,sans-serif;font-size:28px;font-weight:700;text-align:center;margin-bottom:30px;}}
        .logo-accent{{color:#B91C1C;}}
        h1{{font-family:Oswald,sans-serif;color:#22C55E;}}
        .btn{{display:inline-block;background:#B91C1C;color:#fff;padding:14px 28px;text-decoration:none;font-weight:600;margin-top:20px;}}
        .footer{{margin-top:40px;padding-top:20px;border-top:1px solid #374151;text-align:center;font-size:12px;color:#6B7280;}}
    </style></head><body>
    <div class="container">
        <div class="logo">SILENT<span class="logo-accent">HONOR</span></div>
        <h1>Application Approved!</h1>
        <p style="color:#9CA3AF;">Hi {first_name},</p>
        <p style="color:#9CA3AF;">Great news — your <strong style="color:#fff;">{program_name}</strong> application has been approved.</p>
        {counselor_block}
        <p style="text-align:center;"><a href="https://silenthonor.org/dashboard.html" class="btn">Go to Dashboard</a></p>
        <div class="footer"><p>Silent Honor Foundation | Veterans Helping Veterans</p></div>
    </div></body></html>
    "#
    );
    let text = format!(
        "Your {program_name} application has been approved, {first_name}! Visit https://silenthonor.org/dashboard.html"
    );
    send_email(to, &subject, &html, &text).await;
}

/// Welcome email to a newly created staff member, including a temporary password
/// (port of send_staff_welcome_email).
pub async fn send_staff_welcome_email(to: &str, first_name: &str, role: &str, temp_password: &str) {
    let role_title = title_case(role);
    let subject = format!("Welcome to Silent Honor Foundation - Your {role_title} Account");
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
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
</style></head><body>
<div class="container">
<div class="header"><div class="logo">SILENT<span class="logo-accent">HONOR</span></div></div>
<h1>Welcome to the Team!</h1>
<p>Hi {first_name},</p>
<p>Your {role} account has been created for the Silent Honor Foundation portal. You can now log in and start helping our veteran members.</p>
<div class="credentials">
<p><strong style="color: #ffffff;">Your Login Credentials:</strong></p>
<p>Email: <strong style="color: #ffffff;">{to}</strong></p>
<p>Temporary Password: <strong style="color: #ffffff;">{temp_password}</strong></p>
<p class="warning">Please change your password after your first login for security.</p>
</div>
<p style="text-align: center;"><a href="https://silenthonor.org/login.html" class="btn">Log In Now</a></p>
<div class="footer">
<p>Silent Honor Foundation | Veterans Helping Veterans</p>
<p>If you have questions, contact m.lugenbell@silenthonor.org</p>
</div></div></body></html>"#
    );
    let text = format!(
        "Welcome to Silent Honor Foundation!\n\nHi {first_name},\n\nYour {role} account has been created for the Silent Honor Foundation portal.\n\nYour Login Credentials:\nEmail: {to}\nTemporary Password: {temp_password}\n\nIMPORTANT: Please change your password after your first login for security.\n\nLog in at: https://silenthonor.org/login.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, &subject, &html, &text).await;
}

/// Portal-invitation email to a new counselor/staff member with a password-setup
/// link (port of send_staff_invite_email). Awaited; returns whether it was sent.
pub async fn send_staff_invite_email(to: &str, first_name: &str, role: &str, reset_token: &str) -> bool {
    let setup_url = format!("https://silenthonor.org/reset-password.html?token={reset_token}");
    let role_label = capitalize(role);
    let portal_url = if role == "counselor" {
        "https://silenthonor.org/counselor-portal.html"
    } else {
        "https://silenthonor.org/admin.html"
    };
    let subject = "You've Been Invited to the Silent Honor Staff Portal";
    let html = format!(
        r#"<!DOCTYPE html>
<html><head><style>
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
</style></head><body>
<div class="container">
<div class="header"><div class="logo">SILENT<span class="logo-accent">HONOR</span></div></div>
<h1>Welcome to the Team, {first_name}!</h1>
<p>You have been added as a <strong>{role_label}</strong> at Silent Honor Foundation. Please set up your password to access the staff portal.</p>
<div class="info-box">
<p><strong>Your portal:</strong> <a href="{portal_url}" style="color:#C9952A;">{portal_url}</a></p>
<p>Once your password is set, log in with your email address at the link above.</p>
</div>
<p style="text-align: center;"><a href="{setup_url}" class="btn">Set Up My Password</a></p>
<p class="warning">This link will expire in 24 hours. Contact your administrator if it has expired.</p>
<div class="footer"><p>Silent Honor Foundation | Veterans Helping Veterans</p></div>
</div></body></html>"#
    );
    let text = format!(
        "Welcome to Silent Honor Foundation, {first_name}!\n\nYou have been added as a {role_label}. Set up your password here:\n{setup_url}\n\nYour portal: {portal_url}\n\nThis link expires in 24 hours.\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, subject, &html, &text).await
}

/// Python `str.capitalize()`: first char upper, rest lower.
fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().collect::<String>() + &chars.as_str().to_lowercase(),
        None => String::new(),
    }
}

/// Python `str.title()`: capitalize each word.
fn title_case(s: &str) -> String {
    s.split(' ')
        .map(capitalize)
        .collect::<Vec<_>>()
        .join(" ")
}
