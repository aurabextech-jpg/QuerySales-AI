"""One way to open an SMTP connection, shared by every sender.

Port decides the TLS mode, not the provider: 465 is implicit TLS (SMTP_SSL),
everything else (587, 25, 2525) is plain SMTP upgraded with STARTTLS. Four call
sites used to pick a mode each on their own — the settings test used STARTTLS
while the mail workspace used SMTP_SSL, so a 587 config (Gmail, Titan, Outlook)
passed "Test" and then failed every "Approve & send".
"""

from __future__ import annotations

import smtplib
import ssl

IMPLICIT_TLS_PORT = 465
DEFAULT_PORT = 587


def open_smtp(host: str, port: int | None, timeout: float) -> smtplib.SMTP:
    """Return a connected, TLS-protected SMTP client. Use it as a context manager."""
    port = port or DEFAULT_PORT
    context = ssl.create_default_context()
    if port == IMPLICIT_TLS_PORT:
        return smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    smtp = smtplib.SMTP(host, port, timeout=timeout)
    try:
        smtp.ehlo()
        # Never fall back to sending credentials in clear text.
        smtp.starttls(context=context)
        smtp.ehlo()
    except Exception:
        smtp.close()
        raise
    return smtp
