from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, new_id, utcnow


class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(default="queued")
    assessment: Mapped[str] = mapped_column(default="incomplete_analysis")
    current_stage: Mapped[str] = mapped_column(default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    error: Mapped[str | None] = mapped_column(Text)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)


class StageRun(Base):
    __tablename__ = "stage_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    stage: Mapped[str]
    status: Mapped[str] = mapped_column(default="processing")
    version: Mapped[str] = mapped_column(default="v1")
    prompt_hash: Mapped[str | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class AuditFinding(Base):
    __tablename__ = "audit_findings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.id"), index=True)
    scope: Mapped[str]
    severity: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB)
