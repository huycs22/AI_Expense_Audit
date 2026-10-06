import asyncio
import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.database import SessionLocal, new_id
from app.features.audits.models import Audit
from app.features.documents.models import Document, DocumentFile, DocumentPage
from app.features.documents.reader import inspect_type, read_pages


async def create_audit(groups: dict[str, list[UploadFile]], auto_classify: bool = False) -> str:
    if len(groups) != 3 or (
        not auto_classify and set(groups) != {"purchase_order", "invoice", "payment_request"}
    ):
        raise ValueError("Cần đúng ba nhóm chứng từ cho một hồ sơ")
    settings = get_settings()
    audit_id = new_id()
    directory = settings.storage_dir.resolve() / audit_id
    directory.mkdir(parents=True)
    written: list[Path] = []
    total_bytes = 0
    try:
        with SessionLocal() as db:
            audit = Audit(id=audit_id)
            db.add(audit)
            db.flush()
            for role, uploads in groups.items():
                if not uploads or len(uploads) > settings.max_document_pages:
                    raise ValueError("Mỗi loại chứng từ cần một PDF hoặc ảnh được sắp theo trang")
                doc = Document(
                    id=new_id(),
                    audit_id=audit_id,
                    role="unclassified" if auto_classify else role,
                    role_hint=None if auto_classify else role,
                )
                db.add(doc)
                db.flush()
                doc_dir = directory / doc.id
                doc_dir.mkdir()
                next_page = 1
                for position, upload in enumerate(uploads):
                    file_id = new_id()
                    path = doc_dir / file_id
                    size = 0
                    with path.open("wb") as output:
                        written.append(path)
                        while chunk := await upload.read(1024 * 1024):
                            size += len(chunk)
                            total_bytes += len(chunk)
                            if (
                                size > settings.max_file_mb * 1024 * 1024
                                or total_bytes > 60 * 1024 * 1024
                            ):
                                raise ValueError("File vượt 20 MB hoặc bộ hồ sơ vượt 60 MB")
                            output.write(chunk)
                    kind = await asyncio.to_thread(inspect_type, path)
                    if kind == "application/pdf" and len(uploads) != 1:
                        raise ValueError(
                            "Mỗi chứng từ chỉ nhận một PDF hoặc nhiều ảnh; không trộn PDF và ảnh trong cùng một chứng từ"
                        )
                    pages = await asyncio.to_thread(read_pages, path, kind, doc.id, next_page)
                    if next_page + len(pages) - 1 > settings.max_document_pages:
                        raise ValueError("Tài liệu vượt giới hạn số trang")
                    source = DocumentFile(
                        id=file_id,
                        document_id=doc.id,
                        name=Path((upload.filename or "document").replace("\\", "/")).name[:255],
                        media_type=kind,
                        path=str(path),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        position=position,
                    )
                    db.add(source)
                    db.flush()
                    for page in pages:
                        written.append(page.image_path)
                        db.add(
                            DocumentPage(
                                id=page.evidence["page_id"],
                                document_id=doc.id,
                                file_id=file_id,
                                number=page.number,
                                evidence=page.evidence,
                                image_path=str(page.image_path),
                            )
                        )
                    next_page += len(pages)
            db.commit()
            return audit_id
    except Exception:
        for path in written:
            if path.is_relative_to(settings.storage_dir.resolve()):
                path.unlink(missing_ok=True)
        raise
    finally:
        for uploads in groups.values():
            for upload in uploads:
                await upload.close()
