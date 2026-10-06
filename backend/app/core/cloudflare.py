import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import get_settings
from app.features.usage import service as usage_service


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, code: str = "provider_error", partial_response: dict | None = None
    ):
        super().__init__(message)
        self.code = code
        # Private diagnostic evidence: never include model content in the exception/log text.
        self.partial_response = partial_response


class CloudflareClient:
    """Direct Workers AI only. Credentials and document bodies never enter logs."""

    def __init__(self):
        self.settings = get_settings()
        self.semaphore = asyncio.Semaphore(2)
        self.stopped_error: ProviderError | None = None
        self.stop_until: datetime | None = None

    async def complete(
        self,
        audit_id: str | None,
        stage: str,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        schema: dict | None = None,
    ) -> dict:
        settings = self.settings
        if (
            not settings.cloudflare_account_id
            or not settings.cloudflare_api_token.get_secret_value()
        ):
            raise ProviderError("Thiếu cấu hình Cloudflare trong .env", "configuration")
        max_tokens = max_tokens or (
            settings.audit_completion_tokens
            if stage.startswith("audit_")
            else settings.max_completion_tokens
        )
        payload = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": 0,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        else:
            payload["response_format"] = (
                {"type": "json_schema", "json_schema": schema}
                if schema
                else {"type": "json_object"}
            )
        # Conservative local estimate: UTF-8 bytes cover text plus a reserve for image tokens.
        text_bytes = sum(
            len(json.dumps(m.get("content", ""), ensure_ascii=False).encode())
            for m in messages
            if isinstance(m.get("content"), str)
        )
        image_count = sum(
            sum(c.get("type") == "image_url" for c in m.get("content", []) if isinstance(c, dict))
            for m in messages
            if isinstance(m.get("content"), list)
        )
        multipart_bytes = sum(
            len(c.get("text", "").encode())
            for m in messages
            if isinstance(m.get("content"), list)
            for c in m["content"]
            if c.get("type") == "text"
        )
        estimated_input = (
            text_bytes
            + multipart_bytes
            + image_count * 12000
            + (len(json.dumps(tools)) if tools else 0)
        )
        async with self.semaphore:
            if self.stopped_error:
                if self.stop_until is None or datetime.now(timezone.utc) < self.stop_until:
                    raise self.stopped_error
                self.stopped_error = None
            for attempt in range(1, 3):
                call_id = usage_service.reserve(
                    audit_id, stage, model, estimated_input, max_tokens, attempt
                )
                started = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=settings.api_timeout_seconds) as client:
                        response = await client.post(
                            f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {settings.cloudflare_api_token.get_secret_value()}"
                            },
                            json=payload,
                        )
                    data = response.json()
                    if response.is_error or not data.get("choices"):
                        errors = data.get("errors", [])
                        code = (
                            str(errors[0].get("code", response.status_code))
                            if errors
                            else str(response.status_code)
                        )
                        descriptions = " ".join(
                            str(error.get("message", "")) for error in errors
                        ).casefold()
                        if "daily" in descriptions and (
                            "neuron" in descriptions or "allocation" in descriptions
                        ):
                            detail = "Đã hết hạn mức Cloudflare miễn phí trong ngày"
                        elif "capacity" in descriptions:
                            detail = "Cloudflare tạm thời hết năng lực xử lý"
                        else:
                            detail = "Cloudflare không xử lý được yêu cầu"
                        usage_service.finish(
                            call_id,
                            data.get("usage"),
                            int((time.perf_counter() - started) * 1000),
                            "failed",
                            code,
                        )
                        # Never retry quota/access failures. Only transient server errors get one retry.
                        if response.status_code >= 500 and attempt == 1:
                            await asyncio.sleep(1)
                            continue
                        failure = ProviderError(
                            f"{detail} (HTTP {response.status_code}, code {code}); kiểm tra quyền/quota trong dashboard",
                            code,
                        )
                        if response.status_code in {401, 403, 429}:
                            self.stopped_error = failure
                            now = datetime.now(timezone.utc)
                            if response.status_code == 429:
                                self.stop_until = (
                                    (now + timedelta(days=1)).replace(
                                        hour=0, minute=0, second=0, microsecond=0
                                    )
                                    if "daily" in descriptions
                                    else now + timedelta(seconds=60)
                                )
                        raise failure
                    choice = data["choices"][0]
                    truncated = choice.get("finish_reason") == "length"
                    usage_service.finish(
                        call_id,
                        data.get("usage"),
                        int((time.perf_counter() - started) * 1000),
                        "truncated" if truncated else "completed",
                        "truncated_output" if truncated else None,
                    )
                    if truncated:
                        raise ProviderError(
                            "Model output exceeded token limit; no truncated result accepted",
                            "truncated_output",
                            partial_response=choice.get("message"),
                        )
                    return choice["message"]
                except (httpx.HTTPError, ValueError) as exc:
                    usage_service.finish(
                        call_id,
                        None,
                        int((time.perf_counter() - started) * 1000),
                        "failed",
                        type(exc).__name__,
                    )
                    if attempt == 2 or isinstance(exc, httpx.ReadTimeout):
                        raise ProviderError(
                            "Lỗi kết nối/định dạng phản hồi Cloudflare", type(exc).__name__
                        ) from None
                    await asyncio.sleep(1)
        raise ProviderError("No model response")
