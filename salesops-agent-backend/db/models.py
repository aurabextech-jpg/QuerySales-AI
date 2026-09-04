from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey, Text,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True) # Firebase/Neon UID
    email = Column(String, unique=True, index=True)
    role = Column(String, default="sales_rep") # e.g. 'sales_rep', 'sales_manager'
    
    # Google Calendar Integration
    google_refresh_token = Column(String, nullable=True) # Should be encrypted in production
    google_calendar_connected = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    status = Column(String, default="running") # running, completed, failed
    mode = Column(String, default="simulation") # simulation, real
    workflow_type = Column(String) # e.g., lead_discovery, hot_lead_analysis
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    steps = relationship("WorkflowStep", back_populates="run")
    messages = relationship("ChatMessageLog", back_populates="run")

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"))
    step_name = Column(String)
    status = Column(String, default="pending")
    state_data = Column(JSON, nullable=True) # Persisted state
    created_at = Column(DateTime, default=datetime.utcnow)
    
    run = relationship("WorkflowRun", back_populates="steps")

class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"))
    tool_name = Column(String)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditTrace(Base):
    __tablename__ = "audit_traces"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"))
    agent_name = Column(String)
    thought_process = Column(Text, nullable=True)
    model_name = Column(String, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessageLog(Base):
    """Stores every user message and agent response for conversation history."""
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"), index=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("WorkflowRun", back_populates="messages")
