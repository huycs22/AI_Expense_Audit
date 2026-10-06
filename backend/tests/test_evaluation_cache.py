import sys

import pytest
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.core.config import ROOT
from app.core.database import SessionLocal
from app.features.audits.pipeline import cached_stage, run_stage
from app.features.audits.reviewer import review_prompt
from app.features.documents.models import Document, DocumentPage
from app.features.documents.service import create_audit
from app.features.extraction.normalization import ground
from app.features.extraction.semantics import SEMANTIC_VERSION
from app.features.extraction.service import extraction_prompt, load_prompt

sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from evaluation_cache import seed_unchanged_documents


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unchanged_evaluation_cache_preserves_new_page_and_observation_ids():
    samples = ROOT / "Expense_Audit_System_Candidate_Pack" / "Sample"

    async def create():
        return await create_audit(
            {
                str(i): [UploadFile(file=(samples / name).open("rb"), filename=name)]
                for i, name in enumerate(
                    [
                        "Sample_Purchase_Order.pdf",
                        "Sample_Invoice.pdf",
                        "Sample_Payment_Request.pdf",
                    ]
                )
            },
            auto_classify=True,
        )

    source_id, target_id = await create(), await create()
    with SessionLocal() as db:
        source = db.scalar(select(Document).where(Document.audit_id == source_id))
        pages = list(
            db.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == source.id)
                .order_by(DocumentPage.number)
            )
        )
    extraction = {
        "document_type": "purchase_order",
        "uncertainties": [],
        "observations": [
            {
                "id": source.id + ":o1",
                "document_id": source.id,
                "page_id": pages[0].id,
                "block_ids": [pages[0].evidence["blocks"][0]["block_id"]],
                "field_key": "document_title",
                "value_type": "text",
                "group_key": None,
                "unit": None,
                "raw_value": pages[0].evidence["blocks"][0]["text"],
                "quote": pages[0].evidence["blocks"][0]["text"],
            }
        ],
        "page_coverage": [page.id for page in pages],
    }

    async def original():
        return extraction

    await run_stage(
        source_id,
        source.id,
        "extraction",
        extraction_prompt([p.evidence for p in pages]),
        original,
        input_data=[p.evidence for p in pages],
    )
    grounded = ground(extraction, [p.evidence for p in pages], source.id)
    added = {**grounded["observations"][0], "id": source.id + ":semantic2"}
    semantic = {
        **grounded,
        "schema_version": SEMANTIC_VERSION,
        "observations": [*grounded["observations"], added],
    }

    async def interpretation():
        return semantic

    await run_stage(
        source_id,
        source.id,
        "source_semantics",
        load_prompt("semantics"),
        interpretation,
        input_data={"extraction": grounded, "pages": [p.evidence for p in pages]},
    )
    internal = {"findings": [{"observation_ids": [added["id"]]}]}

    async def audit_result():
        return internal

    await run_stage(
        source_id,
        source.id,
        "internal",
        review_prompt("internal"),
        audit_result,
        input_data=semantic,
    )
    reused = await seed_unchanged_documents(target_id, source_id)
    assert {stage["stage"] for stage in reused} == {"extraction", "source_semantics", "internal"}
    target_document_id = reused[0]["document_id"]
    copied = cached_stage(target_id, target_document_id, "extraction")
    assert copied["observations"][0]["id"] == target_document_id + ":o1"
    assert copied["observations"][0]["page_id"].startswith(target_document_id)
    assert copied["observations"][0]["block_ids"][0].startswith(target_document_id)
    assert extraction["observations"][0]["id"].startswith(source.id)
    copied_semantic = cached_stage(target_id, target_document_id, "source_semantics")
    assert copied_semantic["observations"][-1]["id"] == target_document_id + ":semantic2"
    copied_internal = cached_stage(target_id, target_document_id, "internal")
    assert copied_internal["findings"][0]["observation_ids"] == [target_document_id + ":semantic2"]
