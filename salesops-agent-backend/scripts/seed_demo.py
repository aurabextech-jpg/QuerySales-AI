"""Demo seed data (Phase 6, plan §58).

Creates two users with distinct leads and knowledge documents.
Idempotent — safe to re-run (checks for existing data before inserting).

Usage:
    python -m scripts.seed_demo
    python -m scripts.seed_demo --user-a-email alice@example.com --user-b-email bob@example.com
    python -m scripts.seed_demo --skip-ingestion   # seed data only, no embedding

The script creates local user records directly. For Neon Auth users, log in
through the dashboard first (which auto-creates the local row), then run this
script with the matching email.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Lead,
    KnowledgeDocument,
    KnowledgeChunk,
    User,
)
from db.session import AsyncSessionLocal
from services.knowledge.chunk import chunk_text

logger = logging.getLogger(__name__)

# ── Default demo emails ───────────────────────────────────────────────────

DEFAULT_USER_A_EMAIL = "alice@querysales.demo"
DEFAULT_USER_B_EMAIL = "bob@querysales.demo"


# ── Knowledge document content ────────────────────────────────────────────

USER_A_DOCS = {
    "manufacturing-solutions.md": """# Manufacturing Solutions

## Overview
QuerySales provides comprehensive manufacturing solutions designed to streamline
production workflows, reduce waste, and improve quality control across your
entire operation.

## Key Features

### Inventory Visibility
Real-time inventory tracking across all warehouses and production lines.
- Automated stock level alerts when items fall below reorder points
- Multi-location inventory synchronization
- Batch and lot tracking for quality traceability
- Integration with existing ERP systems for seamless data flow

### Production Planning
Advanced scheduling and capacity planning tools.
- Drag-and-drop production schedule management
- Machine utilisation dashboards
- Bottleneck identification and resolution suggestions
- Raw material requirement forecasting

### Quality Control
Comprehensive QC modules for manufacturing environments.
- In-line inspection checkpoints with configurable rules
- Defect tracking with root cause analysis
- Statistical process control (SPC) charts
- Compliance reporting for ISO 9001, AS9100

## Benefits
- 30% reduction in inventory carrying costs
- 25% improvement in on-time delivery rates
- 40% reduction in production planning time
- Real-time visibility into every stage of manufacturing
""",

    "inventory-case-study.md": """# Case Study: Acme Manufacturing — Inventory Transformation

## Background
Acme Manufacturing is a mid-sized manufacturer of industrial components with
3 production facilities and over 200 employees. They struggled with manual
inventory tracking using spreadsheets, leading to frequent stockouts and
excess inventory.

## Challenges
- Manual spreadsheet-based inventory tracking across 3 warehouses
- No real-time visibility into stock levels
- Frequent stockouts causing production delays (average 4 per month)
- Excess inventory tying up $2.3M in working capital
- Inefficient reorder processes requiring 3 people full-time

## Solution Implemented
QuerySales Inventory Management was deployed across all 3 facilities with:
- Barcode scanning for real-time stock updates
- Automated reorder point alerts
- Multi-warehouse synchronisation dashboard
- Integration with their existing SAP ERP system
- Mobile access for warehouse staff

## Results (6 months after deployment)
- Stockouts reduced from 4/month to 0.5/month (87% reduction)
- Inventory carrying costs reduced by $890K annually
- Reorder process automated — 2 FTE redeployed to higher-value work
- On-time delivery improved from 82% to 96%
- ROI achieved in 4 months

## Testimonial
"QuerySales transformed our inventory management. We went from constant
firefighting to proactive planning. The real-time visibility alone paid
for the system in the first quarter." — VP Operations, Acme Manufacturing
""",

    "company-products.md": """# QuerySales Product Catalogue

## QuerySales CRM
AI-powered customer relationship management for sales teams.
- Lead scoring and qualification
- Automated follow-up scheduling
- Pipeline analytics and forecasting
- Integration with email and calendar

## QuerySales Inventory
Real-time inventory management for manufacturers.
- Multi-warehouse tracking
- Automated reorder alerts
- ERP integration (SAP, Oracle, Microsoft Dynamics)
- Mobile barcode scanning

## QuerySales Analytics
Business intelligence and reporting platform.
- Customisable dashboards
- Scheduled report delivery
- Predictive analytics with machine learning
- Data export and API access

## QuerySales Outreach
Personalised email outreach platform.
- AI-generated email drafts
- A/B testing and optimisation
- Send scheduling and tracking
- Compliance with CAN-SPAM and GDPR

## Pricing
- Starter: $49/user/month (CRM only)
- Professional: $129/user/month (CRM + Inventory)
- Enterprise: Custom pricing (all products + dedicated support)
- All plans include 14-day free trial

## Integration Partners
- SAP, Oracle, Microsoft Dynamics (ERP)
- Gmail, Outlook (Email)
- Slack, Teams (Communication)
- Google Calendar, Outlook Calendar (Scheduling)
""",

    "sales-playbook.md": """# Sales Playbook — Manufacturing Vertical

## Ideal Customer Profile (ICP)
- Mid-market manufacturers ($10M-$500M revenue)
- 50-500 employees
- Multiple production facilities or warehouses
- Currently using spreadsheets or legacy systems for inventory
- Pain points: stockouts, excess inventory, manual processes

## Discovery Questions
1. How do you currently track inventory across your facilities?
2. How often do stockouts cause production delays?
3. What is your current inventory carrying cost as a percentage of revenue?
4. How much time does your team spend on manual reorder processes?
5. What ERP or planning systems are you using today?
6. What would a 30% reduction in inventory costs mean for your business?

## Competitive Landscape
- **Fishbowl**: Good for small manufacturers, lacks AI features
- **Katana**: Strong production planning, weaker inventory analytics
- **NetSuite**: Enterprise-grade but expensive and complex
- **Our advantage**: AI-powered forecasting + manufacturing-specific features

## Objection Handling
- "We already have an ERP" → We integrate with all major ERPs. We add
  AI-powered analytics and mobile access that ERPs lack.
- "Too expensive" → Our average customer sees ROI in 4 months through
  reduced carrying costs and fewer stockouts.
- "We're too small" → Our Starter plan is designed for manufacturers with
  1-2 facilities. You can scale as you grow.

## Closing Techniques
- Offer a free inventory audit (our team analyses their current state)
- 14-day trial with their actual data
- Reference call with a similar manufacturer in their industry
- ROI calculator showing payback period based on their numbers
""",
}

USER_B_DOCS = {
    "healthcare-solutions.md": """# Healthcare IT Solutions

## Overview
QuerySales Healthcare provides HIPAA-compliant solutions for hospitals,
clinics, and healthcare networks.

## Products
- Patient management systems
- Appointment scheduling with automated reminders
- Electronic health record (EHR) integration
- Revenue cycle management

## Compliance
- HIPAA compliant infrastructure
- SOC 2 Type II certified
- HITECH Act compliance
- Regular third-party security audits
""",

    "healthcare-case-study.md": """# Case Study: City Hospital Network

## Challenge
A 5-hospital network struggled with patient scheduling, leading to 15%
no-show rates and $4M in lost annual revenue.

## Solution
Deployed QuerySales Healthcare scheduling module with automated SMS/email
reminders and predictive no-show scoring.

## Results
- No-show rate reduced from 15% to 6%
- Annual revenue recovered: $2.8M
- Patient satisfaction scores improved by 22%
""",
}


# ── Lead data ─────────────────────────────────────────────────────────────

USER_A_LEADS = [
    {
        "name": "John Martinez",
        "company": "Acme Manufacturing",
        "email": "jmartinez@acme-mfg.com",
        "industry": "Manufacturing",
        "website": "https://acme-mfg.com",
        "status": "New",
        "notes": "Mid-sized manufacturer, 3 facilities, interested in inventory management. Referred by existing customer.",
    },
    {
        "name": "Sarah Chen",
        "company": "PakTech Industries",
        "email": "schen@paktech.com",
        "industry": "Industrial",
        "website": "https://paktech.com",
        "status": "New",
        "notes": "Industrial packaging manufacturer. Manual sales operations, looking for CRM automation.",
    },
    {
        "name": "Ahmed Khan",
        "company": "Karachi Components Ltd",
        "email": "akhan@khi-components.pk",
        "industry": "Manufacturing",
        "website": "https://khi-components.pk",
        "status": "New",
        "notes": "Electronic components manufacturer. Supply chain inefficiency is their main pain point.",
    },
    {
        "name": "Lisa Park",
        "company": "TechVault Solutions",
        "email": "lpark@techvault.io",
        "industry": "Technology",
        "website": "https://techvault.io",
        "status": "Qualified",
        "score": 85,
        "notes": "SaaS company looking for sales automation. Already using competitor but unhappy with pricing.",
    },
    {
        "name": "Robert Williams",
        "company": "GreenLeaf Organics",
        "email": "rwilliams@greenleaf.co",
        "industry": "Agriculture",
        "website": "https://greenleaf.co",
        "status": "Nurture",
        "score": 62,
        "notes": "Organic food producer. Interested but budget cycle starts next quarter. Follow up in 3 months.",
    },
]

USER_B_LEADS = [
    {
        "name": "Dr. Emily Watson",
        "company": "City Hospital Network",
        "email": "ewatson@cityhospital.org",
        "industry": "Healthcare",
        "website": "https://cityhospital.org",
        "status": "New",
        "notes": "5-hospital network looking for patient scheduling improvements.",
    },
    {
        "name": "Mark Thompson",
        "company": "MediCare Plus",
        "email": "mthompson@medicare-plus.com",
        "industry": "Healthcare",
        "website": "https://medicare-plus.com",
        "status": "Qualified",
        "score": 78,
        "notes": "Chain of 12 clinics. Needs HIPAA-compliant CRM. Decision expected this month.",
    },
    {
        "name": "Priya Sharma",
        "company": "Wellness First Clinics",
        "email": "psharma@wellnessfirst.in",
        "industry": "Healthcare",
        "website": "https://wellnessfirst.in",
        "status": "New",
        "notes": "Growing clinic network, 8 locations. Looking at appointment scheduling solutions.",
    },
]


# ── Seed functions ────────────────────────────────────────────────────────


async def _get_or_create_user(
    db: AsyncSession, email: str, user_id: str | None = None
) -> User:
    """Look up a user by email, or create a local record."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if user:
        return user

    # Create a local user with a deterministic ID based on email
    uid = user_id or str(uuid.uuid5(uuid.NAMESPACE_URL, email))
    user = User(id=uid, email=email, role="sales_rep")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Created user: %s (%s)", email, uid)
    return user


async def _seed_leads(
    db: AsyncSession, user: User, leads_data: list[dict]
) -> int:
    """Seed leads for a user, skipping duplicates."""
    created = 0
    for lead_data in leads_data:
        # Check for duplicate by company + user
        result = await db.execute(
            select(Lead).where(
                Lead.user_id == user.id,
                Lead.company == lead_data["company"],
            )
        )
        if result.scalars().first():
            continue

        lead = Lead(user_id=user.id, **lead_data)
        db.add(lead)
        created += 1

    if created:
        await db.commit()
    return created


async def _seed_documents(
    db: AsyncSession, user: User, docs: dict[str, str]
) -> list[KnowledgeDocument]:
    """Seed knowledge documents, skipping duplicates by filename."""
    created_docs = []
    for filename, content in docs.items():
        result = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.user_id == user.id,
                KnowledgeDocument.filename == filename,
            )
        )
        if result.scalars().first():
            continue

        doc = KnowledgeDocument(
            user_id=user.id,
            filename=filename,
            title=filename.replace(".md", "").replace("-", " ").title(),
            file_type=".md",
            content=content,
            status="uploaded",
        )
        db.add(doc)
        created_docs.append(doc)

    if created_docs:
        await db.commit()
        for doc in created_docs:
            await db.refresh(doc)

    return created_docs


async def _run_ingestion(
    db: AsyncSession, docs: list[KnowledgeDocument]
) -> int:
    """Run chunking (without embedding) for seeded documents."""
    chunked = 0
    for doc in docs:
        if doc.status == "indexed":
            continue

        chunks = chunk_text(
            doc.content or "",
            title=doc.title or doc.filename,
            filename=doc.filename,
        )

        for chunk in chunks:
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    chunk_metadata=chunk.chunk_metadata,
                    # embedding is None — will be populated when ingestion runs
                )
            )

        doc.chunk_count = len(chunks)
        doc.status = "chunked"  # Not indexed until embedding runs
        chunked += 1

    if chunked:
        await db.commit()
    return chunked


# ── Main ──────────────────────────────────────────────────────────────────


async def seed(
    user_a_email: str = DEFAULT_USER_A_EMAIL,
    user_b_email: str = DEFAULT_USER_B_EMAIL,
    skip_ingestion: bool = False,
) -> None:
    """Run the full seed process."""
    async with AsyncSessionLocal() as db:
        # ── User A ────────────────────────────────────────────────────
        print(f"Seeding User A: {user_a_email}")
        user_a = await _get_or_create_user(db, user_a_email)

        leads_a = await _seed_leads(db, user_a, USER_A_LEADS)
        print(f"  Leads created: {leads_a} ({len(USER_A_LEADS)} total defined)")

        docs_a = await _seed_documents(db, user_a, USER_A_DOCS)
        print(f"  Documents created: {len(docs_a)} ({len(USER_A_DOCS)} total defined)")

        if not skip_ingestion and docs_a:
            chunked = await _run_ingestion(db, docs_a)
            print(f"  Documents chunked: {chunked}")

        # ── User B ────────────────────────────────────────────────────
        print(f"\nSeeding User B: {user_b_email}")
        user_b = await _get_or_create_user(db, user_b_email)

        leads_b = await _seed_leads(db, user_b, USER_B_LEADS)
        print(f"  Leads created: {leads_b} ({len(USER_B_LEADS)} total defined)")

        docs_b = await _seed_documents(db, user_b, USER_B_DOCS)
        print(f"  Documents created: {len(docs_b)} ({len(USER_B_DOCS)} total defined)")

        if not skip_ingestion and docs_b:
            chunked = await _run_ingestion(db, docs_b)
            print(f"  Documents chunked: {chunked}")

        # ── Summary ───────────────────────────────────────────────────
        lead_count_a = await db.execute(
            select(func.count(Lead.id)).where(Lead.user_id == user_a.id)
        )
        lead_count_b = await db.execute(
            select(func.count(Lead.id)).where(Lead.user_id == user_b.id)
        )
        doc_count_a = await db.execute(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.user_id == user_a.id)
        )
        doc_count_b = await db.execute(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.user_id == user_b.id)
        )

        print(f"\n{'='*60}")
        print(f"User A ({user_a_email}):")
        print(f"  Leads: {lead_count_a.scalar()}")
        print(f"  Documents: {doc_count_a.scalar()}")
        print(f"\nUser B ({user_b_email}):")
        print(f"  Leads: {lead_count_b.scalar()}")
        print(f"  Documents: {doc_count_b.scalar()}")

        if skip_ingestion:
            print("\nNote: Ingestion skipped. Documents are chunked but not embedded.")
            print("Run the ingestion via the API: POST /api/knowledge/{id}/process")
        else:
            print("\nNote: Documents are chunked but embeddings require a live API call.")
            print("To embed: configure embedding settings, then POST /api/knowledge/{id}/process")

        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for QuerySales AI")
    parser.add_argument(
        "--user-a-email",
        default=DEFAULT_USER_A_EMAIL,
        help=f"Email for User A (default: {DEFAULT_USER_A_EMAIL})",
    )
    parser.add_argument(
        "--user-b-email",
        default=DEFAULT_USER_B_EMAIL,
        help=f"Email for User B (default: {DEFAULT_USER_B_EMAIL})",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip document chunking/ingestion",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    asyncio.run(
        seed(
            user_a_email=args.user_a_email,
            user_b_email=args.user_b_email,
            skip_ingestion=args.skip_ingestion,
        )
    )


if __name__ == "__main__":
    main()
