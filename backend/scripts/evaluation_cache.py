"""Evaluation-only reuse of byte-identical documents, with explicit provenance.

Changed documents always run live inference. This avoids repeatedly charging for
unchanged companion documents across synthetic variants, without hiding reuse.
"""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.features.audits.pipeline import cached_stage, run_stage, stage_fingerprint
from app.features.audits.reviewer import remap_references, review_prompt
from app.features.documents.models import Document, DocumentFile, DocumentPage
from app.features.extraction.normalization import ground
from app.features.extraction.service import extraction_prompt, load_prompt


async def seed_unchanged_documents(audit_id: str, source_audit_id: str) -> list[dict]:
    with SessionLocal() as db:
        source_documents = list(
            db.scalars(select(Document).where(Document.audit_id == source_audit_id))
        )
        target_documents = list(db.scalars(select(Document).where(Document.audit_id == audit_id)))

        def files(document):
            return list(
                db.scalars(
                    select(DocumentFile)
                    .where(DocumentFile.document_id == document.id)
                    .order_by(DocumentFile.position)
                )
            )

        def pages(document):
            return list(
                db.scalars(
                    select(DocumentPage)
                    .where(DocumentPage.document_id == document.id)
                    .order_by(DocumentPage.number)
                )
            )

        candidates = []
        for target in target_documents:
            target_hashes = [file.sha256 for file in files(target)]
            source = next(
                (d for d in source_documents if [f.sha256 for f in files(d)] == target_hashes), None
            )
            if source is not None:
                candidates.append((source, target, pages(source), pages(target)))

    reused = []
    for source, target, old_pages, new_pages in candidates:
        if len(old_pages) != len(new_pages):
            continue
        mapping = {source.id: target.id}
        for old, new in zip(old_pages, new_pages):
            mapping[old.id] = new.id
            mapping.update(
                {
                    a["block_id"]: b["block_id"]
                    for a, b in zip(old.evidence["blocks"], new.evidence["blocks"])
                }
            )
        extraction = cached_stage(
            source_audit_id,
            source.id,
            "extraction",
            stage_fingerprint(
                "extraction",
                extraction_prompt([p.evidence for p in old_pages]),
                [p.evidence for p in old_pages],
            ),
        )
        if extraction is None:
            continue
        extraction = ground(extraction, [p.evidence for p in old_pages], source.id)
        mapping.update(
            {
                o["id"]: o["id"].replace(source.id + ":", target.id + ":", 1)
                for o in extraction["observations"]
            }
        )
        new_extraction = remap_references(extraction, mapping)

        async def return_extraction():
            return new_extraction

        await run_stage(
            audit_id,
            target.id,
            "extraction",
            extraction_prompt([p.evidence for p in new_pages]),
            return_extraction,
            input_data=[p.evidence for p in new_pages],
        )
        reused.append(
            {
                "document_id": target.id,
                "stage": "extraction",
                "source_audit_id": source_audit_id,
                "source_document_id": source.id,
                "basis": "ordered SHA-256 files and matching stage fingerprint",
            }
        )
        # Source interpretation has its own version/input contract. Never use the
        # initial flat extraction as the fingerprint for a reviewed internal stage.
        semantic_input = {"extraction": extraction, "pages": [p.evidence for p in old_pages]}
        semantic = cached_stage(
            source_audit_id,
            source.id,
            "source_semantics",
            stage_fingerprint("source_semantics", load_prompt("semantics"), semantic_input),
        )
        if semantic is not None:
            mapping.update(
                {
                    o["id"]: o["id"].replace(source.id + ":", target.id + ":", 1)
                    for o in semantic["observations"]
                }
            )
            new_semantic = remap_references(semantic, mapping)

            async def return_semantic():
                return new_semantic

            await run_stage(
                audit_id,
                target.id,
                "source_semantics",
                load_prompt("semantics"),
                return_semantic,
                input_data={"extraction": new_extraction, "pages": [p.evidence for p in new_pages]},
            )
            reused.append(
                {
                    "document_id": target.id,
                    "stage": "source_semantics",
                    "source_audit_id": source_audit_id,
                    "source_document_id": source.id,
                    "basis": "ordered SHA-256 files and matching stage fingerprint",
                }
            )
            extraction, new_extraction = semantic, new_semantic
        internal = cached_stage(
            source_audit_id,
            source.id,
            "internal",
            stage_fingerprint("internal", review_prompt("internal"), extraction),
        )
        if internal is None:
            continue
        new_internal = remap_references(internal, mapping)

        async def return_internal():
            return new_internal

        await run_stage(
            audit_id,
            target.id,
            "internal",
            review_prompt("internal"),
            return_internal,
            input_data=new_extraction,
        )
        reused.append(
            {
                "document_id": target.id,
                "stage": "internal",
                "source_audit_id": source_audit_id,
                "source_document_id": source.id,
                "basis": "ordered SHA-256 files and matching stage fingerprint",
            }
        )
    return reused
