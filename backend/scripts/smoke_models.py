"""Small live connectivity checks; every call is captured in the usage ledger."""

import asyncio
import json

from app.core import models  # noqa: F401
from app.core.cloudflare import CloudflareClient
from app.core.config import get_settings


async def main():
    client = CloudflareClient()
    settings = get_settings()
    for model in (settings.cloudflare_model, settings.cloudflare_vision_model):
        try:
            response = await client.complete(
                None,
                "smoke",
                model,
                [{"role": "user", "content": 'Return JSON only: {"ok": true}'}],
                max_tokens=128,
            )
            print(
                json.dumps(
                    {"model": model, "response": response.get("content")}, ensure_ascii=False
                )
            )
        except Exception as exc:
            print(json.dumps({"model": model, "error": str(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
