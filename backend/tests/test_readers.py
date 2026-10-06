import base64
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import ROOT
from app.features.documents.reader import inspect_type, read_pages
from app.features.extraction.vision import page_views

SAMPLES = ROOT / "Expense_Audit_System_Candidate_Pack" / "Sample"


def test_real_invoice_all_pages_and_table_evidence(tmp_path):
    source = tmp_path / "invoice"
    source.write_bytes((SAMPLES / "Sample_Invoice.pdf").read_bytes())
    assert inspect_type(source) == "application/pdf"
    pages = read_pages(source, "application/pdf", "invoice")
    assert len(pages) == 2
    assert all(p.evidence["input_method"] == "native_text" for p in pages)
    assert "55,220,000" in " ".join(b["text"] for b in pages[1].evidence["blocks"])
    assert all(p.image_path.exists() for p in pages)


def test_image_content_detection_and_order(tmp_path):
    source = tmp_path / "not-an-extension"
    Image.new("RGB", (400, 600), "white").save(source, format="PNG")
    assert inspect_type(source) == "image/png"
    pages = read_pages(source, "image/png", "scan", start=3)
    assert pages[0].evidence["page_id"] == "scan:p3"
    assert pages[0].evidence["input_method"] == "vision"


def test_spoofed_extension_rejected(tmp_path):
    source = tmp_path / "fake.pdf"
    source.write_text("not a pdf")
    with pytest.raises(ValueError):
        inspect_type(source)


def test_visual_views_cover_page_edges_and_preserve_source(tmp_path):
    source = tmp_path / "scan.png"
    image = Image.new("RGB", (400, 600), "red")
    image.paste("blue", (0, 300, 400, 600))
    image.save(source)
    original_bytes = source.read_bytes()
    content = page_views("p7", str(source))
    assert all("p7" in part["text"] for part in content if part["type"] == "text")
    views = [
        Image.open(BytesIO(base64.b64decode(part["image_url"]["url"].split(",", 1)[1])))
        for part in content
        if part["type"] == "image_url"
    ]
    assert len(views) == 2
    assert views[0].getpixel((0, 0))[0] > 240
    assert views[1].getpixel((0, views[1].height - 1))[2] > 240
    assert sum(view.height for view in views) > image.height
    assert source.read_bytes() == original_bytes


def test_sparse_page_views_preserve_ink_and_remove_empty_margins(tmp_path):
    source = tmp_path / "sparse.png"
    image = Image.new("RGB", (400, 600), "white")
    image.paste("black", (100, 100, 300, 200))
    image.save(source)
    views = [
        Image.open(BytesIO(base64.b64decode(part["image_url"]["url"].split(",", 1)[1])))
        for part in page_views("p1", str(source))
        if part["type"] == "image_url"
    ]
    assert all(view.width == 232 for view in views)
    assert sum(view.height for view in views) > 132
    assert sum(view.height for view in views) < 600
