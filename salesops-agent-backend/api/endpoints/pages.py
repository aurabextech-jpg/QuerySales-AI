"""Public legal pages — Privacy Policy & Terms of Service.

These endpoints return fully styled HTML pages and require NO authentication.
They are meant to be linked from app stores, OAuth consent screens, and footers.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from core.config import settings

router = APIRouter()

_COMMON_STYLES = """\
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #0a0a0f;
    color: #e0e0e8;
    line-height: 1.75;
    -webkit-font-smoothing: antialiased;
  }

  .container {
    max-width: 780px;
    margin: 0 auto;
    padding: 60px 24px 100px;
  }

  .badge {
    display: inline-block;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 4px 14px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }

  h1 {
    font-size: 2.25rem;
    font-weight: 700;
    color: #fff;
    margin-bottom: 8px;
    letter-spacing: -0.5px;
  }

  .effective-date {
    font-size: 0.9rem;
    color: #888;
    margin-bottom: 48px;
  }

  h2 {
    font-size: 1.35rem;
    font-weight: 600;
    color: #c4b5fd;
    margin-top: 40px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(139, 92, 246, 0.2);
  }

  p { margin-bottom: 16px; color: #c0c0cc; }

  ul {
    margin: 12px 0 20px 20px;
    list-style: none;
  }

  ul li {
    position: relative;
    padding-left: 20px;
    margin-bottom: 8px;
    color: #b0b0bc;
  }

  ul li::before {
    content: '•';
    position: absolute;
    left: 0;
    color: #8b5cf6;
    font-weight: 700;
  }

  a { color: #a78bfa; text-decoration: none; }
  a:hover { text-decoration: underline; }

  .footer-note {
    margin-top: 60px;
    padding-top: 24px;
    border-top: 1px solid rgba(255,255,255,0.08);
    font-size: 0.85rem;
    color: #666;
    text-align: center;
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 32px;
    font-size: 0.9rem;
    color: #888;
  }
  .back-link:hover { color: #a78bfa; text-decoration: none; }
</style>
"""

_APP_NAME = "Salesops"
_COMPANY = "Salesops"
_CONTACT_EMAIL = "support@salesops.ai"
_EFFECTIVE_DATE = "19-May-2026"


# ── Home Page ────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def home_page():
    """Public home page explaining the app purpose and linking to policies."""
    verification_meta = ""
    if settings.GOOGLE_SITE_VERIFICATION:
        verification_meta = f'<meta name="google-site-verification" content="{settings.GOOGLE_SITE_VERIFICATION}" />'

    return HTMLResponse(content=f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_APP_NAME} — AI-Powered Sales Operations</title>
  <meta name="description" content="{_APP_NAME} is an AI-powered sales operations assistant that automates lead discovery, ERPNext CRM management, and outreach." />
  {verification_meta}
  {_COMMON_STYLES}
  <style>
    .hero {{
      text-align: center;
      padding: 80px 0 40px;
    }}
    .hero h1 {{
      font-size: 3rem;
      background: linear-gradient(135deg, #fff 30%, #a78bfa 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 24px;
      letter-spacing: -1px;
    }}
    .hero p {{
      font-size: 1.15rem;
      max-width: 600px;
      margin: 0 auto 40px;
      color: #a0a0b0;
    }}
    .features {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 24px;
      margin-bottom: 60px;
    }}
    @media (min-width: 640px) {{
      .features {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
    .feature-card {{
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 28px;
      transition: all 0.3s ease;
    }}
    .feature-card:hover {{
      transform: translateY(-2px);
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(139, 92, 246, 0.2);
    }}
    .feature-card h3 {{
      font-size: 1.1rem;
      font-weight: 600;
      color: #fff;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .feature-card p {{
      font-size: 0.95rem;
      color: #9090a0;
      line-height: 1.6;
      margin: 0;
    }}
    .cta-group {{
      display: flex;
      justify-content: center;
      gap: 16px;
      margin-bottom: 60px;
    }}
    .btn {{
      display: inline-block;
      padding: 12px 28px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.95rem;
      transition: all 0.2s ease;
      cursor: pointer;
    }}
    .btn-primary {{
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      color: #fff;
    }}
    .btn-primary:hover {{
      opacity: 0.9;
      text-decoration: none;
    }}
    .btn-secondary {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #fff;
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.08);
      text-decoration: none;
    }}
    .legal-footer {{
      display: flex;
      justify-content: center;
      gap: 24px;
      margin-top: 40px;
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
<div class="container">
  <div class="hero">
    <span class="badge">Introducing</span>
    <h1>{_APP_NAME}</h1>
    <p>
      An intelligent, autonomous sales operations assistant that simplifies lead discovery, 
      streamlines CRM management, and automates outreach workflows.
    </p>
    <div class="cta-group">
      <a href="/health" class="btn btn-primary">Check System Health</a>
      <a href="/privacy" class="btn btn-secondary">Privacy Policy</a>
    </div>
  </div>

  <h2>Purpose &amp; Capabilities</h2>
  <p style="margin-bottom: 32px;">
    {_APP_NAME} is built to serve as a bridge between public business directories, your internal 
    ERPNext CRM instance, and Google Workspace services. It empowers sales and operations teams to automate 
    time-consuming prospect research and messaging securely.
  </p>

  <div class="features">
    <div class="feature-card">
      <h3>🔍 Lead Generation</h3>
      <p>Discovers and enriches potential business leads dynamically using location, industry, and ratings criteria via Google Places.</p>
    </div>
    <div class="feature-card">
      <h3>💼 CRM Integration</h3>
      <p>Syncs prospects directly to your ERPNext instances. Organizes pipelines, tracks lead creation, and structures contact details.</p>
    </div>
    <div class="feature-card">
      <h3>✉️ Smart Outreach</h3>
      <p>Drafts personalized introductory emails and coordinates direct outreach based on lead source data.</p>
    </div>
    <div class="feature-card">
      <h3>📅 Calendar Scheduling</h3>
      <p>Checks real-time availability and schedules conflict-free calendar appointments with prospective clients automatically.</p>
    </div>
  </div>

  <h2>Application Scope &amp; OAuth Consent</h2>
  <p>
    To perform its duties, {_APP_NAME} requests permissions to access Gmail (for sending emails) 
    and Google Calendar (for scheduling appointments). Your data is treated with the highest standard of security. 
    We strictly act on your explicit prompts and commands to the assistant.
  </p>

  <div class="legal-footer">
    <a href="/privacy">Privacy Policy</a>
    <a href="/terms">Terms of Service</a>
  </div>

  <div class="footer-note">
    &copy; 2026 {_COMPANY}. All rights reserved.
  </div>
</div>
</body>
</html>
""")


@router.get("/google{{verification_code}}.html", response_class=HTMLResponse)
async def google_verification(verification_code: str):
    """Dynamic Google Search Console ownership verification file handler."""
    return HTMLResponse(content=f"google-site-verification: google{{verification_code}}.html")


# ── Privacy Policy ───────────────────────────────────────────────────────

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """Public Privacy Policy page."""
    return HTMLResponse(content=f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Privacy Policy — {_APP_NAME}</title>
  <meta name="description" content="Privacy Policy for {_APP_NAME}. Learn how we collect, use, and protect your data." />
  {_COMMON_STYLES}
</head>
<body>
<div class="container">

  <a href="/" class="back-link">← Back to {_APP_NAME}</a>
  <span class="badge">Legal</span>
  <h1>Privacy Policy</h1>
  <p class="effective-date">Effective Date: {_EFFECTIVE_DATE}</p>

  <p>
    {_COMPANY} ("we", "us", or "our") operates the <strong>{_APP_NAME}</strong> platform.
    This Privacy Policy explains how we collect, use, disclose, and safeguard your information
    when you use our application and services.
  </p>

  <h2>1. Information We Collect</h2>
  <p>We may collect the following types of information:</p>
  <ul>
    <li><strong>Account Information</strong> — Name, email address, and profile details provided during registration or Google OAuth sign-in.</li>
    <li><strong>Usage Data</strong> — Interaction logs, agent queries, tool usage metrics, and session timestamps.</li>
    <li><strong>CRM Data</strong> — Lead information, contact details, and business data you input or generate through the platform.</li>
    <li><strong>Calendar &amp; Email Data</strong> — When you connect Google services, we access calendar events and send emails on your behalf. We do not store email content beyond delivery confirmation.</li>
    <li><strong>Device Information</strong> — Browser type, IP address, and device identifiers for security and analytics purposes.</li>
  </ul>

  <h2>2. How We Use Your Information</h2>
  <ul>
    <li>To provide, operate, and improve the {_APP_NAME} platform and its AI-powered features.</li>
    <li>To manage your CRM leads, schedule meetings, and send outreach emails as directed by you.</li>
    <li>To track usage metrics (token consumption, API calls) for billing and optimization.</li>
    <li>To communicate service updates, security alerts, and support responses.</li>
    <li>To detect, prevent, and address security incidents and abuse.</li>
  </ul>

  <h2>3. Data Sharing &amp; Third Parties</h2>
  <p>We do not sell your personal information. We may share data with:</p>
  <ul>
    <li><strong>Service Providers</strong> — Google Cloud (OAuth, Calendar, Gmail APIs), ERPNext (CRM), Neon (database hosting), and AI model providers (Google Gemini, OpenRouter) for core functionality.</li>
    <li><strong>Legal Compliance</strong> — When required by law, regulation, or legal process.</li>
    <li><strong>Business Transfers</strong> — In connection with a merger, acquisition, or sale of assets.</li>
  </ul>

  <h2>4. Data Retention</h2>
  <p>
    We retain your data for as long as your account is active or as needed to provide services.
    Agent conversation logs and traces are retained for 90 days for debugging and audit purposes.
    You may request deletion of your account and associated data at any time.
  </p>

  <h2>5. Data Security</h2>
  <p>
    We implement industry-standard security measures including encrypted connections (TLS),
    hashed passwords, encrypted OAuth tokens at rest, and role-based access controls.
    However, no method of transmission over the internet is 100% secure.
  </p>

  <h2>6. Your Rights</h2>
  <ul>
    <li><strong>Access</strong> — Request a copy of your personal data.</li>
    <li><strong>Correction</strong> — Update inaccurate information.</li>
    <li><strong>Deletion</strong> — Request removal of your data.</li>
    <li><strong>Revoke Access</strong> — Disconnect Google services at any time from your Google Account settings.</li>
  </ul>

  <h2>7. Cookies &amp; Tracking</h2>
  <p>
    We use essential cookies for authentication (JWT session tokens). We do not use
    third-party advertising trackers. Analytics data is collected server-side only.
  </p>

  <h2>8. Children's Privacy</h2>
  <p>
    {_APP_NAME} is not intended for users under the age of 16. We do not knowingly
    collect personal information from children.
  </p>

  <h2>9. Changes to This Policy</h2>
  <p>
    We may update this Privacy Policy from time to time. Changes will be posted on this page
    with a revised effective date. Continued use of the platform constitutes acceptance of the updated policy.
  </p>

  <h2>10. Contact Us</h2>
  <p>
    If you have questions about this Privacy Policy, please contact us at
    <a href="mailto:{_CONTACT_EMAIL}">{_CONTACT_EMAIL}</a>.
  </p>

  <div class="footer-note">
    &copy; 2026 {_COMPANY}. All rights reserved.
  </div>

</div>
</body>
</html>
""")


# ── Terms of Service ─────────────────────────────────────────────────────

@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    """Public Terms of Service page."""
    return HTMLResponse(content=f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Terms of Service — {_APP_NAME}</title>
  <meta name="description" content="Terms of Service for {_APP_NAME}. Read about your rights and responsibilities." />
  {_COMMON_STYLES}
</head>
<body>
<div class="container">

  <a href="/" class="back-link">← Back to {_APP_NAME}</a>
  <span class="badge">Legal</span>
  <h1>Terms of Service</h1>
  <p class="effective-date">Effective Date: {_EFFECTIVE_DATE}</p>

  <p>
    Welcome to <strong>{_APP_NAME}</strong>. By accessing or using our platform,
    you agree to be bound by these Terms of Service ("Terms"). If you do not agree
    to these Terms, please do not use the platform.
  </p>

  <h2>1. Acceptance of Terms</h2>
  <p>
    By creating an account or using {_APP_NAME}, you confirm that you are at least 16 years old
    and have the legal capacity to enter into these Terms. If you are using the platform on
    behalf of an organization, you represent that you have the authority to bind that organization.
  </p>

  <h2>2. Description of Service</h2>
  <p>{_APP_NAME} is an AI-powered sales operations platform that provides:</p>
  <ul>
    <li>Automated lead generation and enrichment via Google Places API.</li>
    <li>CRM management through ERPNext integration.</li>
    <li>Email outreach and calendar scheduling via Google Workspace APIs.</li>
    <li>AI-driven pipeline analytics and recommendations.</li>
  </ul>

  <h2>3. User Accounts</h2>
  <ul>
    <li>You are responsible for maintaining the confidentiality of your account credentials.</li>
    <li>You agree to provide accurate and complete information during registration.</li>
    <li>You must notify us immediately of any unauthorized access to your account.</li>
    <li>We reserve the right to suspend or terminate accounts that violate these Terms.</li>
  </ul>

  <h2>4. Acceptable Use</h2>
  <p>You agree NOT to:</p>
  <ul>
    <li>Use the platform for any unlawful, fraudulent, or harmful purpose.</li>
    <li>Send spam, unsolicited marketing, or abusive emails through our outreach tools.</li>
    <li>Attempt to reverse-engineer, decompile, or hack the platform or its AI models.</li>
    <li>Upload malicious content or attempt to exploit system vulnerabilities.</li>
    <li>Exceed reasonable usage limits or abuse API quotas intentionally.</li>
    <li>Impersonate another person or misrepresent your affiliation with any entity.</li>
  </ul>

  <h2>5. Intellectual Property</h2>
  <p>
    All content, branding, code, and AI models comprising {_APP_NAME} are the property
    of {_COMPANY} or its licensors. You retain ownership of data you input into the platform.
    By using the platform, you grant us a limited license to process your data solely
    to provide the services.
  </p>

  <h2>6. Third-Party Services</h2>
  <p>
    {_APP_NAME} integrates with third-party services including Google APIs, ERPNext, and
    AI model providers. Your use of these integrations is also subject to the respective
    third-party terms of service. We are not responsible for the availability or
    functionality of third-party services.
  </p>

  <h2>7. Data &amp; Privacy</h2>
  <p>
    Your use of {_APP_NAME} is also governed by our
    <a href="/privacy">Privacy Policy</a>, which describes how we collect, use,
    and protect your information.
  </p>

  <h2>8. AI-Generated Content</h2>
  <p>
    {_APP_NAME} uses AI models to generate responses, recommendations, and actions.
    While we strive for accuracy, AI-generated content may contain errors or inaccuracies.
    You are responsible for reviewing and validating all AI outputs before acting on them.
    We disclaim liability for decisions made based on AI-generated content.
  </p>

  <h2>9. Service Availability</h2>
  <p>
    We aim to provide reliable service but do not guarantee 100% uptime.
    The platform may be temporarily unavailable due to maintenance, updates, or
    circumstances beyond our control. We are not liable for any losses resulting
    from service interruptions.
  </p>

  <h2>10. Limitation of Liability</h2>
  <p>
    To the maximum extent permitted by law, {_COMPANY} shall not be liable for any
    indirect, incidental, special, consequential, or punitive damages arising from
    your use of the platform, including but not limited to loss of profits, data,
    or business opportunities.
  </p>

  <h2>11. Termination</h2>
  <p>
    You may terminate your account at any time by contacting us. We may suspend or
    terminate your access if you violate these Terms or engage in abusive behavior.
    Upon termination, your right to use the platform ceases immediately.
  </p>

  <h2>12. Changes to Terms</h2>
  <p>
    We may modify these Terms at any time. Material changes will be communicated
    via email or in-app notification. Continued use of the platform after changes
    constitutes acceptance of the updated Terms.
  </p>

  <h2>13. Governing Law</h2>
  <p>
    These Terms shall be governed by and construed in accordance with the laws of Pakistan.
    Any disputes shall be resolved through arbitration in Lahore, Pakistan.
  </p>

  <h2>14. Contact Us</h2>
  <p>
    For questions about these Terms, please contact us at
    <a href="mailto:{_CONTACT_EMAIL}">{_CONTACT_EMAIL}</a>.
  </p>

  <div class="footer-note">
    &copy; 2026 {_COMPANY}. All rights reserved.
  </div>

</div>
</body>
</html>
""")
