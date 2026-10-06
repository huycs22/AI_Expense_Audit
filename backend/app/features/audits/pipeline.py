import asyncio
import json

from sqlalchemy import delete, select

from app.core.cloudflare import CloudflareClient
from app.core.config import get_settings
from app.core.database import SessionLocal, utcnow
from app.features.audits.consolidation import consolidate_findings
from app.features.audits.models import Audit, AuditFinding, StageRun
from app.features.audits.reviewer import POLICY, review, review_prompt
from app.features.audits.schemas import REPORT_VERSION
from app.features.audits.verification import revalidate_review
from app.features.documents.models import Document, DocumentPage
from app.features.extraction.normalization import ground
from app.features.extraction.semantics import SEMANTIC_VERSION, review_source_semantics
from app.features.extraction.service import (
    extract_document,
    extraction_prompt,
    load_prompt,
    prompt_hash,
)


def update_progress(audit_id: str, stage: str):
    with SessionLocal() as db:
        audit = db.get(Audit, audit_id)
        audit.current_stage = stage
        audit.updated_at = utcnow()
        db.commit()


def cached_stage(
    audit_id: str, document_id: str | None, stage: str, fingerprint: str | None = None
) -> dict | None:
    with SessionLocal() as db:
        query = (
            select(StageRun)
            .where(
                StageRun.audit_id == audit_id,
                StageRun.document_id == document_id,
                StageRun.stage == stage,
                StageRun.status == "completed",
            )
        )
        if fingerprint is not None:
            query = query.where(StageRun.prompt_hash == fingerprint)
        run = db.scalar(query.order_by(StageRun.started_at.desc()))
        return run.payload if run else None


def stage_fingerprint(stage: str, prompt: str, input_data=None) -> str:
    settings = get_settings()
    return prompt_hash(
        prompt
        + json.dumps(
            {
                "input": input_data,
                "model": settings.cloudflare_cross_model
                if stage in {"cross", "identity_coverage"}
                else (
                    settings.cloudflare_internal_model
                    if stage in {"internal", "source_semantics"}
                    else settings.cloudflare_model
                ),
                "vision_model": settings.cloudflare_vision_model,
                "policy": POLICY,
                "schema_version": "extraction-v4-source-coverage"
                if stage == "extraction"
                else (
                    SEMANTIC_VERSION
                    if stage == "source_semantics"
                    else "v9-bounded-semantic-refinement"
                ),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )


async def run_stage(
    audit_id: str, document_id: str | None, stage: str, prompt: str, operation, input_data=None
) -> dict:
    fingerprint = stage_fingerprint(stage, prompt, input_data)
    cached = cached_stage(audit_id, document_id, stage, fingerprint)
    if cached is not None:
        return cached
    with SessionLocal() as db:
        run = StageRun(
            audit_id=audit_id,
            document_id=document_id,
            stage=stage,
            prompt_hash=fingerprint,
            version="extraction-v4"
            if stage == "extraction"
            else ("source-semantics-v1" if stage == "source_semantics" else "review-v9"),
        )
        db.add(run)
        db.commit()
        run_id = run.id
    try:
        payload = await operation()
    except Exception as exc:
        with SessionLocal() as db:
            run = db.get(StageRun, run_id)
            run.status, run.error, run.finished_at = "failed", str(exc)[:1000], utcnow()
            if getattr(exc, "partial_response", None):
                run.payload = {"diagnostic_partial_response": exc.partial_response}
            db.commit()
        raise
    with SessionLocal() as db:
        run = db.get(StageRun, run_id)
        run.status, run.payload, run.finished_at = "completed", payload, utcnow()
        db.commit()
    return payload


async def process_document(client: CloudflareClient, audit_id: str, document_id: str) -> dict:
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        role_hint = doc.role_hint
        pages = list(
            db.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document_id)
                .order_by(DocumentPage.number)
            )
        )
        evidence = [p.evidence for p in pages]
        image_paths = {p.id: p.image_path for p in pages}
    extraction = await run_stage(
        audit_id,
        document_id,
        "extraction",
        extraction_prompt(evidence),
        lambda: extract_document(
            client,
            audit_id,
            document_id,
            evidence,
            image_paths,
            on_source_read=lambda reading: save_extraction_checkpoint(
                document_id, reading, reviewed=False
            ),
        ),
        input_data=evidence,
    )
    # Reapply current conservative typing/grounding even when a saved extraction is reused.
    extraction = ground(extraction, evidence, document_id)
    save_extraction_checkpoint(document_id, extraction, reviewed=False)
    extraction = await run_stage(
        audit_id,
        document_id,
        "source_semantics",
        load_prompt("semantics"),
        lambda: review_source_semantics(
            client, audit_id, document_id, extraction, evidence, image_paths
        ),
        input_data={"extraction": extraction, "pages": evidence},
    )
    save_extraction_checkpoint(document_id, extraction, reviewed=True)
    with SessionLocal() as db:
        role = db.get(Document, document_id).role
    if (
        extraction["document_type"] not in {"purchase_order", "invoice", "payment_request"}
        or extraction["mixed_document"]
    ):
        raise ValueError(
            "Loại chứng từ chưa hỗ trợ/không xác định: "
            + extraction["document_type"]
            + ". Hồ sơ cần Đơn đặt hàng, Hóa đơn và Đề nghị thanh toán; Đề nghị mua hàng là loại khác."
        )
    if role_hint is not None and extraction["document_type"] != role_hint:
        raise ValueError(
            f"Loại chứng từ không khớp gợi ý: {role_hint} → {extraction['document_type']}"
        )
    try:
        internal = await run_stage(
            audit_id,
            document_id,
            "internal",
            review_prompt("internal"),
            lambda: review(
                client,
                audit_id,
                "internal",
                extraction["observations"],
                {
                    "document_id": document_id,
                    "document_type": role,
                    "source_pages": evidence,
                    "extraction_uncertainties": extraction["uncertainties"],
                },
            ),
            input_data=extraction,
        )
        internal = revalidate_review(internal, extraction["observations"], POLICY, "internal")
        internal["processing_status"] = "completed"
    except Exception as exc:
        # Extraction is independently usable even if interpretation fails.
        # Preserve the failed stage instead of declaring its evidence invalid.
        internal = {
            "processing_status": "failed",
            "findings": [],
            "calculations": [],
            "assessed_topics": [],
            "links": [],
            "check_definitions": [],
            "unresolved_checks": [
                f"Kiểm tra nội bộ {document_id[:8]} chưa hoàn tất: {str(exc)[:300]}"
            ],
        }
    with SessionLocal() as db:
        db.get(Document, document_id).status = internal["processing_status"]
        db.commit()
    return {
        "id": document_id,
        "role": role,
        "extraction": extraction,
        "internal": internal,
        "source_pages": evidence,
    }


def save_extraction_checkpoint(document_id: str, extraction: dict, *, reviewed: bool):
    """Publish successful reading independently of the next paid review stage.

    The stage cache remains immutable and is the retry input. Pending semantic
    interpretation is explicit; source-grounded values do not certify audit completeness.
    """
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        doc.extraction = {
            **extraction,
            "processing_review_status": "completed" if reviewed else "pending",
        }
        if doc.role_hint is None:
            doc.role = extraction["document_type"]
        doc.status = "extracted"
        db.commit()


async def run_audit(audit_id: str, client: CloudflareClient):
    with SessionLocal() as db:
        audit = db.get(Audit, audit_id)
        audit.status, audit.error = "processing", None
        audit.report, audit.assessment = {}, "incomplete_analysis"
        docs = list(
            db.scalars(select(Document).where(Document.audit_id == audit_id).order_by(Document.id))
        )
        ids = [d.id for d in docs]
        db.commit()
    report = {
        "findings": [],
        "unresolved_checks": [],
        "internal": [],
        "cross": None,
        "policy": POLICY,
        "schema_version": "v1",
    }
    try:
        update_progress(audit_id, "extraction_and_internal")
        results = await asyncio.gather(
            *(process_document(client, audit_id, doc_id) for doc_id in ids), return_exceptions=True
        )
        successful = []
        for doc_id, result in zip(ids, results):
            if isinstance(result, BaseException):
                report["unresolved_checks"].append(f"Chứng từ {doc_id[:8]}: {str(result)[:500]}")
                with SessionLocal() as db:
                    db.get(Document, doc_id).status = "failed"
                    db.commit()
            else:
                successful.append(result)
                report["internal"].append({"document_id": doc_id, **result["internal"]})
                report["findings"].extend(result["internal"]["findings"])
                report["unresolved_checks"].extend(
                    result["extraction"]["uncertainties"] + result["internal"]["unresolved_checks"]
                )
        if len(successful) == 3:
            successful.sort(key=lambda document: document["role"])
            report["internal"].sort(key=lambda result: result["document_id"])
            if {document["role"] for document in successful} != {
                "purchase_order",
                "invoice",
                "payment_request",
            }:
                raise ValueError(
                    "Loại chứng từ bị trùng hoặc thiếu; cần đúng một Đơn đặt hàng, một Hóa đơn và một Đề nghị thanh toán"
                )
            update_progress(audit_id, "cross_document")
            observations = [o for doc in successful for o in doc["extraction"]["observations"]]
            context = {
                "documents": [{"id": d["id"], "role": d["role"]} for d in successful],
                "internal_results": report["internal"],
                "source_pages": [p for d in successful for p in d["source_pages"]],
            }
            cross = await run_stage(
                audit_id,
                None,
                "cross",
                review_prompt("cross"),
                lambda: review(client, audit_id, "cross", observations, context),
                input_data={"observations": observations, "context": context},
            )
            cross = revalidate_review(cross, observations, POLICY, "cross")
            report["cross"] = cross
            report["findings"].extend(cross["findings"])
            report["unresolved_checks"].extend(cross["unresolved_checks"])
            roles = {d["role"]: d["id"] for d in successful}
            linked = {
                frozenset((link["from_document"], link["to_document"]))
                for link in cross["links"]
                if link["status"] == "supported"
            }
            required = [
                frozenset((roles["purchase_order"], roles["invoice"])),
                frozenset((roles["invoice"], roles["payment_request"])),
            ]
            if any(pair not in linked for pair in required):
                report["unresolved_checks"].append(
                    "Chưa xác minh đầy đủ liên kết PO → Invoice → Payment Request"
                )
        else:
            report["unresolved_checks"].append("Chưa đủ ba chứng từ hợp lệ để kiểm tra chéo")
        final_status = (
            "completed"
            if len(successful) == 3
            and all(
                item["internal"].get("processing_status", "completed") == "completed"
                for item in successful
            )
            else "failed"
        )
        save_report(
            audit_id,
            report,
            final_status,
            (
                "Một hoặc nhiều giai đoạn kiểm tra nội bộ chưa hoàn tất; các kết quả độc lập được giữ lại."
                if final_status == "failed"
                else None
            ),
        )
    except Exception as exc:
        report["unresolved_checks"].append(str(exc)[:1000])
        save_report(audit_id, report, "failed", str(exc)[:1000])


def save_report(audit_id: str, report: dict, status: str, error: str | None = None):
    report["unresolved_checks"] = list(dict.fromkeys(report["unresolved_checks"]))
    with SessionLocal() as db:
        observations = [
            observation
            for document in db.scalars(select(Document).where(Document.audit_id == audit_id))
            for observation in (document.extraction or {}).get("observations", [])
        ]
        report["findings"] = consolidate_findings(report["findings"], observations)
        report["schema_version"] = REPORT_VERSION
        db.execute(delete(AuditFinding).where(AuditFinding.audit_id == audit_id))
        for finding in report["findings"]:
            row = AuditFinding(
                audit_id=audit_id,
                scope=finding["scope"],
                severity=finding["severity"],
                payload=finding,
            )
            db.add(row)
            db.flush()
            finding["id"] = row.id
        audit = db.get(Audit, audit_id)
        audit.report, audit.status, audit.error = report, status, error
        audit.assessment = (
            "incomplete_analysis"
            if report["unresolved_checks"] or status != "completed"
            else (
                "review_required" if report["findings"] else "no_issues_detected_in_assessed_scope"
            )
        )
        audit.current_stage, audit.updated_at = "finished", utcnow()
        db.commit()
