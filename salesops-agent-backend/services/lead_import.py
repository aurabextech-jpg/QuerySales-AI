"""Save discovered leads into the app's own pipeline, optionally mirroring to ERPNext.

The Leads page reads the user-scoped `leads` table (Decision D5); ERPNext is an
optional outbound copy. Before this existed the agent could only write to
ERPNext, so leads it "added to the CRM" never appeared in the app.

Runs in plain code, not through the CRM sub-agent: one tool call saves a whole
batch, with no extra model round-trips.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from db.models import Lead
from db.session import AsyncSessionLocal
from mcp_tools.erpnext import CreateLeadInput, create_erpnext_lead

logger = logging.getLogger(__name__)

MAX_LEADS_PER_SAVE = 10


class LeadToSave(BaseModel):
    company: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    city: str | None = None
    notes: str | None = Field(None, description="e.g. 'Discovery score 75 (High)'")


def _notes(lead: LeadToSave, erpnext_id: str | None) -> str | None:
    # The leads table has no phone or city column; notes keep them visible on
    # the lead page without a migration.
    parts = [
        f"Phone: {lead.phone}" if lead.phone else "",
        f"City: {lead.city}" if lead.city else "",
        lead.notes or "",
        f"ERPNext: {erpnext_id}" if erpnext_id else "",
    ]
    return "\n".join(p for p in parts if p) or None


def _summary(results: list[dict[str, Any]]) -> str:
    saved = [r for r in results if r["status"] == "saved"]
    skipped = [r["company"] for r in results if r["status"] == "skipped"]
    pushed = [f"{r['company']} ({r['erpnext_id']})" for r in saved if r.get("erpnext_id")]
    failed = [f"{r['company']}: {r['erpnext_error']}" for r in saved if r.get("erpnext_error")]
    parts = [f"Saved {len(saved)} of {len(results)} leads to the Leads page."]
    if pushed:
        parts.append("ERPNext: " + ", ".join(pushed) + ".")
    if failed:
        parts.append("ERPNext push failed for " + "; ".join(failed) + ".")
    if skipped:
        parts.append("Already in your leads (skipped): " + ", ".join(skipped) + ".")
    return " ".join(parts)


async def _existing_companies(db, user_id: str, companies: list[str]) -> set[str]:
    lowered = [c.strip().lower() for c in companies]
    rows = await db.execute(
        select(func.lower(Lead.company)).where(
            Lead.user_id == user_id, func.lower(Lead.company).in_(lowered)
        )
    )
    return set(rows.scalars().all())


async def save_leads(
    user_id: str, leads: list[LeadToSave], erpnext_creds: Any = None
) -> dict[str, Any]:
    """Insert new leads for *user_id*; push each new one to ERPNext when configured."""
    leads = leads[:MAX_LEADS_PER_SAVE]
    results: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        existing = await _existing_companies(db, user_id, [l.company for l in leads])
        for lead in leads:
            if lead.company.strip().lower() in existing:
                results.append({"company": lead.company, "status": "skipped", "reason": "already in your leads"})
                continue

            erpnext_id = None
            erpnext_error = None
            if erpnext_creds is not None:
                pushed = await create_erpnext_lead(
                    CreateLeadInput(
                        first_name=lead.company,
                        mobile_no=lead.phone or "",
                        email_id=lead.email or "",
                    ),
                    erpnext_creds,
                )
                if pushed.get("status") == "success":
                    erpnext_id = (pushed.get("data") or {}).get("name")
                else:
                    erpnext_error = pushed.get("message", "ERPNext push failed")

            row = Lead(
                user_id=user_id,
                company=lead.company.strip(),
                name=lead.contact_name,
                email=lead.email,
                website=lead.website,
                industry=lead.industry,
                status="New",
                notes=_notes(lead, erpnext_id),
            )
            db.add(row)
            existing.add(lead.company.strip().lower())
            entry: dict[str, Any] = {"company": lead.company, "status": "saved"}
            if erpnext_id:
                entry["erpnext_id"] = erpnext_id
            if erpnext_error:
                entry["erpnext_error"] = erpnext_error
            results.append(entry)

        await db.commit()

    saved = sum(1 for r in results if r["status"] == "saved")
    logger.info("save_leads user=%s saved=%d of %d", user_id[:8], saved, len(results))
    return {
        "status": "success",
        # An exact sentence for the reply: a small model once reported a fifth
        # "created" lead with an invented ERPNext ID when four were created.
        "summary": _summary(results),
        "saved": saved,
        "erpnext": "configured" if erpnext_creds is not None else "not configured (saved in app only)",
        "results": results,
    }
