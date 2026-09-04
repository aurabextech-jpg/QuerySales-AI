"""Gmail SMTP MCP tool adapter.

Sends real emails via Gmail using App Password + SMTP (TLS).
All calls hit the live SMTP server — no simulation mode.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    creds: Any = None,
) -> dict[str, Any]:
    """Send an email via Gmail SMTP.

    Args:
        to_email: Recipient address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        Dict with status and message.
    """
    # Credentials come from the caller's own email configuration — there is
    # no shared mailbox to fall back to (plan §54 Option A).
    gmail_user = getattr(creds, "email_address", "") if creds else ""
    gmail_password = getattr(creds, "smtp_password", "") if creds else ""
    smtp_host = getattr(creds, "smtp_host", None) or "smtp.gmail.com"
    smtp_port = getattr(creds, "smtp_port", None) or 587

    if not gmail_user or not gmail_password:
        return {
            "status": "error",
            "reason": "not_configured",
            "message": (
                "No email account configured. Add your SMTP details in "
                "Settings -> Email / Outreach."
            ),
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = gmail_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        logger.info("send_email: sent")
        return {
            "status": "success",
            "message": f"Email sent to {to_email}",
            "data": {"to": to_email, "subject": subject},
        }

    except smtplib.SMTPAuthenticationError:
        return {
            "status": "error",
            "message": "Gmail authentication failed — check GMAIL_USER and GMAIL_APP_PASSWORD",
        }
    except Exception as exc:
        logger.error("send_email error: %s", exc)
        return {"status": "error", "message": str(exc)}
