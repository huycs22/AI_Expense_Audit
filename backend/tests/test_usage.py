from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.features.usage import service
from app.features.usage.models import ApiCall
from app.features.usage.service import PRICING, estimate, summarize


def test_rate_calculation():

    neurons, usd = estimate("@cf/zai-org/glm-4.7-flash", 1000, 1000)

    assert neurons == 41.9

    assert abs(usd - 0.0004609) < 1e-10


def test_missing_usage_is_unknown_and_reasoning_not_double_counted():

    call = ApiCall(
        id="c",
        stage="test",
        model="@cf/zai-org/glm-4.7-flash",
        status="failed",
        attempt=1,
        reserved_neurons=100,
        pricing_version=PRICING["version"],
    )

    summary = summarize([call])

    assert summary["unknown_usage_calls"] == 1

    assert summary["billed_usd"] is None

    assert summary["account_remaining_neurons"] is None


@pytest.mark.integration
def test_account_budget_isolated_without_erasing_prior_usage(monkeypatch):

    first_account, second_account = str(uuid4()), str(uuid4())

    settings = SimpleNamespace(
        cloudflare_account_id=first_account, budget_scope="account", daily_neuron_budget=1000
    )

    monkeypatch.setattr(service, "get_settings", lambda: settings)

    calls = []

    try:
        calls.append(
            service.reserve(None, "scope_test", "@cf/zai-org/glm-4.7-flash", 1000, 1000, 1)
        )

        settings.daily_neuron_budget = 42

        with pytest.raises(service.BudgetExceeded):
            service.reserve(None, "scope_test", "@cf/zai-org/glm-4.7-flash", 1000, 1000, 1)

        settings.cloudflare_account_id = second_account

        calls.append(
            service.reserve(None, "scope_test", "@cf/zai-org/glm-4.7-flash", 1000, 1000, 1)
        )

        with SessionLocal() as db:
            assert db.get(ApiCall, calls[0]).account_scope == service.account_scope(first_account)

            assert db.get(ApiCall, calls[1]).account_scope == service.account_scope(second_account)

        settings.budget_scope = "application"

        with pytest.raises(service.BudgetExceeded):
            service.reserve(None, "scope_test", "@cf/zai-org/glm-4.7-flash", 1000, 1000, 1)

    finally:
        with SessionLocal() as db:
            db.execute(delete(ApiCall).where(ApiCall.id.in_(calls)))

            db.commit()


@pytest.mark.parametrize("hour", [0, 3, 23])
def test_budget_message_always_names_next_utc_reset_date(hour):

    from datetime import datetime, timezone

    now = datetime(2030, 4, 18, hour, 15, tzinfo=timezone.utc)

    assert service.budget_reset_at(now) == datetime(2030, 4, 19, tzinfo=timezone.utc)

    message = service.budget_exceeded_message(now)

    assert "07:00 ngày 19/04/2030" in message

    assert "Neuron" not in message
