//! Transactional email via Amazon SES v2.
//!
//! The templates are deliberately **email-client-safe**: a white card on a light
//! background, dark high-contrast text, table-based layout, and every style
//! INLINE (Gmail/Outlook strip `<head><style>` blocks and mangle dark themes, so
//! the previous dark-theme templates rendered as unreadable low-contrast text).
//!
//! Sends are awaited by the (Lambda) callers because the execution environment
//! freezes on return; each `send_*` swallows its own errors so mail delivery
//! never fails the request. Requires `ses:SendEmail` on the Lambda role and
//! FROM_EMAIL/ADMIN_EMAIL in env (see infra/aws/lambda-api.tf).

use aws_config::BehaviorVersion;
use aws_sdk_sesv2::types::{Body, Content, Destination, EmailContent, Message};
use aws_sdk_sesv2::Client;
use once_cell::sync::OnceCell;

static FROM: OnceCell<String> = OnceCell::new();

const SITE: &str = "https://silenthonor.org";

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

// ─────────────────────────────────────────────────────────────────────────────
// Email-safe HTML building blocks (all styles inline, table-based, light theme).
// ─────────────────────────────────────────────────────────────────────────────

/// Minimal HTML escape for interpolated user data (names, emails, free text).
fn esc(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;")
}

/// Wrap inner `content` (already inline-styled) in the branded shell.
/// `heading_color` tints the H1 (e.g. green for approvals). `cta` is an optional
/// (label, url) button.
fn shell(heading: &str, heading_color: &str, content: &str, cta: Option<(&str, &str)>) -> String {
    let button = match cta {
        Some((label, url)) => format!(
            r#"<tr><td align="center" style="padding:6px 32px 8px;">
<a href="{url}" style="display:inline-block;background:#B91C1C;color:#ffffff;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;padding:14px 34px;border-radius:6px;">{label}</a>
</td></tr>"#
        ),
        None => String::new(),
    };
    format!(
        r#"<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
<tr><td style="height:4px;background:#B91C1C;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td align="center" style="padding:26px 32px 6px;">
<span style="font-family:Arial,Helvetica,sans-serif;font-size:24px;font-weight:bold;letter-spacing:1px;color:#0B1220;">SILENT<span style="color:#B91C1C;">HONOR</span></span>
</td></tr>
<tr><td style="padding:10px 32px 2px;">
<h1 style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:1.3;color:{heading_color};">{heading}</h1>
</td></tr>
<tr><td style="padding:10px 32px 6px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#374151;">
{content}
</td></tr>
{button}
<tr><td style="padding:22px 32px 26px;border-top:1px solid #e5e7eb;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;color:#6b7280;">
Silent Honor Foundation &nbsp;&middot;&nbsp; Veterans Helping Veterans
</td></tr>
</table>
</td></tr></table>
</body></html>"#
    )
}

fn para(html: &str) -> String {
    format!(r#"<p style="margin:0 0 14px;">{html}</p>"#)
}

fn bullets(items: &[&str]) -> String {
    let lis: String = items
        .iter()
        .map(|i| format!(r#"<li style="margin:5px 0;">{i}</li>"#))
        .collect();
    format!(r#"<ul style="margin:4px 0 14px;padding-left:20px;line-height:1.7;">{lis}</ul>"#)
}

fn info_table(rows: &[(&str, String)]) -> String {
    let mut trs = String::new();
    for (k, v) in rows {
        trs.push_str(&format!(
            r#"<tr><td style="padding:9px 0;border-bottom:1px solid #eef0f2;color:#6b7280;font-size:13px;width:38%;vertical-align:top;">{k}</td><td style="padding:9px 0;border-bottom:1px solid #eef0f2;color:#111827;font-size:14px;font-weight:bold;">{v}</td></tr>"#
        ));
    }
    format!(
        r#"<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 6px;">{trs}</table>"#
    )
}

/// A tinted callout box. `accent` is the left-border color.
fn note_box(accent: &str, bg: &str, inner: &str) -> String {
    format!(
        r#"<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:14px 0;"><tr><td style="background:{bg};border-left:4px solid {accent};border-radius:5px;padding:14px 16px;color:#374151;font-size:14px;line-height:1.6;">{inner}</td></tr></table>"#
    )
}

// ─────────────────────────────────────────────────────────────────────────────
// Templates
// ─────────────────────────────────────────────────────────────────────────────

/// Welcome email to a newly registered member.
pub async fn send_welcome_email(to: &str, first_name: &str) {
    let fname = esc(first_name);
    let content = format!(
        "{}{}{}",
        para("Thank you for joining the Silent Honor Foundation. We're honored to serve those who have served our nation."),
        para("Here's what you can do next:"),
        bullets(&[
            "Upload your DD-214 to verify your veteran status",
            "Access free financial education courses",
            "Connect with a certified financial counselor",
            "Track your credit repair progress",
        ]),
    );
    let html = shell(
        &format!("Welcome, {fname}!"),
        "#111827",
        &content,
        Some(("Access Your Dashboard", &format!("{SITE}/dashboard.html"))),
    );
    let text = format!(
        "Welcome to Silent Honor Foundation, {first_name}!\n\nThank you for joining. Here's what you can do next:\n- Upload your DD-214 to verify your veteran status\n- Access free financial education courses\n- Connect with a certified financial counselor\n- Track your credit repair progress\n\nDashboard: {SITE}/dashboard.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, "Welcome to Silent Honor Foundation", &html, &text).await;
}

/// Password-reset email.
pub async fn send_password_reset_email(to: &str, first_name: &str, reset_token: &str) {
    let reset_url = format!("{SITE}/reset-password.html?token={reset_token}");
    let fname = esc(first_name);
    let content = format!(
        "{}{}{}",
        para(&format!("Hi {fname},")),
        para("We received a request to reset your password. Click the button below to create a new one."),
        note_box("#f59e0b", "#fffbeb", "This link expires in 1 hour. If you didn't request a reset, you can safely ignore this email."),
    );
    let html = shell("Password Reset Request", "#111827", &content, Some(("Reset Password", &reset_url)));
    let text = format!(
        "Password Reset Request\n\nHi {first_name},\n\nWe received a request to reset your password. Visit this link to create a new one:\n{reset_url}\n\nThis link expires in 1 hour. If you didn't request it, ignore this email.\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, "Reset Your Password - Silent Honor Foundation", &html, &text).await;
}

/// DD-214 approval notification.
pub async fn send_dd214_approved_email(to: &str, first_name: &str) {
    let fname = esc(first_name);
    let content = format!(
        "{}{}{}",
        para(&format!("Great news, {fname}! Your DD-214 has been reviewed and your veteran status is verified.")),
        para("You now have full access to all Silent Honor Foundation services:"),
        bullets(&[
            "All financial education courses",
            "One-on-one financial counseling",
            "Credit repair guidance",
            "Dispute tracking tools",
        ]),
    );
    let html = shell(
        "You're Verified &#10004;",
        "#15803d",
        &content,
        Some(("Go to Dashboard", &format!("{SITE}/dashboard.html"))),
    );
    let text = format!(
        "You're Verified!\n\nGreat news, {first_name}! Your DD-214 has been reviewed and your veteran status is verified. You now have full access to all Silent Honor Foundation services.\n\nDashboard: {SITE}/dashboard.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, "Your Veteran Status Has Been Verified - Silent Honor Foundation", &html, &text).await;
}

/// Counselor-assignment notification.
pub async fn send_counselor_assigned_email(to: &str, first_name: &str, counselor_name: &str) {
    let fname = esc(first_name);
    let cname = esc(counselor_name);
    let content = format!(
        "{}{}{}{}",
        para(&format!("Hi {fname},")),
        para("You've been assigned a certified financial counselor who will guide you on your journey to financial wellness."),
        note_box("#B08D2A", "#fbf7ee", &format!(
            r#"<span style="color:#6b7280;font-size:13px;">Your Counselor</span><br><span style="color:#111827;font-size:18px;font-weight:bold;">{cname}</span>"#
        )),
        para("They'll reach out soon to schedule your first session. You can also message them from your dashboard."),
    );
    let html = shell(
        "Your Counselor is Ready",
        "#B08D2A",
        &content,
        Some(("View Counselor", &format!("{SITE}/counselor.html"))),
    );
    let text = format!(
        "You've Been Assigned a Financial Counselor!\n\nHi {first_name},\n\nYour counselor: {counselor_name}. They'll reach out soon to schedule your first session.\n\n{SITE}/counselor.html\n\nSilent Honor Foundation | Veterans Helping Veterans"
    );
    send_email(to, "You've Been Assigned a Financial Counselor - Silent Honor Foundation", &html, &text).await;
}

/// Dispute status-change notification.
pub async fn send_dispute_update_email(
    to: &str,
    first_name: &str,
    account_name: &str,
    bureau: &str,
    status: &str,
) {
    let (label, color) = match status {
        "sent" => ("Sent to Bureau", "#2563eb"),
        "responded" => ("Bureau Responded", "#B08D2A"),
        "resolved" => ("Resolved", "#15803d"),
        "rejected" => ("Rejected by Bureau", "#dc2626"),
        _ => (status, "#6b7280"),
    };
    let (fname, acct, bur) = (esc(first_name), esc(account_name), esc(bureau));
    let badge = format!(
        r#"<span style="display:inline-block;background:{color};color:#ffffff;font-size:13px;font-weight:bold;padding:6px 16px;border-radius:4px;">{label}</span>"#
    );
    let content = format!(
        "{}{}{}",
        para(&format!("Hi {fname},")),
        para(&format!(
            "Your dispute for <strong style=\"color:#111827;\">{acct}</strong> with <strong style=\"color:#111827;\">{bur}</strong> has been updated."
        )),
        para(&format!("New status: {badge}")),
    );
    let html = shell(
        "Dispute Update",
        "#111827",
        &content,
        Some(("View Disputes", &format!("{SITE}/dispute-tracker.html"))),
    );
    let text = format!(
        "Dispute update for {account_name} ({bureau}): {label}.\nView: {SITE}/dispute-tracker.html\n\nSilent Honor Foundation"
    );
    send_email(to, &format!("Dispute Update: {account_name} - {label}"), &html, &text).await;
}

/// Generic admin notification (sent to ADMIN_EMAIL).
pub async fn send_admin_notification(subject: &str, message: &str) {
    let admin = std::env::var("ADMIN_EMAIL")
        .unwrap_or_else(|_| "admin@silenthonorfoundation.org".to_string());
    let content = para(&esc(message));
    let html = shell(
        &esc(subject),
        "#111827",
        &content,
        Some(("Go to Admin Panel", &format!("{SITE}/admin.html"))),
    );
    send_email(&admin, &format!("[Admin] {subject}"), &html, message).await;
}

/// New-membership notification to the admin.
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
    let full = format!("{} {}", esc(first_name), esc(last_name));
    let rows = info_table(&[
        ("Name", full.clone()),
        ("Email", esc(email)),
        ("Phone", esc(phone)),
        ("Branch", esc(branch)),
        ("Service Status", esc(service_status)),
        ("State", esc(state)),
    ]);
    let content = format!(
        "{}{}{}",
        para("A new veteran has submitted a membership application and is awaiting DD-214 review."),
        rows,
        note_box(
            "#B08D2A",
            "#fbf7ee",
            &format!(
                r#"<strong style="color:#111827;">What they need help with</strong><br>{}"#,
                esc(challenges)
            )
        ),
    );
    let html = shell(
        "New Membership Application",
        "#B08D2A",
        &content,
        Some(("Review Application", &format!("{SITE}/admin.html"))),
    );
    let text = format!(
        "New Membership Application - {first_name} {last_name}\n\nName: {first_name} {last_name}\nEmail: {email}\nPhone: {phone}\nBranch: {branch}\nService Status: {service_status}\nState: {state}\n\nWhat they need help with:\n{challenges}\n\nReview: {SITE}/admin.html"
    );
    send_email(
        &admin_addr(),
        &format!("New Membership Application - {first_name} {last_name}"),
        &html,
        &text,
    )
    .await;
}

/// Program-approval notification to a member.
pub async fn send_program_approved_email(
    to: &str,
    first_name: &str,
    program_name: &str,
    has_counselor: bool,
    counselor_name: Option<&str>,
) {
    let fname = esc(first_name);
    let prog = esc(program_name);
    let counselor_block = match (has_counselor, counselor_name) {
        (true, Some(name)) if !name.is_empty() => format!(
            "{}{}",
            note_box("#B08D2A", "#fbf7ee", &format!(
                r#"<span style="color:#6b7280;font-size:13px;">Your Assigned Counselor</span><br><span style="color:#111827;font-size:18px;font-weight:bold;">{}</span>"#,
                esc(name)
            )),
            para("Your counselor will reach out soon to schedule your first session."),
        ),
        _ => para("A counselor will be assigned to you shortly. You'll receive another email once that happens."),
    };
    let content = format!(
        "{}{}{}",
        para(&format!("Hi {fname},")),
        para(&format!(
            "Great news &mdash; your <strong style=\"color:#111827;\">{prog}</strong> application has been approved."
        )),
        counselor_block,
    );
    let html = shell(
        "Application Approved",
        "#15803d",
        &content,
        Some(("Go to Dashboard", &format!("{SITE}/dashboard.html"))),
    );
    let text = format!(
        "Your {program_name} application has been approved, {first_name}! Visit {SITE}/dashboard.html\n\nSilent Honor Foundation"
    );
    send_email(
        to,
        &format!("Your {program_name} Application Has Been Approved - Silent Honor Foundation"),
        &html,
        &text,
    )
    .await;
}

/// Program-rejection notification to a member.
pub async fn send_program_rejected_email(
    to: &str,
    first_name: &str,
    program_name: &str,
    reason: &str,
) {
    let fname = esc(first_name);
    let prog = esc(program_name);
    let reason_block = if reason.trim().is_empty() {
        String::new()
    } else {
        note_box("#dc2626", "#fef2f2", &format!(
            r#"<strong style="color:#111827;">Reason</strong><br>{}"#,
            esc(reason)
        ))
    };
    let content = format!(
        "{}{}{}{}",
        para(&format!("Hi {fname},")),
        para(&format!(
            "Thank you for your interest in our <strong style=\"color:#111827;\">{prog}</strong> program. After review, we're unable to approve your application at this time."
        )),
        reason_block,
        para("If you have questions, please contact us at m.lugenbell@silenthonor.org."),
    );
    let html = shell("Application Update", "#111827", &content, None);
    let text = format!(
        "Application Update\n\nHi {first_name},\n\nAfter review, we're unable to approve your {program_name} application at this time.\n{}\nQuestions? m.lugenbell@silenthonor.org\n\nSilent Honor Foundation",
        if reason.trim().is_empty() { String::new() } else { format!("Reason: {reason}\n") }
    );
    send_email(
        to,
        &format!("Update on Your {program_name} Application - Silent Honor Foundation"),
        &html,
        &text,
    )
    .await;
}

/// Welcome email to a newly created staff member, including a temporary password.
pub async fn send_staff_welcome_email(to: &str, first_name: &str, role: &str, temp_password: &str) {
    let role_title = title_case(role);
    let fname = esc(first_name);
    let content = format!(
        "{}{}{}",
        para(&format!("Hi {fname},")),
        para(&format!(
            "Your {} account has been created for the Silent Honor Foundation portal. You can log in and start helping our veteran members.",
            esc(role)
        )),
        note_box("#B91C1C", "#fef2f2", &format!(
            r#"<strong style="color:#111827;">Your Login Credentials</strong><br>Email: <strong style="color:#111827;">{}</strong><br>Temporary Password: <strong style="color:#111827;">{}</strong><br><span style="color:#b45309;font-size:13px;">Please change your password after your first login.</span>"#,
            esc(to), esc(temp_password)
        )),
    );
    let html = shell(
        "Welcome to the Team",
        "#111827",
        &content,
        Some(("Log In Now", &format!("{SITE}/login.html"))),
    );
    let text = format!(
        "Welcome to Silent Honor Foundation!\n\nHi {first_name},\n\nYour {role} account has been created.\nEmail: {to}\nTemporary Password: {temp_password}\n\nPlease change your password after your first login.\nLog in: {SITE}/login.html\n\nSilent Honor Foundation"
    );
    send_email(
        to,
        &format!("Welcome to Silent Honor Foundation - Your {role_title} Account"),
        &html,
        &text,
    )
    .await;
}

/// Portal-invitation email to a new counselor/staff member. Awaited; returns
/// whether it was sent.
pub async fn send_staff_invite_email(to: &str, first_name: &str, role: &str, reset_token: &str) -> bool {
    let setup_url = format!("{SITE}/reset-password.html?token={reset_token}");
    let role_label = capitalize(role);
    let portal_url = if role == "counselor" {
        format!("{SITE}/counselor-portal.html")
    } else {
        format!("{SITE}/admin.html")
    };
    let fname = esc(first_name);
    let content = format!(
        "{}{}{}",
        para(&format!(
            "You've been added as a <strong style=\"color:#111827;\">{}</strong> at Silent Honor Foundation. Set up your password to access the staff portal.",
            esc(&role_label)
        )),
        note_box("#e5e7eb", "#f9fafb", &format!(
            r#"<strong style="color:#111827;">Your portal</strong><br><a href="{portal_url}" style="color:#B91C1C;">{portal_url}</a><br>Once your password is set, log in with your email at the link above."#
        )),
        note_box("#f59e0b", "#fffbeb", "This invite link expires in 24 hours. Contact your administrator if it has expired."),
    );
    let html = shell(
        &format!("Welcome to the Team, {fname}"),
        "#111827",
        &content,
        Some(("Set Up My Password", &setup_url)),
    );
    let text = format!(
        "Welcome to Silent Honor Foundation, {first_name}!\n\nYou've been added as a {role_label}. Set up your password:\n{setup_url}\n\nYour portal: {portal_url}\nThis link expires in 24 hours.\n\nSilent Honor Foundation"
    );
    send_email(to, "You've Been Invited to the Silent Honor Staff Portal", &html, &text).await
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
    s.split(' ').map(capitalize).collect::<Vec<_>>().join(" ")
}
