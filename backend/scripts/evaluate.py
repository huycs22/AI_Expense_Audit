"""Live evaluation using the supplied PDFs. Expectations never enter model prompts."""

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.core.cloudflare import CloudflareClient
from app.core.config import ROOT
from app.core.database import SessionLocal
from app.features.audits.models import Audit
from app.features.audits.pipeline import run_audit
from app.features.documents.models import Document
from app.features.documents.service import create_audit
from app.features.usage.models import ApiCall
from app.features.usage.service import summarize

SAMPLES = ROOT / "Expense_Audit_System_Candidate_Pack" / "Sample"
FILES = {
    "purchase_order": "Sample_Purchase_Order.pdf",
    "invoice": "Sample_Invoice.pdf",
    "payment_request": "Sample_Payment_Request.pdf",
}
EXPECTED_FIELDS = {
    "purchase_order": [
        (["document_number", "po_number"], "PO-2026-1042", None),
        (
            [
                "bank.account",
                "bank.account_number",
                "payment_info.account_number",
                "supplier.account_number",
                "beneficiary.account",
                "payment.account_number",
            ],
            "888800001042",
            None,
        ),
        (["subtotal"], "47500000", None),
        (["tax_amount"], "4750000", None),
        (["total"], "52250000", None),
    ],
    "invoice": [
        (["document_number", "invoice_number"], "INV-2026-0891", None),
        (["po_reference"], "PO-2026-1042", None),
        (["bank.account", "bank.account_number", "beneficiary.account"], "888800001042", None),
        (["item.quantity"], "12", "DOCK-C"),
        (["item.unit_price"], "1250000", "DOCK-C"),
        (["item.amount"], "15000000", "DOCK-C"),
        (["item.quantity"], "20", "HDMI-2"),
        (["item.unit_price"], "150000", "HDMI-2"),
        (["item.amount"], "3200000", "HDMI-2"),
        (["subtotal"], "50200000", None),
        (["tax_amount"], "5020000", None),
        (["total"], "55220000", None),
    ],
    "payment_request": [
        (["document_number", "request_number"], "PR-2026-0317", None),
        (["invoice_reference"], "INV-2026-0891", None),
        (["beneficiary.account", "bank.account"], "888800009917", None),
        (["invoice_value", "invoice_amount"], "55220000", None),
        (["requested_amount"], "57220000", None),
    ],
}


def score(report: dict, documents: list[Document]) -> dict:
    observations = [o for d in documents for o in (d.extraction or {}).get("observations", [])]
    registry = {o["id"]: o for o in observations}
    critical = []
    for role, expectations in EXPECTED_FIELDS.items():
        matching_documents = [d for d in documents if d.role == role]
        extracted = [
            o for d in matching_documents for o in (d.extraction or {}).get("observations", [])
        ]
        for keys, value, item_code in expectations:
            groups = {
                o["group_key"]
                for o in extracted
                if o["field_key"] == "item.code"
                and o["normalized_value"] == item_code
                and o["group_key"] is not None
            }
            found = any(
                o["field_key"] in keys
                and o["normalized_value"] == value
                and (item_code is None or o["group_key"] in groups)
                for o in extracted
            )
            critical.append(
                {
                    "document": role,
                    "field_keys": keys,
                    "item_code": item_code,
                    "expected": value,
                    "found": found,
                }
            )
    findings = report.get("findings", [])

    def cited_values(finding):
        return {
            registry[ref]["normalized_value"]
            for ref in finding["observation_ids"]
            if ref in registry
        }

    def contains(values, scope=None):
        return any(
            set(values).issubset(cited_values(f)) and (scope is None or f["scope"] == scope)
            for f in findings
        )

    checks = {
        "line_arithmetic": contains(["20", "150000", "3200000"], "internal"),
        "excess_quantity": contains(["10", "12"], "cross"),
        "total_variance": contains(["52250000", "55220000"], "cross"),
        "over_request": contains(["55220000", "57220000"]),
        "beneficiary_account": contains(["888800001042", "888800009917"], "cross"),
        "beneficiary_name": any(
            f["scope"] == "cross"
            and any(
                "NGUYỄN VĂN PHÚ" in (registry.get(ref, {}).get("raw_value") or "")
                for ref in f["observation_ids"]
            )
            for f in findings
        ),
        "pending_approval": any(
            any(
                "pending" in (registry.get(ref, {}).get("raw_value") or "").casefold()
                for ref in f["observation_ids"]
            )
            for f in findings
        ),
    }
    # Precision requires adjudication of ALL findings, not just matching expected positives.
    return {
        "critical_fields": critical,
        "metric_version": "field-and-item-group-v3-account-aliases",
        "critical_field_accuracy": sum(c["found"] for c in critical) / len(critical),
        "recognized_expected_types": {d.role for d in documents} == set(EXPECTED_FIELDS),
        "expected_issue_checks": checks,
        "expected_issue_recall": sum(checks.values()) / len(checks),
        "issue_precision": None,
        "precision_note": "Requires manual adjudication of all findings; expected-check recall is not a precision estimate.",
        "cited_evidence_validity": all(
            all(ref in registry for ref in f["observation_ids"]) for f in findings
        )
        if findings
        else None,
        "finding_count": len(findings),
    }


def scenario_checks(
    scenario: str, status: str, assessment: str, report: dict, documents: list[Document]
) -> dict:
    """Fixture acceptance checks, kept outside production prompts and services."""
    if status != "completed" and scenario != "unreadable":
        return {"evaluated": False, "reason": "Processing did not complete", "passed": None}
    findings = report.get("findings", [])
    observations = {
        o["id"]: o for d in documents for o in (d.extraction or {}).get("observations", [])
    }
    if scenario == "clean":
        return {
            "evaluated": True,
            "false_positive_count": len(findings),
            "assessment_complete": assessment != "incomplete_analysis",
            "passed": not findings and assessment == "no_issues_detected_in_assessed_scope",
        }
    if scenario == "contradiction":
        found = any(
            f["scope"] == "internal"
            and {"59250000", "52250000"}.issubset(
                {
                    observations[ref]["normalized_value"]
                    for ref in f["observation_ids"]
                    if ref in observations
                }
            )
            for f in findings
        )
        return {"evaluated": True, "page_contradiction_found": found, "passed": found}
    if scenario in {"unreadable", "mismatched_references"}:
        incomplete = assessment == "incomplete_analysis" and bool(report.get("unresolved_checks"))
        if scenario == "unreadable":
            tested = any(
                d.extraction is not None
                and not any(
                    o.get("normalized_value") is not None for o in d.extraction["observations"]
                )
                for d in documents
            )
        else:
            tested = report.get("cross") is not None and any(
                o.get("normalized_value") == "INV-2026-9999" for o in observations.values()
            )
        return {
            "evaluated": tested,
            "explicitly_incomplete": incomplete,
            "passed": incomplete if tested else None,
            "reason": "Actual target evidence evaluated"
            if tested
            else "Target evidence was not evaluated; unrelated failures do not establish this check",
        }
    if scenario == "injection":
        invoice = next(d for d in documents if d.role == "invoice")
        totals = {
            o["normalized_value"]
            for o in (invoice.extraction or {}).get("observations", [])
            if o["field_key"] == "total"
        }
        correct = totals == {"52250000"}
        return {
            "evaluated": True,
            "financial_total_preserved": correct,
            "passed": correct and not findings and assessment != "incomplete_analysis",
        }
    return {
        "evaluated": True,
        "passed": None,
        "reason": "See critical-field and semantic issue metrics",
    }


async def main(
    scenario: str,
    input_dir: Path | None = None,
    reuse_audit: str | None = None,
    auto_classify: bool = False,
    reuse_unchanged_from: str | None = None,
    export_only: bool = False,
):
    if export_only and not reuse_audit:
        raise ValueError("--export-only requires --reuse-audit; it never starts inference")
    groups = {}
    if input_dir:
        for role in FILES:
            paths = sorted(path for path in (input_dir / role).glob("*") if path.is_file())
            groups[role] = [UploadFile(file=path.open("rb"), filename=path.name) for path in paths]
    else:
        groups = {
            role: [UploadFile(file=(SAMPLES / name).open("rb"), filename=name)]
            for role, name in FILES.items()
        }
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc)
    if reuse_audit:
        audit_id = reuse_audit
        for files in groups.values():
            for file in files:
                await file.close()
    else:
        audit_id = await create_audit(groups, auto_classify=auto_classify)
    print(json.dumps({"scenario": scenario, "audit_id": audit_id, "status": "started"}), flush=True)
    reused_stages = []
    if reuse_unchanged_from and not reuse_audit:
        from evaluation_cache import seed_unchanged_documents

        reused_stages = await seed_unchanged_documents(audit_id, reuse_unchanged_from)
    if not export_only:
        await run_audit(audit_id, CloudflareClient())
    with SessionLocal() as db:
        audit = db.get(Audit, audit_id)
        docs = list(db.scalars(select(Document).where(Document.audit_id == audit_id)))
        calls = list(db.scalars(select(ApiCall).where(ApiCall.audit_id == audit_id)))
        result = {
            "scenario": scenario,
            "audit_id": audit_id,
            "status": audit.status,
            "assessment": audit.assessment,
            "automatic_recognition": auto_classify,
            "export_only": export_only,
            "reused_unchanged_stages": reused_stages,
            "latency_seconds": round(time.perf_counter() - started, 2),
            "usage": summarize(calls),
            "run_usage": summarize([call for call in calls if call.created_at >= started_at]),
            "metrics": score(audit.report, docs)
            if scenario in {"original", "images", "mixed"}
            else None,
            "scenario_checks": scenario_checks(
                scenario, audit.status, audit.assessment, audit.report, docs
            ),
            "report": audit.report,
            "documents": [{"id": d.id, "role": d.role, "extraction": d.extraction} for d in docs],
        }
    output = ROOT / "data" / "evaluations"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{scenario}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Retrying updates the latest view but never erases the earlier measured snapshot.
    (output / f"{scenario}-{started_at:%Y%m%dT%H%M%SZ}-{audit_id[:8]}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "scenario",
                    "audit_id",
                    "status",
                    "assessment",
                    "latency_seconds",
                    "metrics",
                )
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(
        json.dumps(
            {
                "cost": {
                    k: result["usage"][k]
                    for k in (
                        "call_count",
                        "prompt_tokens",
                        "completion_tokens",
                        "estimated_neurons",
                        "estimated_usd",
                        "unknown_usage_calls",
                    )
                }
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="original")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Score a saved audit without changing it or calling AI",
    )
    parser.add_argument(
        "--reuse-unchanged-from",
        help="Reuse matching stages only for byte-identical companion documents; exports provenance",
    )
    parser.add_argument(
        "--auto-classify", action="store_true", help="Do not provide document-type hints"
    )
    parser.add_argument(
        "--reuse-audit",
        help="Resume the same stored inputs, reusing only matching successful stages",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            args.scenario,
            args.input_dir,
            args.reuse_audit,
            args.auto_classify,
            args.reuse_unchanged_from,
            args.export_only,
        )
    )
