"""Lead management endpoints (plan §18, §28).

Full CRUD for user-scoped leads plus the core CTA:
POST /api/leads/{id}/analyze — triggers the autonomous sales agent.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.sales_agent import run_sales_agent
from core.security import get_current_user
from core.user_config import resolve_email_config, ConfigurationMissing
from db.models import Lead, OutreachDraft, User, WorkflowRun
from db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────


class LeadCreate(BaseModel):
    name: Optional[str] = None
    company: str
    email: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    status: str = "New"
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    pain_points: Optional[list[str]] = None
    notes: Optional[str] = None


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: Optional[str] = None
    company: str
    email: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    status: str
    score: Optional[int] = None
    pain_points: Optional[list] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LeadDetailResponse(LeadResponse):
    runs: list[dict] = []
    outreach_drafts: list[dict] = []


class AnalyzeResponse(BaseModel):
    run_id: str
    status: str
    result: Optional[dict] = None


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    search: Optional[str] = Query(None, description="Search name/company/email"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's leads with optional search and status filter."""
    query = select(Lead).where(Lead.user_id == user.id)

    if status:
        query = query.where(Lead.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Lead.name.ilike(pattern))
            | (Lead.company.ilike(pattern))
            | (Lead.email.ilike(pattern))
        )

    query = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=LeadResponse)
async def create_lead(
    body: LeadCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new lead."""
    lead = Lead(
        user_id=user.id,
        name=body.name,
        company=body.company,
        email=body.email,
        industry=body.industry,
        website=body.website,
        status=body.status,
        notes=body.notes,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get lead detail + associated runs + outreach drafts."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id)
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    # Associated runs
    runs_result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.lead_id == lead_id, WorkflowRun.user_id == user.id)
        .order_by(WorkflowRun.created_at.desc())
    )
    runs = [
        {
            "id": r.id,
            "status": r.status,
            "workflow_type": r.workflow_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "final_result": r.final_result,
        }
        for r in runs_result.scalars().all()
    ]

    # Outreach drafts
    drafts_result = await db.execute(
        select(OutreachDraft)
        .where(OutreachDraft.lead_id == lead_id, OutreachDraft.user_id == user.id)
        .order_by(OutreachDraft.created_at.desc())
    )
    drafts = [
        {
            "id": d.id,
            "subject": d.subject,
            "body": d.body,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in drafts_result.scalars().all()
    ]

    resp = LeadDetailResponse.model_validate(lead)
    resp.runs = runs
    resp.outreach_drafts = drafts
    return resp


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a lead's fields."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id)
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a lead and its associated data."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id)
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    await db.delete(lead)
    await db.commit()
    return {"deleted": True}


@router.post("/{lead_id}/analyze", response_model=AnalyzeResponse)
async def analyze_lead(
    lead_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger the autonomous sales agent to analyse a lead.

    This is the core CTA — 'Analyze with QuerySales AI'.
    """
    # Verify ownership
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id)
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        run = await run_sales_agent(
            lead_id=lead_id,
            user_id=user.id,
            db=db,
        )
        return AnalyzeResponse(
            run_id=run.id,
            status=run.status,
            result=run.final_result,
        )
    except Exception as exc:
        logger.error(
            "analyze_lead failed: lead=%s user=%s: %s",
            lead_id, user.id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Please try again.",
        )


# ── Outreach approve ──────────────────────────────────────────────────────


class ApproveResponse(BaseModel):
    id: str
    status: str
    sent: bool
    message: str


@router.post("/outreach/{draft_id}/approve", response_model=ApproveResponse)
async def approve_outreach(
    draft_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an outreach draft as approved. Attempts to send via email config.

    Sending is best-effort — approval always succeeds even when email
    is not configured (plan §13).
    """
    result = await db.execute(
        select(OutreachDraft).where(
            OutreachDraft.id == draft_id,
            OutreachDraft.user_id == user.id,
        )
    )
    draft = result.scalars().first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    draft.status = "approved"
    await db.commit()

    # Try to send — but never block the approval on it
    sent = False
    send_message = "Approved. Email not sent (no email configuration)."
    try:
        email_cfg = await resolve_email_config(user.id, db)
        if email_cfg and email_cfg.smtp_host and email_cfg.smtp_password:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(draft.body)
            msg["Subject"] = draft.subject
            msg["From"] = email_cfg.email_address
            # Get the lead email
            lead_result = await db.execute(
                select(Lead).where(Lead.id == draft.lead_id)
            )
            lead = lead_result.scalars().first()
            to_email = lead.email if lead else None

            if to_email:
                msg["To"] = to_email
                with smtplib.SMTP(
                    email_cfg.smtp_host, email_cfg.smtp_port or 587, timeout=10
                ) as smtp:
                    smtp.starttls()
                    smtp.login(email_cfg.email_address, email_cfg.smtp_password)
                    smtp.send_message(msg)
                sent = True
                draft.status = "sent"
                draft.sent_at = datetime.now()
                await db.commit()
                send_message = "Approved and sent."
            else:
                send_message = "Approved. Lead has no email address."
    except ConfigurationMissing:
        send_message = "Approved. Email not configured."
    except Exception as exc:
        logger.warning("Email send failed for draft %s: %s", draft_id, exc)
        send_message = f"Approved. Email send failed: {type(exc).__name__}"

    return ApproveResponse(
        id=draft.id,
        status=draft.status,
        sent=sent,
        message=send_message,
    )
