"""SQLAlchemy ORM models for QuerySales AI.

Existing tables (pre-Phase-1): users, workflow_runs, workflow_steps (unused),
tool_call_logs, audit_traces, chat_messages.

Phase 1 additions: leads, knowledge_documents, knowledge_chunks (pgvector),
user_llm_config, user_embedding_config, user_email_config, agent_events,
outreach_drafts.  WorkflowRun extended with lead_id, final_result, completed_at.

Every user-owned table carries user_id with an index.  Vector similarity search
filters by user_id inside the SQL — the column is denormalised onto
knowledge_chunks on purpose (Decision D2, plan §50).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Return a naive UTC datetime (consistent with existing DateTime columns).

    `datetime.utcnow` is deprecated in 3.12+ but still emits naive UTC which is
    what SQLAlchemy's `DateTime` column expects by default.  Wrap in a helper so
    the deprecation fix is a single-line change when it is finally removed.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ═════════════════════════════════════════════════════════════════════════════
#  EXISTING TABLES (unchanged semantics)
# ═════════════════════════════════════════════════════════════════════════════


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)  # Neon UID
    email = Column(String, unique=True, index=True)
    role = Column(String, default="sales_rep")

    # Google Calendar Integration (legacy — encrypted with Fernet)
    google_refresh_token = Column(String, nullable=True)
    google_calendar_connected = Column(Boolean, default=False)

    created_at = Column(DateTime, default=_utcnow)

    # Back-references from new tables
    leads = relationship("Lead", back_populates="user", lazy="selectin")
    llm_config = relationship("UserLLMConfig", back_populates="user", uselist=False, lazy="selectin")
    embedding_config = relationship("UserEmbeddingConfig", back_populates="user", uselist=False, lazy="selectin")
    email_config = relationship("UserEmailConfig", back_populates="user", uselist=False, lazy="selectin")
    integrations = relationship("UserIntegrationConfig", back_populates="user", lazy="selectin")


class WorkflowRun(Base):
    """A single agent run.  Shared by both the chat orchestrator (legacy) and the
    autonomous sales agent (Phase 4, workflow_type='lead_analysis')."""

    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    status = Column(String, default="running")  # running, completed, failed
    mode = Column(String, default="simulation")  # simulation, real
    workflow_type = Column(String, nullable=True)  # lead_discovery, lead_analysis, …
    created_at = Column(DateTime, default=_utcnow)

    # ── Phase 1 additions ────────────────────────────────────────────────
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)
    final_result = Column(JSON, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")
    lead = relationship("Lead", back_populates="runs")
    steps = relationship("WorkflowStep", back_populates="run")
    messages = relationship("ChatMessageLog", back_populates="run")
    events = relationship("AgentEvent", back_populates="run", order_by="AgentEvent.sequence")
    outreach_drafts = relationship("OutreachDraft", back_populates="run")


class WorkflowStep(Base):
    """Defined but unused by any code path.  Kept for backwards compatibility."""

    __tablename__ = "workflow_steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"))
    step_name = Column(String)
    status = Column(String, default="pending")
    state_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    run = relationship("WorkflowRun", back_populates="steps")


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"), index=True)
    tool_name = Column(String)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class AuditTrace(Base):
    __tablename__ = "audit_traces"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"), index=True)
    agent_name = Column(String)
    thought_process = Column(Text, nullable=True)
    model_name = Column(String, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class ChatMessageLog(Base):
    """Stores every user message and agent response for conversation history."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"), index=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    run = relationship("WorkflowRun", back_populates="messages")


# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — NEW TABLES
# ═════════════════════════════════════════════════════════════════════════════


class Lead(Base):
    """A sales lead, user-scoped.  Lives in our Postgres (Decision D5), not ERPNext."""

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_user_status", "user_id", "status"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=True)
    company = Column(String, nullable=False)
    email = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    website = Column(String, nullable=True)
    # Statuses: New · Analyzing · Qualified · Nurture · Disqualified · Contacted
    status = Column(String, default="New", nullable=False)
    score = Column(Integer, nullable=True)  # 0-100 lead quality score
    pain_points = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="leads")
    runs = relationship("WorkflowRun", back_populates="lead")
    outreach_drafts = relationship("OutreachDraft", back_populates="lead")


class KnowledgeDocument(Base):
    """An uploaded document belonging to a user.  Status tracks the ingestion
    pipeline: uploaded → extracting → chunking → embedding → indexed (or failed)."""

    __tablename__ = "knowledge_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    title = Column(String, nullable=True)
    file_type = Column(String, nullable=False)  # .txt, .md, .pdf
    content = Column(Text, nullable=True)  # Extracted raw text
    # Statuses: uploaded · extracting · chunking · embedding · indexed · failed
    status = Column(String, default="uploaded", nullable=False)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)  # User-safe message on failure
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User")
    chunks = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class KnowledgeChunk(Base):
    """A chunk of a knowledge document with its pgvector embedding.

    user_id is denormalised onto this table on purpose: vector similarity search
    must filter by user_id INSIDE the SQL without a join (plan §50, Decision D2).

    The embedding column is fixed at vector(1536).  The dimension is validated
    against 1536 when the user saves their embedding config (Phase 2).

    `metadata` is reserved by SQLAlchemy's declarative API — the column is named
    `chunk_metadata` instead.
    """

    __tablename__ = "knowledge_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    # Fixed dimension 1536 (Decision D2).  IVFFlat index is added in the migration
    # because autogenerate cannot produce the USING ivfflat clause.
    embedding = Column(Vector(1536), nullable=True)
    chunk_metadata = Column(JSON, nullable=True)  # title, filename, char_start, …
    created_at = Column(DateTime, default=_utcnow)

    document = relationship("KnowledgeDocument", back_populates="chunks")


class UserLLMConfig(Base):
    """Per-user LLM provider configuration.  API key is AES-256-GCM encrypted
    (Phase 2, Decision D3).  This row is the only source — no env fallback."""

    __tablename__ = "user_llm_config"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(
        String, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    provider_name = Column(String, nullable=False)  # e.g. "openai", "gemini", "openrouter"
    base_url = Column(String, nullable=False)
    api_key_encrypted = Column(Text, nullable=False)  # AES-256-GCM ciphertext
    model = Column(String, nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="llm_config")


class UserEmbeddingConfig(Base):
    """Per-user embedding provider configuration.

    dimension is validated against 1536 on save (Decision D2 — the stored column
    is vector(1536)).  A different value is rejected with a clear message.
    """

    __tablename__ = "user_embedding_config"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(
        String, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    provider_name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    model = Column(String, nullable=False)
    dimension = Column(Integer, default=1536, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="embedding_config")


class UserEmailConfig(Base):
    """Per-user email configuration for outreach send.

    SMTP password and OAuth tokens are AES-256-GCM encrypted.  At most one of
    (smtp_password_encrypted, access_token_encrypted) is populated per row.
    """

    __tablename__ = "user_email_config"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(
        String, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    provider = Column(String, nullable=False)  # "gmail_smtp", "gmail_oauth", …
    email_address = Column(String, nullable=False)
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_password_encrypted = Column(Text, nullable=True)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="email_config")


class AgentEvent(Base):
    """Semantic phase event emitted during an autonomous agent run.

    Drives the live analysis timeline UI (polled via GET /api/runs/{id}/events,
    Decision D6).  sequence is monotonic per run for incremental polling.

    Phases: OBSERVE · RETRIEVE · REASON · PLAN · TOOL_CALL · RESULT · COMPLETE · ERROR
    """

    __tablename__ = "agent_events"
    __table_args__ = (
        Index("ix_agent_events_run_seq", "run_id", "sequence"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(
        String, ForeignKey("workflow_runs.id"), nullable=False, index=True
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    phase = Column(String, nullable=False)  # OBSERVE, RETRIEVE, …, COMPLETE, ERROR
    title = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    run = relationship("WorkflowRun", back_populates="events")


class OutreachDraft(Base):
    """An outreach email draft generated by the agent.  Status: draft → approved → sent.
    Approval is a separate endpoint (plan §13 Tool 6).  Never sends automatically."""

    __tablename__ = "outreach_drafts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    run_id = Column(String, ForeignKey("workflow_runs.id"), nullable=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    # Statuses: draft · approved · sent · failed
    status = Column(String, default="draft", nullable=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    lead = relationship("Lead", back_populates="outreach_drafts")
    run = relationship("WorkflowRun", back_populates="outreach_drafts")


class MailMessage(Base):
    """One email in the user's Mail workspace — inbound (IMAP sync) or
    outbound (approved reply sent via SMTP).  Trash = trashed_at set."""

    __tablename__ = "mail_messages"
    __table_args__ = (
        Index("ix_mail_messages_user_dir_trashed", "user_id", "direction", "trashed_at"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    direction = Column(String, nullable=False)  # inbound | outbound
    imap_uid = Column(Integer, nullable=True)  # IMAP UID — inbound dedup key
    message_id = Column(String, nullable=True)  # RFC-822 Message-ID (threading)
    from_addr = Column(String, nullable=False, default="")
    to_addrs = Column(String, nullable=False, default="")
    subject = Column(String, nullable=False, default="")
    body_text = Column(Text, nullable=False, default="")
    received_at = Column(DateTime, default=_utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)
    trashed_at = Column(DateTime, nullable=True)
    in_reply_to_id = Column(String, ForeignKey("mail_messages.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class MailDraft(Base):
    """An editable reply draft.  Statuses: draft → sent | discarded.
    Never sent automatically — approval is a separate endpoint."""

    __tablename__ = "mail_drafts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    inbound_message_id = Column(String, ForeignKey("mail_messages.id"), nullable=True)
    run_id = Column(String, ForeignKey("workflow_runs.id"), nullable=True)
    to_addr = Column(String, nullable=False, default="")
    subject = Column(String, nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    status = Column(String, default="draft", nullable=False)
    sent_message_id = Column(String, ForeignKey("mail_messages.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class UserIntegrationConfig(Base):
    """Per-user third-party integration credentials (plan §41).

    One generic table rather than one table per provider: the field set for
    each provider is declared in ``core/integrations.py``, so adding an
    integration needs no migration.

    ``config`` holds the non-secret fields (base URLs, client IDs) as plain
    JSON so the settings UI can display them. ``secrets_encrypted`` holds a
    single AES-256-GCM blob containing a JSON object of every secret field for
    that provider — one encrypt/decrypt per provider rather than per field.
    """

    __tablename__ = "user_integration_config"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_integration_provider"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # One of core.integrations.PROVIDERS — erpnext · google_places ·
    # lead_sources · google_dork_search · google_calendar
    provider = Column(String, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    secrets_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="integrations")
