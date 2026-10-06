from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import ROOT
from app.core.database import SessionLocal
from app.features.audits import routes
from app.features.audits.models import Audit
from app.features.audits.pipeline import run_stage, save_report
from app.features.documents.models import Document
from app.features.usage import service as usage_service
from app.features.usage.models import ApiCall
from app.main import app

pytestmark = pytest.mark.integration
SAMPLES = ROOT / "Expense_Audit_System_Candidate_Pack" / "Sample"


async def no_ai_job(audit_id, client):
    save_report(
        audit_id,
        {
            "findings": [],
            "unresolved_checks": ["AI intentionally not invoked in API integration test"],
        },
        "failed",
    )


def uploads():
    return [
        (role, (name, (SAMPLES / name).read_bytes(), "application/pdf"))
        for role, name in [
            ("purchase_order", "Sample_Purchase_Order.pdf"),
            ("invoice", "Sample_Invoice.pdf"),
            ("payment_request", "Sample_Payment_Request.pdf"),
        ]
    ]


def test_real_pdf_upload_persistence_history_preview_and_retry(monkeypatch):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        response = client.post("/api/audits", files=uploads())
        assert response.status_code == 202
        audit_id = response.json()["id"]
        detail = client.get(f"/api/audits/{audit_id}").json()
        assert detail["status"] == "failed"
        assert detail["assessment"] == "incomplete_analysis"
        assert any(row["id"] == audit_id for row in client.get("/api/audits").json())
        invoice = next(d for d in detail["documents"] if d["role"] == "invoice")
        document = client.get(f"/api/audits/{audit_id}/documents/{invoice['id']}").json()
        assert len(document["pages"]) == 2
        assert (
            client.get(document["pages"][1]["preview_url"]).headers["content-type"] == "image/jpeg"
        )
        assert client.get(document["files"][0]["url"]).content[:5] == b"%PDF-"
        assert client.post(f"/api/audits/{audit_id}/retry").status_code == 202
    with TestClient(app) as client:
        assert client.get(f"/api/audits/{audit_id}").json()["status"] == "failed"


def test_invalid_upload_and_wrong_document_access(monkeypatch):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        assert client.post("/api/audits", files=[]).status_code == 422
        files = uploads()
        files[0] = ("purchase_order", ("spoof.pdf", b"not a file", "application/pdf"))
        assert client.post("/api/audits", files=files).status_code == 422
        assert client.get("/api/audits/not-found").status_code == 404
        assert client.get("/api/documents/wrong/files/wrong").status_code == 404


def test_completed_legacy_report_can_be_reaudited_but_current_report_cannot(monkeypatch):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        audit_id = client.post("/api/audits", files=uploads()).json()["id"]
        with SessionLocal() as db:
            audit = db.get(Audit, audit_id)
            audit.status, audit.assessment, audit.report = (
                "completed",
                "review_required",
                {"schema_version": "v1"},
            )
            db.commit()
        assert client.get(f"/api/audits/{audit_id}").json()["verification_outdated"]
        assert client.post(f"/api/audits/{audit_id}/retry").status_code == 202
        with SessionLocal() as db:
            audit = db.get(Audit, audit_id)
            audit.status, audit.assessment, audit.report = (
                "completed",
                "review_required",
                {"schema_version": routes.REPORT_VERSION},
            )
            # A current audit contract cannot conceal an old extraction.
            for document in db.scalars(select(Document).where(Document.audit_id == audit_id)):
                document.extraction = {"schema_version": "extraction-v4-source-coverage"}
            db.commit()
        assert client.get(f"/api/audits/{audit_id}").json()["verification_outdated"]
        with SessionLocal() as db:
            for document in db.scalars(select(Document).where(Document.audit_id == audit_id)):
                document.extraction = {"schema_version": routes.SEMANTIC_VERSION}
            db.commit()
        assert not client.get(f"/api/audits/{audit_id}").json()["verification_outdated"]
        assert client.post(f"/api/audits/{audit_id}/retry").status_code == 409


@pytest.mark.asyncio
async def test_successful_stage_is_reused_without_ai():
    with SessionLocal() as db:
        audit = Audit()
        db.add(audit)
        db.commit()
        audit_id = audit.id
    operation = AsyncMock(return_value={"saved": True})
    first = await run_stage(audit_id, None, "test", "prompt", operation)
    second = await run_stage(audit_id, None, "test", "prompt", operation)
    assert first == second == {"saved": True}
    assert operation.await_count == 1


@pytest.mark.asyncio
async def test_newer_version_does_not_hide_an_older_matching_successful_stage():
    with SessionLocal() as db:
        audit = Audit()
        db.add(audit)
        db.commit()
        audit_id = audit.id
    original = AsyncMock(return_value={"source": "original"})
    revised = AsyncMock(return_value={"source": "revised"})
    await run_stage(audit_id, None, "test", "prompt", original, input_data={"version": 1})
    await run_stage(audit_id, None, "test", "prompt", revised, input_data={"version": 2})
    result = await run_stage(audit_id, None, "test", "prompt", original, input_data={"version": 1})
    assert result == {"source": "original"}
    assert original.await_count == revised.await_count == 1


def test_local_budget_and_usage_ledger(monkeypatch):
    monkeypatch.setattr(
        usage_service, "get_settings", lambda: type("Settings", (), {"daily_neuron_budget": 0})()
    )
    with pytest.raises(usage_service.BudgetExceeded):
        usage_service.reserve(None, "test", "@cf/zai-org/glm-4.7-flash", 10, 10, 1)


def test_ledger_records_reasoning_without_double_charge():
    call_id = usage_service.reserve(None, "test", "@cf/zai-org/glm-4.7-flash", 10, 10, 1)
    usage_service.finish(
        call_id,
        {
            "prompt_tokens": 1000,
            "completion_tokens": 1000,
            "completion_tokens_details": {"reasoning_tokens": 800},
        },
        123,
        "completed",
    )
    with SessionLocal() as db:
        call = db.get(ApiCall, call_id)
        assert call.estimated_neurons == 41.9
        assert call.usage["completion_tokens_details"]["reasoning_tokens"] == 800


def test_completed_but_incomplete_assessment_can_retry(monkeypatch):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with SessionLocal() as db:
        audit = Audit(status="completed", assessment="incomplete_analysis")
        db.add(audit)
        db.commit()
        audit_id = audit.id
    with TestClient(app) as client:
        assert client.post(f"/api/audits/{audit_id}/retry").status_code == 202


def test_restart_marks_pending_usage_interrupted_without_releasing_reservation():
    with SessionLocal() as db:
        call = ApiCall(
            stage="restart",
            model="@cf/zai-org/glm-4.7-flash",
            status="reserved",
            reserved_neurons=123,
            pricing_version="test",
        )
        db.add(call)
        db.commit()
        call_id = call.id
    with TestClient(app):
        pass
    with SessionLocal() as db:
        call = db.get(ApiCall, call_id)
        assert call.status == "interrupted"
        assert call.reserved_neurons == 123
        assert call.estimated_neurons is None


@pytest.mark.asyncio
async def test_source_review_failure_keeps_successful_extraction_checkpoint(monkeypatch):
    from app.features.audits import pipeline
    from app.features.documents.models import DocumentPage

    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        audit_id = client.post("/api/audits", files=uploads()).json()["id"]
    with SessionLocal() as db:
        doc = db.scalar(
            select(Document).where(Document.audit_id == audit_id, Document.role == "purchase_order")
        )
        doc.role_hint = None
        doc.role = "unclassified"
        page = db.scalar(
            select(DocumentPage)
            .where(DocumentPage.document_id == doc.id)
            .order_by(DocumentPage.number)
        )
        block = page.evidence["blocks"][0]
        doc_id = doc.id
        extraction = dict(
            document_type="purchase_order",
            mixed_document=False,
            schema_version="extraction-v4-source-coverage",
            observations=[
                dict(
                    id=doc.id + ":o1",
                    field_key="header",
                    value_type="text",
                    raw_value=block["text"],
                    quote=block["text"],
                    page_id=page.id,
                    block_ids=[block["block_id"]],
                    group_key=None,
                    unit=None,
                )
            ],
            uncertainties=[],
            page_coverage=[page.id],
        )
        db.commit()
    stage = AsyncMock(
        side_effect=[extraction, usage_service.BudgetExceeded("testing budget blocked")]
    )
    monkeypatch.setattr(pipeline, "run_stage", stage)
    with pytest.raises(usage_service.BudgetExceeded):
        await pipeline.process_document(object(), audit_id, doc_id)
    with SessionLocal() as db:
        saved = db.get(Document, doc_id)
        assert saved.role == "purchase_order"
        assert saved.extraction["processing_review_status"] == "pending"
        assert saved.extraction["observations"][0]["raw_value"] == block["text"]
        assert saved.extraction["observations"][0]["page_id"] == page.id
        audit = db.get(Audit, audit_id)
        audit.report = {"schema_version": routes.REPORT_VERSION}
        db.commit()
        assert not routes.verification_outdated(
            audit, list(db.scalars(select(Document).where(Document.audit_id == audit_id)))
        )
    assert stage.await_count == 2
