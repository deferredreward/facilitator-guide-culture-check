"""
Email/SMS notification helper using SMTP.

Reads credentials from environment:
- EMAIL_ADDRESS
- EMAIL_APP_PASSWORD

Optional overrides:
- SMTP_SERVER (default inferred from EMAIL_ADDRESS domain)
- SMTP_PORT (default 587)
- NOTIFY_SMS_TO (default 4782274867@vtext.com)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def _infer_smtp_server(email_address: str) -> str:
    domain = (email_address.split("@", 1)[1] if "@" in email_address else "").lower()
    if domain in ("gmail.com", "googlemail.com"):
        return "smtp.gmail.com"
    if domain in ("outlook.com", "hotmail.com", "live.com", "office365.com"):
        return "smtp.office365.com"
    if domain in ("yahoo.com", "yahoo.co.uk"):
        return "smtp.mail.yahoo.com"
    # Fallback to Gmail if unknown
    return "smtp.gmail.com"


def send_page_completion_notification(page_id: str, page_title: str, success: bool, 
                                     ai_models: dict, current_page: int, total_pages: int, 
                                     error_message: str | None = None) -> None:
    """Send SMS notification when a page processing is completed"""
    sender = os.getenv("EMAIL_ADDRESS", "").strip()
    app_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()
    recipient = os.getenv("NOTIFY_SMS_TO", "4782274867@vtext.com").strip()

    if not sender or not app_password or not recipient:
        # Silent no-op if not configured
        print("Notification skipped: EMAIL_ADDRESS/EMAIL_APP_PASSWORD/NOTIFY_SMS_TO not fully configured.")
        return

    server = os.getenv("SMTP_SERVER") or _infer_smtp_server(sender)
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except Exception:
        port = 587
    use_ssl_env = os.getenv("SMTP_USE_SSL", "").strip().lower() in ("1", "true", "yes", "on")
    use_ssl = use_ssl_env or port == 465

    # Create short, informative SMS message
    status = "✅" if success else "❌"
    progress = f"({current_page}/{total_pages})"
    title_short = page_title[:40] + "..." if len(page_title) > 40 else page_title
    
    if success:
        models = f"AI:{ai_models.get('reading', 'N/A')}"
        subject = f"FG {status} {progress} {title_short}"
        body = f"FG Page {progress} completed: {title_short} using {models}"
    else:
        subject = f"FG {status} {progress} FAILED {title_short}"
        error_short = error_message[:60] + "..." if error_message and len(error_message) > 60 else error_message
        body = f"FG Page {progress} FAILED: {title_short} - {error_short}"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(server, port, context=context, timeout=30) as smtp:
                smtp.login(sender, app_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(sender, app_password)
                smtp.send_message(msg)
        print(f"📱 SMS sent: {subject}")
    except Exception as exc:
        print(f"❌ SMS failed: {exc}")

def send_batch_completion_notification(total_pages: int, completed_pages: int, 
                                     failed_pages: int, ai_models: dict) -> None:
    """Send SMS notification when entire batch processing is completed"""
    sender = os.getenv("EMAIL_ADDRESS", "").strip()
    app_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()
    recipient = os.getenv("NOTIFY_SMS_TO", "4782274867@vtext.com").strip()

    if not sender or not app_password or not recipient:
        print("Notification skipped: EMAIL_ADDRESS/EMAIL_APP_PASSWORD/NOTIFY_SMS_TO not fully configured.")
        return

    server = os.getenv("SMTP_SERVER") or _infer_smtp_server(sender)
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except Exception:
        port = 587
    use_ssl_env = os.getenv("SMTP_USE_SSL", "").strip().lower() in ("1", "true", "yes", "on")
    use_ssl = use_ssl_env or port == 465

    # Create batch completion summary
    if failed_pages == 0:
        status = "🎉"
        subject = f"FG Batch Complete {status} {completed_pages}/{total_pages} success"
        body = f"FG Batch processing complete! All {completed_pages} pages processed successfully using {ai_models.get('reading', 'N/A')}"
    else:
        status = "⚠️"
        subject = f"FG Batch Complete {status} {completed_pages}/{total_pages} ({failed_pages} failed)"
        body = f"FG Batch processing complete: {completed_pages} success, {failed_pages} failed out of {total_pages} total"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(server, port, context=context, timeout=30) as smtp:
                smtp.login(sender, app_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(sender, app_password)
                smtp.send_message(msg)
        print(f"📱 Batch SMS sent: {subject}")
    except Exception as exc:
        print(f"❌ Batch SMS failed: {exc}")

def send_job_notification(provider: str, model: str, success: bool, error_message: str | None = None) -> None:
    sender = os.getenv("EMAIL_ADDRESS", "").strip()
    app_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()
    recipient = os.getenv("NOTIFY_SMS_TO", "4782274867@vtext.com").strip()

    if not sender or not app_password or not recipient:
        # Silent no-op if not configured
        print("Notification skipped: EMAIL_ADDRESS/EMAIL_APP_PASSWORD/NOTIFY_SMS_TO not fully configured.")
        return

    server = os.getenv("SMTP_SERVER") or _infer_smtp_server(sender)
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except Exception:
        port = 587
    use_ssl_env = os.getenv("SMTP_USE_SSL", "").strip().lower() in ("1", "true", "yes", "on")
    use_ssl = use_ssl_env or port == 465

    status = "completed without errors" if success else "completed with errors"
    subject = f"ai_prompt_improver job to {provider}/{model} {status}"
    body = subject
    if error_message:
        # keep SMS short
        body = f"{subject}: {error_message[:140]}"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(server, port, context=context, timeout=30) as smtp:
                smtp.login(sender, app_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(sender, app_password)
                smtp.send_message(msg)
        print(f"Notification sent to {recipient}: {subject}")
    except Exception as exc:
        print(f"Notification failed: {exc}")


def send_system_notification(title: str, message: str) -> None:
    """Send system notification (Windows toast notification)"""
    try:
        # Try to use plyer for cross-platform notifications
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Facilitator Guide",
            timeout=5
        )
        print(f"📢 System notification: {title}")
    except ImportError:
        print("System notifications unavailable (install plyer: pip install plyer)")
    except Exception as exc:
        print(f"System notification failed: {exc}")

__all__ = ["send_job_notification", "send_page_completion_notification", "send_batch_completion_notification", "send_system_notification"]



