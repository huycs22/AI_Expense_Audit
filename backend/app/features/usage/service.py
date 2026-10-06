import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.features.usage.models import ApiCall

PRICING = json.loads(Path(__file__).with_name("pricing.json").read_text())
logger = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    pass


def budget_reset_at(now: datetime) -> datetime:
    """The local daily ledger uses UTC, independently of the computer timezone."""
    return now.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)


def budget_exceeded_message(now: datetime) -> str:
    reset = budget_reset_at(now).astimezone(timezone(timedelta(hours=7)))
    return (
        "Ngân sách kiểm thử trong ngày không đủ cho yêu cầu tiếp theo. "
        f"Có thể thử lại sau {reset:%H:%M ngày %d/%m/%Y} (UTC+7). "
        "Dữ liệu đã xử lý được giữ lại; kết quả kiểm tra chưa hoàn tất."
    )


def account_scope(account_id: str) -> str:
    return hashlib.sha256(account_id.encode()).hexdigest()[:16] if account_id else "unconfigured"


def estimate(model: str, input_tokens: int, output_tokens: int) -> tuple[float, float]:
    rates = PRICING["models"].get(model)
    if rates is None:
        raise ValueError("Model is not in the configured free-access pricing allowlist")
    neurons = (
        input_tokens * rates["input_neurons_per_million"]
        + output_tokens * rates["output_neurons_per_million"]
    ) / 1_000_000
    return neurons, neurons * PRICING["usd_per_thousand_neurons"] / 1000


def reserve(
    audit_id: str | None,
    stage: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    attempt: int,
) -> str:
    neurons, _ = estimate(model, input_tokens, output_tokens)
    settings = get_settings()
    scope = account_scope(getattr(settings, "cloudflare_account_id", ""))
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        # Transaction lock also serializes reservations from separate requests.
        db.execute(text("SELECT pg_advisory_xact_lock(724810)"))
        query = select(
            func.sum(func.coalesce(ApiCall.estimated_neurons, ApiCall.reserved_neurons))
        ).where(ApiCall.created_at >= today)
        if getattr(settings, "budget_scope", "application") == "account":
            query = query.where(ApiCall.account_scope == scope)
        spent = db.scalar(query) or 0
        if spent + neurons > settings.daily_neuron_budget:
            raise BudgetExceeded(budget_exceeded_message(datetime.now(timezone.utc)))
        call = ApiCall(
            audit_id=audit_id,
            stage=stage,
            model=model,
            account_scope=scope,
            attempt=attempt,
            reserved_neurons=neurons,
            pricing_version=PRICING["version"],
        )
        db.add(call)
        db.commit()
        return call.id


def finish(
    call_id: str, usage: dict | None, latency_ms: int, status: str, error_code: str | None = None
):
    with SessionLocal() as db:
        call = db.get(ApiCall, call_id)
        call.status = status
        call.latency_ms = latency_ms
        call.usage = usage
        call.error_code = error_code
        if usage is not None:
            call.prompt_tokens = usage.get("prompt_tokens")
            call.completion_tokens = usage.get("completion_tokens")
            if call.prompt_tokens is not None and call.completion_tokens is not None:
                call.estimated_neurons, call.estimated_usd = estimate(
                    call.model, call.prompt_tokens, call.completion_tokens
                )
        # Reasoning tokens are already included in completion_tokens: do not add them twice.
        db.commit()
        logger.info(
            "ai_call id=%s stage=%s model=%s status=%s ms=%s input=%s output=%s neurons=%s estimated_usd=%s",
            call.id,
            call.stage,
            call.model,
            status,
            latency_ms,
            call.prompt_tokens,
            call.completion_tokens,
            call.estimated_neurons,
            call.estimated_usd,
        )


def summarize(calls: list[ApiCall]) -> dict:
    stages = []
    for stage in dict.fromkeys(c.stage for c in calls):
        group = [c for c in calls if c.stage == stage]
        stages.append(
            {
                "stage": stage,
                "call_count": len(group),
                "estimated_usd": sum(c.estimated_usd or 0 for c in group),
                "estimated_neurons": sum(c.estimated_neurons or 0 for c in group),
                "unknown_usage_calls": sum(c.estimated_usd is None for c in group),
            }
        )
    items = [
        {
            "id": c.id,
            "stage": c.stage,
            "model": c.model,
            "account_scope": c.account_scope,
            "status": c.status,
            "attempt": c.attempt,
            "latency_ms": c.latency_ms,
            "prompt_tokens": c.prompt_tokens,
            "completion_tokens": c.completion_tokens,
            "estimated_neurons": c.estimated_neurons,
            "estimated_usd": c.estimated_usd,
            "usage": c.usage,
            "pricing_version": c.pricing_version,
        }
        for c in calls
    ]
    return {
        "calls": items,
        "stages": stages,
        "call_count": len(calls),
        "prompt_tokens": sum(c.prompt_tokens or 0 for c in calls),
        "completion_tokens": sum(c.completion_tokens or 0 for c in calls),
        "estimated_neurons": sum(c.estimated_neurons or 0 for c in calls),
        "estimated_usd": sum(c.estimated_usd or 0 for c in calls),
        "unknown_usage_calls": sum(c.estimated_usd is None for c in calls),
        "billing": "provider_charges_unknown",
        "billed_usd": None,
        "account_remaining_neurons": None,
        "pricing_version": PRICING["version"],
    }
