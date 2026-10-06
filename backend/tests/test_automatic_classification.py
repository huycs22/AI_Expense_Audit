"""Real uploads/persistence with stubbed inference; not a live model benchmark."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_api_integration import no_ai_job, uploads

from app.core.cloudflare import ProviderError
from app.core.database import SessionLocal
from app.features.audits import pipeline, routes
from app.features.audits.models import Audit
from app.features.documents.models import Document
from app.main import app

pytestmark = pytest.mark.integration


def automatic_uploads():
    # Opaque names and deliberately reversed document order.
    ordered = list(reversed(uploads()))
    return [
        (f"document_{index + 1}", (f"opaque-{index}.pdf", content[1][1], "application/pdf"))
        for index, content in enumerate(ordered)
    ]


def test_automatic_upload_preserves_boundaries_without_assigning_type_hints(monkeypatch):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        response = client.post("/api/audits", data={"mode": "auto"}, files=automatic_uploads())
        assert response.status_code == 202
        detail = client.get(f"/api/audits/{response.json()['id']}").json()
        assert len(detail["documents"]) == 3
        assert all(
            d["role"] == "unclassified" and d["role_hint"] is None for d in detail["documents"]
        )
        assert client.post("/api/audits", data={"mode": "auto"}, files=uploads()).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "types,expected_cross_calls",
    [
        (["invoice", "payment_request", "purchase_order"], 1),
        (["invoice", "invoice", "purchase_order"], 0),
        (["invoice", "purchase_request", "purchase_order"], 0),
        (["invoice", "unknown", "purchase_order"], 0),
    ],
)
async def test_ai_types_assign_roles_and_invalid_sets_never_cross_audit(
    monkeypatch, types, expected_cross_calls
):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        audit_id = client.post(
            "/api/audits", data={"mode": "auto"}, files=automatic_uploads()
        ).json()["id"]
    with SessionLocal() as db:
        docs = list(
            db.scalars(select(Document).where(Document.audit_id == audit_id).order_by(Document.id))
        )
        classifications = dict(zip([d.id for d in docs], types))

    async def extract(client, audit, doc, pages, images, on_source_read=None):
        return {
            "document_type": classifications[doc],
            "mixed_document": False,
            "observations": [],
            "uncertainties": [],
            "page_coverage": [p["page_id"] for p in pages],
        }

    result = {
        "findings": [],
        "unresolved_checks": [],
        "links": [],
        "calculations": [],
        "assessed_topics": [],
    }
    review = AsyncMock(return_value=result)
    monkeypatch.setattr(pipeline, "extract_document", extract)

    async def semantics(client, audit, doc, extraction, pages, images):
        return extraction

    monkeypatch.setattr(pipeline, "review_source_semantics", semantics)
    monkeypatch.setattr(pipeline, "review", review)
    await pipeline.run_audit(audit_id, object())
    cross = [call for call in review.call_args_list if call.args[2] == "cross"]
    assert len(cross) == expected_cross_calls
    with SessionLocal() as db:
        assert {
            d.id: d.role for d in db.scalars(select(Document).where(Document.audit_id == audit_id))
        } == classifications
        assert db.get(Audit, audit_id).assessment == "incomplete_analysis"


@pytest.mark.asyncio
async def test_internal_failure_keeps_readable_extraction_available_for_cross_audit(monkeypatch):
    monkeypatch.setattr(routes, "run_audit", no_ai_job)
    with TestClient(app) as client:
        audit_id = client.post("/api/audits", files=uploads()).json()["id"]
    with SessionLocal() as db:
        roles = {
            d.id: d.role for d in db.scalars(select(Document).where(Document.audit_id == audit_id))
        }

    async def extract(client, audit, doc, pages, images, on_source_read=None):
        return {
            "document_type": roles[doc],
            "mixed_document": False,
            "observations": [],
            "uncertainties": [],
            "page_coverage": [page["page_id"] for page in pages],
        }

    async def semantics(client, audit, doc, extraction, pages, images):
        return extraction

    cross_contexts = []

    async def review(client, audit, scope, observations, context):
        if scope == "internal" and context["document_type"] == "purchase_order":
            raise ProviderError("Output incomplete", "truncated_output")
        if scope == "cross":
            cross_contexts.append(context)
        return {
            "findings": [],
            "unresolved_checks": [],
            "links": [],
            "calculations": [],
            "assessed_topics": [],
        }

    monkeypatch.setattr(pipeline, "extract_document", extract)
    monkeypatch.setattr(pipeline, "review_source_semantics", semantics)
    monkeypatch.setattr(pipeline, "review", review)
    await pipeline.run_audit(audit_id, object())
    assert len(cross_contexts) == 1
    assert len(cross_contexts[0]["documents"]) == 3
    assert any(
        result["processing_status"] == "failed" for result in cross_contexts[0]["internal_results"]
    )
    with SessionLocal() as db:
        audit = db.get(Audit, audit_id)
        assert audit.status == "failed"
        assert audit.assessment == "incomplete_analysis"
        assert audit.report["cross"] is not None
        assert any("Output incomplete" in item for item in audit.report["unresolved_checks"])
