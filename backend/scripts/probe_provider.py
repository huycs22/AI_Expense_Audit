"""One metered, tiny diagnostic; never print credentials or provider response bodies."""

import asyncio

from app.core import models  # noqa: F401
from app.core.cloudflare import CloudflareClient, ProviderError


async def main():
    client = CloudflareClient()
    try:
        await client.complete(
            None,
            "connectivity_probe",
            client.settings.cloudflare_model,
            [{"role": "user", "content": 'Return JSON: {"ok":true}'}],
            max_tokens=16,
        )
        print("Cloudflare connectivity: available")
    except ProviderError as error:
        print(f"Cloudflare connectivity blocked: {error}")


if __name__ == "__main__":
    asyncio.run(main())
