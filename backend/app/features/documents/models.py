from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, new_id


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.id"), index=True)
    role: Mapped[str]
    role_hint: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="uploaded")
    extraction: Mapped[dict | None] = mapped_column(JSONB)


class DocumentFile(Base):
    __tablename__ = "document_files"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    name: Mapped[str]
    media_type: Mapped[str]
    path: Mapped[str]
    sha256: Mapped[str]
    position: Mapped[int]


class DocumentPage(Base):
    __tablename__ = "document_pages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("document_files.id"))
    number: Mapped[int]
    evidence: Mapped[dict] = mapped_column(JSONB)
    image_path: Mapped[str]
