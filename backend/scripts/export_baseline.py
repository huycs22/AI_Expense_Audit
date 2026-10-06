"""Recover the last completed measured revision from immutable stage history.

This exports historical evidence only; it does not change the current failed audit,
rerun models, or describe an earlier prompt revision as passing the final prompts.
"""

import json

from evaluate import score
from sqlalchemy import select

from app.core import models  # noqa: F401
from app.core.config import ROOT
from app.core.database import SessionLocal
from app.features.audits.models import StageRun
from app.features.documents.models import Document
from app.features.usage.models import ApiCall
from app.features.usage.service import summarize


def main():
    latest_path = ROOT / "data/evaluations/original.json"
    current = json.loads(latest_path.read_text(encoding="utf-8"))
    audit_id = current["audit_id"]
    with SessionLocal() as db:
        cross = db.scalar(
            select(StageRun)
            .where(
                StageRun.audit_id == audit_id,
                StageRun.stage == "cross",
                StageRun.status == "completed",
            )
            .order_by(StageRun.started_at.desc())
        )
        if cross is None:
            raise RuntimeError("No completed cross-document revision is available")
        docs = list(db.scalars(select(Document).where(Document.audit_id == audit_id)))
        internal = []
        for doc in docs:
            stage = db.scalar(
                select(StageRun)
                .where(
                    StageRun.audit_id == audit_id,
                    StageRun.document_id == doc.id,
                    StageRun.stage == "internal",
                    StageRun.status == "completed",
                    StageRun.finished_at <= cross.started_at,
                )
                .order_by(StageRun.finished_at.desc())
            )
            internal.append(stage)
        report = {
            "internal": [{"document_id": stage.document_id, **stage.payload} for stage in internal],
            "cross": cross.payload,
            "findings": [f for stage in internal for f in stage.payload["findings"]]
            + cross.payload["findings"],
            "unresolved_checks": [
                c for stage in internal for c in stage.payload["unresolved_checks"]
            ]
            + cross.payload["unresolved_checks"],
        }
        beginning = min(stage.started_at for stage in internal)
        calls = list(
            db.scalars(
                select(ApiCall)
                .where(ApiCall.audit_id == audit_id, ApiCall.created_at <= cross.finished_at)
                .order_by(ApiCall.created_at)
            )
        )
        baseline = {
            "scenario": "original_historical_baseline",
            "audit_id": audit_id,
            "historical_revision": cross.id,
            "note": "Historical completed stages before the final prompt fixes. Current retry is quota-blocked.",
            "stage_latency_seconds": (cross.finished_at - beginning).total_seconds(),
            "metrics": score(report, docs),
            "usage": summarize(calls),
            "revision_usage": summarize([call for call in calls if call.created_at >= beginning]),
            "report": report,
        }
    path = ROOT / "data/evaluations/original-baseline.json"
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "stage_latency_seconds": baseline["stage_latency_seconds"],
                "metrics": baseline["metrics"],
                "revision_usage": {
                    k: v
                    for k, v in baseline["revision_usage"].items()
                    if k not in {"calls", "stages"}
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
