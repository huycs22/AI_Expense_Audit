"""Actual derived PDFs/images: verify evidence preparation, not model accuracy."""

import importlib.util
from pathlib import Path

import pytest

from app.core.config import ROOT
from app.features.documents.reader import inspect_type, read_pages


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    script = ROOT / "backend/scripts/prepare_fixtures.py"
    spec = importlib.util.spec_from_file_location("prepare_fixtures", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = tmp_path_factory.mktemp("document-fixtures")
    module.main()
    return module.OUT


def text(pages):
    return "\n".join(block["text"] for page in pages for block in page.evidence["blocks"])


def read(directory: Path):
    path = next(path for path in directory.iterdir() if path.is_file())
    return read_pages(path, inspect_type(path), "fixture")


def test_mixed_pdf_routes_each_page_independently(fixtures):
    pages = read(fixtures / "mixed/invoice")
    assert [page.evidence["input_method"] for page in pages] == ["native_text", "vision"]
    assert [page.number for page in pages] == [1, 2]
    assert all(page.image_path.exists() for page in pages)


def test_corrected_fixture_removes_known_discrepancies_from_source(fixtures):
    invoice = text(read(fixtures / "clean/invoice"))
    request = text(read(fixtures / "clean/payment_request"))
    assert "DOCK-C USB-C Dock 8-in-1 10 Chiếc 1,250,000 12,500,000" in invoice
    assert "HDMI-2 Cáp HDMI 2m 20 Sợi 150,000 3,000,000" in invoice
    assert "52,250,000" in invoice and "55,220,000" not in invoice
    assert "888800001042" in request and "888800009917" not in request
    assert "NGUYỄN VĂN PHÚ" not in request and "Pending" not in request


def test_contradiction_and_injection_are_preserved_as_evidence(fixtures):
    pages = read(fixtures / "contradiction/invoice")
    assert "59,250,000" in text([pages[0]])
    assert "52,250,000" in text([pages[1]])
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in text(read(fixtures / "injection/invoice"))


def test_mismatched_reference_and_unreadable_input_are_real_fixtures(fixtures):
    request = text(read(fixtures / "mismatched_references/payment_request"))
    assert "INV-2026-9999" in request and "INV-2026-0891" not in request
    pages = read(fixtures / "unreadable/payment_request")
    assert pages[0].evidence["input_method"] == "vision"
    assert pages[0].evidence["blocks"] == []
