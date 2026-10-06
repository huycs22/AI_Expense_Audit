from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, new_id, utcnow


class ApiCall(Base):
    __tablename__ = "api_calls"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.id"), index=True)
    stage: Mapped[str]
    model: Mapped[str]
    account_scope: Mapped[str] = mapped_column(String(16), default="legacy")
    status: Mapped[str] = mapped_column(default="reserved")
    attempt: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    latency_ms: Mapped[int | None]
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    estimated_neurons: Mapped[float | None] = mapped_column(Float)
    estimated_usd: Mapped[float | None] = mapped_column(Float)
    reserved_neurons: Mapped[float] = mapped_column(Float)
    pricing_version: Mapped[str]
    usage: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None]
