"""Local operational diagnostics; never prints credentials or document/model bodies."""

import argparse
import json

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal, utcnow
from app.features.audits.models import Audit, StageRun
from app.features.usage.models import ApiCall
from app.features.usage.service import account_scope


def main(audit_id):
    settings = get_settings()
    with SessionLocal() as db:
        audit = db.get(Audit, audit_id)
        calls = list(db.scalars(select(ApiCall).where(ApiCall.audit_id == audit_id)))
        runs = list(db.scalars(select(StageRun).where(StageRun.audit_id == audit_id)))
        budget_query = select(
            func.sum(func.coalesce(ApiCall.estimated_neurons, ApiCall.reserved_neurons))
        ).where(ApiCall.created_at >= utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
        if settings.budget_scope == "account":
            budget_query = budget_query.where(
                ApiCall.account_scope == account_scope(settings.cloudflare_account_id)
            )
        budget = db.scalar(budget_query)
        print(
            json.dumps(
                {
                    "status": audit.status,
                    "stage": audit.current_stage,
                    "remaining_local_neurons": settings.daily_neuron_budget - float(budget or 0),
                    "calls": [
                        {
                            "stage": c.stage,
                            "status": c.status,
                            "input": c.prompt_tokens,
                            "output": c.completion_tokens,
                        }
                        for c in calls
                    ],
                    "failed_stages": [
                        {
                            "stage": r.stage,
                            "error_length": len(r.error or ""),
                            "partial_fields": {
                                key: len(str(value))
                                for key, value in r.payload.get(
                                    "diagnostic_partial_response", {}
                                ).items()
                            },
                        }
                        for r in runs
                        if r.status == "failed"
                    ],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_id")
    main(parser.parse_args().audit_id)
