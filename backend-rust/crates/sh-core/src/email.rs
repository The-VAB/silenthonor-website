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

/// Low-level send. Logs and swallows errors (callers are fire-and-forget).
pub async fn send_email(to: &str, subject: &str, html: &str, text: &str) {
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
        None => return,
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
        Ok(_) => tracing::info!("email sent to {to}: {subject}"),
        Err(e) => tracing::error!("SES email error to {to}: {e}"),
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
