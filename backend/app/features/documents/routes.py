from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.features.documents.models import DocumentFile, DocumentPage

router = APIRouter(prefix="/api/documents", tags=["documents"])
DB = Annotated[Session, Depends(get_session)]


@router.get("/{document_id}/files/{file_id}")
def original(document_id: str, file_id: str, db: DB):
    source = db.get(DocumentFile, file_id)
    if source is None or source.document_id != document_id:
        raise HTTPException(404, "Không tìm thấy file")
    return FileResponse(
        source.path,
        media_type=source.media_type,
        filename=source.name,
        content_disposition_type="inline",
    )


@router.get("/{document_id}/pages/{number}")
def preview(document_id: str, number: int, db: DB):
    page = db.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id, DocumentPage.number == number
        )
    )
    if page is None:
        raise HTTPException(404, "Không tìm thấy trang")
    return FileResponse(page.image_path, media_type="image/jpeg")
