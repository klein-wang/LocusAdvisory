import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_USE_TLS, DEV_EMAIL_MODE, FEEDBACK_TO_EMAIL,
)

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_body: str, plain_body: str = None) -> bool:
    if DEV_EMAIL_MODE:
        logger.warning(
            f"[DEV MODE] Would send email to {to_email}: subject='{subject}', body preview: {plain_body or html_body[:200]}"
        )
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM_EMAIL
    msg["To"] = to_email

    if plain_body:
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.ehlo()
        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
        if SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_verification_code(to_email: str, code: str, purpose: str = "register") -> bool:
    purpose_label = "register your LocusAdvisory account" if purpose == "register" else "reset your LocusAdvisory password"
    subject = f"LocusAdvisory - Verification Code"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
        <div style="background: #f4f6fb; border-radius: 12px; padding: 32px; border: 1px solid #e5e7eb;">
            <h2 style="color: #1e40af; margin: 0 0 16px 0; font-size: 20px;">LocusAdvisory</h2>
            <p style="color: #374151; margin: 0 0 16px 0;">Use this code to {purpose_label}:</p>
            <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #1e40af; text-align: center; padding: 16px; background: #dbeafe; border-radius: 10px; margin: 16px 0;">{code}</div>
            <p style="color: #6b7280; font-size: 13px; margin: 16px 0 0 0;">This code expires in 15 minutes. If you didn't request this, please ignore this email.</p>
        </div>
    </div>
    """
    plain = f"LocusAdvisory Verification Code: {code}\nUse this code to {purpose_label}. Expires in 15 minutes."
    return send_email(to_email, subject, html, plain)


def send_feedback_notification(name: str, email: str, message: str, rating: int = None) -> bool:
    to_addr = FEEDBACK_TO_EMAIL
    if not to_addr:
        logger.warning(f"[DEV MODE] Would forward feedback: name={name}, email={email}, rating={rating}, message={message[:200]}")
        return True
    subject = f"[LocusAdvisory Feedback] from {name or 'Anonymous'}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">New Feedback Received</h2>
        <table style="border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 6px 12px; background: #f4f6fb; border: 1px solid #e5e7eb; font-weight: 600;">Name</td><td style="padding: 6px 12px; border: 1px solid #e5e7eb;">{name or 'Anonymous'}</td></tr>
            <tr><td style="padding: 6px 12px; background: #f4f6fb; border: 1px solid #e5e7eb; font-weight: 600;">Email</td><td style="padding: 6px 12px; border: 1px solid #e5e7eb;">{email}</td></tr>
            <tr><td style="padding: 6px 12px; background: #f4f6fb; border: 1px solid #e5e7eb; font-weight: 600;">Rating</td><td style="padding: 6px 12px; border: 1px solid #e5e7eb;">{'★' * (rating or 0) if rating else 'N/A'}</td></tr>
        </table>
        <div style="background: #f4f6fb; border-radius: 8px; padding: 16px; border: 1px solid #e5e7eb;">
            <strong>Message:</strong>
            <p style="margin: 8px 0 0 0; white-space: pre-wrap;">{message}</p>
        </div>
    </div>
    """
    plain = f"Feedback from {name} ({email}):\nRating: {rating}\n\n{message}"
    return send_email(to_addr, subject, html, plain)