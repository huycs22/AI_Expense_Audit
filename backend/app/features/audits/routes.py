from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session, utcnow
from app.features.audits.models import Audit, StageRun
from app.features.audits.pipeline import run_audit
from app.features.audits.schemas import REPORT_VERSION
from app.features.documents.models import Document, DocumentFile, DocumentPage
from app.features.documents.service import create_audit
from app.features.extraction.semantics import SEMANTIC_VERSION
from app.features.usage.models import ApiCall
from app.features.usage.service import summarize

router = APIRouter(prefix="/api/audits", tags=["audits"])
DB = Annotated[Session, Depends(get_session)]


def verification_outdated(audit: Audit, documents: list[Document]) -> bool:
    return audit.report.get("schema_version") != REPORT_VERSION or any(
        document.extraction is not None
        and document.extraction.get("processing_review_status") != "pending"
        and document.extraction.get("schema_version") != SEMANTIC_VERSION
        for document in documents
    )


def require_audit(db: Session, audit_id: str) -> Audit:
    audit = db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    return audit


@router.post("", status_code=202)
async def upload(
    request: Request,
    background: BackgroundTasks,
    purchase_order: Annotated[list[UploadFile] | None, File()] = None,
    invoice: Annotated[list[UploadFile] | None, File()] = None,
    payment_request: Annotated[list[UploadFile] | None, File()] = None,
    document_1: Annotated[list[UploadFile] | None, File()] = None,
    document_2: Annotated[list[UploadFile] | None, File()] = None,
    document_3: Annotated[list[UploadFile] | None, File()] = None,
    mode: Annotated[Literal["manual", "auto"], Form()] = "manual",
):
    try:
        manual = {
            "purchase_order": purchase_order,
            "invoice": invoice,
            "payment_request": payment_request,
        }
        automatic = {"document_1": document_1, "document_2": document_2, "document_3": document_3}
        selected, other = (automatic, manual) if mode == "auto" else (manual, automatic)
        if any(other.values()) or not all(selected.values()):
            raise ValueError(
                "Chọn đúng ba nhóm file của một chế độ tải lên; không trộn chế độ tự nhận diện và gán loại"
            )
        audit_id = await create_audit(selected, auto_classify=mode == "auto")
    except Exception as exc:
        if isinstance(exc, (ValueError, OSError)):
            raise HTTPException(422, str(exc)[:300]) from None
        raise HTTPException(
            422, "Không đọc được file: PDF mã hóa/hỏng hoặc ảnh không hợp lệ"
        ) from None
    background.add_task(run_audit, audit_id, request.app.state.ai_client)
    return {"id": audit_id, "status": "queued", "status_url": f"/api/audits/{audit_id}"}


@router.get("")
def history(db: DB, limit: int = 30, offset: int = 0):
    rows = db.scalars(
        select(Audit)
        .order_by(Audit.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    )
    return [
        {
            "id": a.id,
            "status": a.status,
            "assessment": a.assessment,
            "created_at": a.created_at,
            "finding_count": len(a.report.get("findings", [])),
        }
        for a in rows
    ]


@router.get("/{audit_id}")
def detail(audit_id: str, db: DB):
    audit = require_audit(db, audit_id)
    documents = list(db.scalars(select(Document).where(Document.audit_id == audit_id)))
    calls = list(
        db.scalars(select(ApiCall).where(ApiCall.audit_id == audit_id).order_by(ApiCall.created_at))
    )
    return {
        "id": audit.id,
        "status": audit.status,
        "assessment": audit.assessment,
        "verification_outdated": verification_outdated(audit, documents),
        "current_stage": audit.current_stage,
        "created_at": audit.created_at,
        "updated_at": audit.updated_at,
        "error": audit.error,
        "documents": [
            {
                "id": d.id,
                "role": d.role,
                "role_hint": d.role_hint,
                "status": d.status,
                "extraction": d.extraction,
            }
            for d in documents
        ],
        "report": audit.report,
        "usage": summarize(calls),
    }


@router.get("/{audit_id}/documents/{document_id}")
def document_detail(audit_id: str, document_id: str, db: DB):
    require_audit(db, audit_id)
    doc = db.get(Document, document_id)
    if doc is None or doc.audit_id != audit_id:
        raise HTTPException(404, "Không tìm thấy chứng từ")
    files = db.scalars(
        select(DocumentFile)
        .where(DocumentFile.document_id == document_id)
        .order_by(DocumentFile.position)
    )
    pages = db.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.number)
    )
    return {
        "id": doc.id,
        "role": doc.role,
        "extraction": doc.extraction,
        "files": [
            {
                "id": f.id,
                "name": f.name,
                "media_type": f.media_type,
                "url": f"/api/documents/{doc.id}/files/{f.id}",
            }
            for f in files
        ],
        "pages": [
            {
                "id": p.id,
                "number": p.number,
                "evidence": p.evidence,
                "preview_url": f"/api/documents/{doc.id}/pages/{p.number}",
            }
            for p in pages
        ],
    }


@router.post("/{audit_id}/retry", status_code=202)
def retry(audit_id: str, request: Request, background: BackgroundTasks, db: DB):
    # Lock prevents two clients enqueuing the same retry.
    audit = db.scalar(select(Audit).where(Audit.id == audit_id).with_for_update())
    if audit is None:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    if audit.status not in {"failed", "interrupted"} and not (
        audit.status == "completed"
        and (
            audit.assessment == "incomplete_analysis"
            or verification_outdated(
                audit, list(db.scalars(select(Document).where(Document.audit_id == audit_id)))
            )
        )
    ):
        raise HTTPException(409, "Chỉ thử lại hồ sơ bị lỗi, gián đoạn hoặc phân tích chưa đầy đủ")
    audit.status, audit.updated_at = "queued", utcnow()
    db.commit()
    background.add_task(run_audit, audit_id, request.app.state.ai_client)
    return {"id": audit_id, "status": "queued"}


@router.get("/{audit_id}/stages")
def stages(audit_id: str, db: DB):
    require_audit(db, audit_id)
    rows = db.scalars(
        select(StageRun).where(StageRun.audit_id == audit_id).order_by(StageRun.started_at)
    )
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "stage": r.stage,
            "status": r.status,
            "version": r.version,
            "prompt_hash": r.prompt_hash,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "error": r.error,
        }
        for r in rows
    ]
