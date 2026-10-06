import asyncio

from app.core import models  # noqa: F401
from app.core.cloudflare import CloudflareClient
from app.core.config import get_settings


async def main():
    schema = {
        "type": "object",
        "properties": {"severity": {"type": "string", "enum": ["high", "medium", "low"]}},
        "required": ["severity"],
        "additionalProperties": False,
    }
    message = await CloudflareClient().complete(
        None,
        "schema_smoke",
        get_settings().cloudflare_model,
        [{"role": "user", "content": "Return JSON severity high. Keep enum values English."}],
        max_tokens=128,
        schema=schema,
    )
    print(message.get("content"))


if __name__ == "__main__":
    asyncio.run(main())
