"""Provider control flow, without sending credentials or spending API allowance."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from app.core import cloudflare


def provider(monkeypatch, handler):
    settings = SimpleNamespace(
        cloudflare_account_id="test-account",
        cloudflare_api_token=SecretStr("test-secret"),
        audit_completion_tokens=100,
        max_completion_tokens=100,
        api_timeout_seconds=1,
    )
    monkeypatch.setattr(cloudflare, "get_settings", lambda: settings)
    reserve = Mock(return_value="call")
    finish = Mock()
    monkeypatch.setattr(cloudflare.usage_service, "reserve", reserve)
    monkeypatch.setattr(cloudflare.usage_service, "finish", finish)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        cloudflare.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    return cloudflare.CloudflareClient(), reserve, finish


@pytest.mark.asyncio
async def test_quota_failure_stops_queued_calls_and_is_secret_safe(monkeypatch):
    client, reserve, finish = provider(
        monkeypatch,
        lambda request: httpx.Response(
            429,
            json={
                "errors": [
                    {
                        "code": 3036,
                        "message": "You have used up your daily free allocation of 10,000 neurons",
                    }
                ]
            },
        ),
    )
    for _ in range(2):
        with pytest.raises(cloudflare.ProviderError) as error:
            await client.complete(None, "test", "model", [{"role": "user", "content": "test"}])
        assert "test-secret" not in str(error.value)
    assert reserve.call_count == 1
    assert finish.call_args.args[3:] == ("failed", "3036")
    assert "trong ngày" in str(error.value)


@pytest.mark.asyncio
async def test_transient_server_failure_retries_once_and_records_both_attempts(monkeypatch):
    responses = iter(
        [
            httpx.Response(503, json={"errors": [{"code": 503}]}),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                },
            ),
        ]
    )
    client, reserve, finish = provider(monkeypatch, lambda request: next(responses))
    assert await client.complete(None, "test", "model", []) == {"content": "{}"}
    assert [call.args[-1] for call in reserve.call_args_list] == [1, 2]
    assert [call.args[3] for call in finish.call_args_list] == ["failed", "completed"]


@pytest.mark.asyncio
async def test_read_timeout_is_unknown_usage_and_not_automatically_replayed(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("timed out", request=request)

    client, reserve, finish = provider(monkeypatch, timeout)
    with pytest.raises(cloudflare.ProviderError):
        await client.complete(None, "test", "model", [])
    assert reserve.call_count == 1
    assert finish.call_args.args[1] is None
    assert finish.call_args.args[3:] == ("failed", "ReadTimeout")


@pytest.mark.asyncio
async def test_truncated_response_usage_is_recorded_but_output_is_rejected(monkeypatch):
    client, reserve, finish = provider(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{broken"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 100},
            },
        ),
    )
    with pytest.raises(cloudflare.ProviderError, match="token limit") as error:
        await client.complete(None, "test", "model", [])
    assert reserve.call_count == 1
    assert finish.call_args.args[1]["completion_tokens"] == 100
    assert finish.call_args.args[3:] == ("truncated", "truncated_output")
    assert error.value.partial_response == {"content": "{broken"}
    assert "{broken" not in str(error.value)


@pytest.mark.asyncio
async def test_explicit_retry_can_run_after_quota_reset(monkeypatch):
    responses = iter(
        [
            httpx.Response(
                429,
                json={
                    "errors": [{"code": 4006, "message": "Daily free neuron allocation exhausted"}]
                },
            ),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                },
            ),
        ]
    )
    client, reserve, finish = provider(monkeypatch, lambda request: next(responses))
    with pytest.raises(cloudflare.ProviderError):
        await client.complete(None, "test", "model", [])
    assert client.stop_until > datetime.now(timezone.utc)
    client.stop_until = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert await client.complete(None, "test", "model", []) == {"content": "{}"}
    assert reserve.call_count == 2
