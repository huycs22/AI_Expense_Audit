from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.core.config import get_settings

PDFIUM_LOCK = Lock()


@dataclass
class PreparedPage:
    number: int
    evidence: dict
    image_path: Path


def inspect_type(path: Path) -> str:
    if path.read_bytes()[:5] == b"%PDF-":
        return "application/pdf"
    try:
        with Image.open(path) as image:
            kind = image.format
            image.verify()
        if kind in {"PNG", "JPEG"}:
            return "image/png" if kind == "PNG" else "image/jpeg"
    except (OSError, ValueError):
        pass
    raise ValueError("Chỉ hỗ trợ PDF, PNG hoặc JPEG hợp lệ")


def read_pages(path: Path, media_type: str, document_id: str, start: int = 1) -> list[PreparedPage]:
    # PDFium is not thread-safe, including when separate documents are opened.
    with PDFIUM_LOCK:
        return _read_pages(path, media_type, document_id, start)


def _read_pages(path: Path, media_type: str, document_id: str, start: int) -> list[PreparedPage]:
    settings = get_settings()
    output_dir = path.parent / "pages"
    output_dir.mkdir(exist_ok=True)
    result = []
    if media_type == "application/pdf":
        with pdfplumber.open(path) as pdf, pdfium.PdfDocument(path) as renderer:
            if len(pdf.pages) > settings.max_document_pages:
                raise ValueError("Tài liệu vượt giới hạn số trang")
            for offset, page in enumerate(pdf.pages):
                number = start + offset
                page_id = f"{document_id}:p{number}"
                blocks = []
                for i, line in enumerate(page.extract_text_lines(layout=False)):
                    blocks.append(
                        {
                            "block_id": f"{page_id}:b{i + 1}",
                            "text": line["text"],
                            "bbox": [line[k] for k in ("x0", "top", "x1", "bottom")],
                        }
                    )
                text = " ".join(b["text"] for b in blocks)
                # Sparse or visibly corrupted text needs visual reading. This is a routing signal.
                usable = len(text.strip()) >= 80 and text.count("\ufffd") < max(2, len(text) // 100)
                image_path = output_dir / f"p{number}.jpg"
                rendered = renderer[offset]
                bitmap = rendered.render(scale=2)
                bitmap.to_pil().convert("RGB").save(image_path, quality=92)
                bitmap.close()
                rendered.close()
                evidence = {
                    "page_id": page_id,
                    "page_number": number,
                    "blocks": blocks,
                    "table_candidates": page.extract_tables(),
                    "input_method": "native_text" if usable else "vision",
                    "coordinate_system": "pdf_top_left_points",
                    "width": page.width,
                    "height": page.height,
                }
                result.append(PreparedPage(number, evidence, image_path))
    else:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((2400, 3200))
            image_path = output_dir / f"p{start}.jpg"
            image.save(image_path, quality=92)
            evidence = {
                "page_id": f"{document_id}:p{start}",
                "page_number": start,
                "blocks": [],
                "table_candidates": [],
                "input_method": "vision",
                "coordinate_system": "image_pixels",
                "width": image.width,
                "height": image.height,
            }
            result.append(PreparedPage(start, evidence, image_path))
    if not result:
        raise ValueError("Tài liệu không có trang")
    return result
