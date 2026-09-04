"""Unit tests for mail_service pure helpers (no network, no DB)."""

from email.message import EmailMessage

import pytest

from services.mail_service import (
    MailSyncError,
    derive_imap_host,
    extract_body_text,
)


def test_derive_imap_host_gmail():
    assert derive_imap_host("smtp.gmail.com") == "imap.gmail.com"


def test_derive_imap_host_generic_smtp_prefix():
    assert derive_imap_host("smtp.example.com") == "imap.example.com"


def test_derive_imap_host_no_prefix_used_as_is():
    assert derive_imap_host("mail.example.com") == "mail.example.com"


def test_derive_imap_host_none_raises():
    with pytest.raises(MailSyncError):
        derive_imap_host(None)


def test_extract_body_plain():
    msg = EmailMessage()
    msg.set_content("Hello there")
    assert extract_body_text(msg) == "Hello there"


def test_extract_body_html_fallback_strips_tags():
    msg = EmailMessage()
    msg.set_content("<p>Hi <b>bold</b></p>", subtype="html")
    text = extract_body_text(msg)
    assert "<" not in text
    assert "Hi" in text and "bold" in text


def test_extract_body_prefers_plain_part():
    msg = EmailMessage()
    msg.set_content("plain version")
    msg.add_alternative("<p>html version</p>", subtype="html")
    assert "plain version" in extract_body_text(msg)
    assert "html version" not in extract_body_text(msg)
