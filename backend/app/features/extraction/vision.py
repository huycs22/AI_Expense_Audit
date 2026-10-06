"""Overlapping page views keep small print legible without changing source files."""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image


def page_views(page_id: str, image_path: str) -> list[dict]:
    content = []
    with Image.open(Path(image_path)) as source:
        # Empty margins consume the vision model's resolution budget, especially
        # on sparse continuation pages. Keep every non-white pixel plus padding.
        ink = source.convert("L").point(lambda value: 255 if value < 245 else 0)
        bounds = ink.getbbox()
        if bounds:
            left, top, right, bottom = bounds
            source = source.crop(
                (
                    max(0, left - 16),
                    max(0, top - 16),
                    min(source.width, right + 16),
                    min(source.height, bottom + 16),
                )
            )
        width, height = source.size
        for name, top, bottom in [("upper", 0, 0.58), ("lower", 0.42, 1)]:
            view = source.crop((0, int(height * top), width, int(height * bottom))).convert("RGB")
            buffer = BytesIO()
            view.save(buffer, format="JPEG", quality=95)
            encoded = base64.b64encode(buffer.getvalue()).decode()
            content.extend(
                [
                    {
                        "type": "text",
                        "text": f"Original page {page_id}, overlapping {name} view. Cite {page_id}.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ]
            )
    return content
