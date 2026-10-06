import json
from unittest.mock import AsyncMock

import pytest

from app.core.cloudflare import ProviderError
from app.features.extraction.quality import (
    QualityReview,
    apply_review,
    missing_identifier_occurrences,
    validate_coverage,
)
from app.features.extraction.service import extract_document


def observation(value="REF-X9", page="p1", block="p1b1", **changes):
    return {
        "field_key": "document_number",
        "value_type": "identifier",
        "raw_value": value,
        "page_id": page,
        "block_ids": [block],
        "quote": value,
        "group_key": None,
        **changes,
    }


def page(number, text):
    return {
        "page_id": f"p{number}",
        "input_method": "native_text",
        "blocks": [{"block_id": f"p{number}b1", "text": text}],
    }


def review(blocks, **changes):
    return QualityReview.model_validate(
        {
            "reviewed_page_ids": [f"p{i + 1}" for i in range(len(blocks))],
            "block_coverage": [
                {"block_id": block, "disposition": "extracted", "reason": "Nguồn"}
                for block in blocks
            ],
            "corrections": [],
            "additions": [],
            "unresolved_checks": [],
            **changes,
        }
    )


def test_known_identifier_coverage_is_per_source_occurrence_not_per_page_flag():
    pages = [page(1, "Number REF-X9"), page(2, "Reference REF-X9")]
    draft = {"observations": [observation()], "uncertainties": [], "page_coverage": ["p1", "p2"]}
    assert missing_identifier_occurrences(draft, pages) == [
        {"page_id": "p2", "block_id": "p2b1", "raw_value": "REF-X9"}
    ]
    draft["observations"].append(observation(page="p2", block="p2b1"))
    assert not missing_identifier_occurrences(draft, pages)
    # Do not mistake a longer identifier for an occurrence of this one.
    assert not missing_identifier_occurrences(draft, [page(3, "REF-X99")])


def test_coverage_cannot_claim_an_empty_block_is_extracted_or_skip_a_block():
    draft = {"observations": [observation()]}
    pages = [page(1, "REF-X9"), page(2, "Other fact")]
    with pytest.raises(ValueError, match="no cited observation"):
        validate_coverage(draft, review(["p1b1", "p2b1"]), pages)
    with pytest.raises(ValueError, match="every native source block"):
        validate_coverage(draft, review(["p1b1"], reviewed_page_ids=["p1", "p2"]), pages)


def test_extraneous_citations_cannot_fake_block_coverage():
    pages = [page(1, "REF-X9")]
    pages[0]["blocks"].append({"block_id": "p1b2", "text": "Other source fact"})
    source = observation(block_ids=["p1b1", "p1b2"])
    with pytest.raises(ValueError, match="no cited observation"):
        validate_coverage(
            {"observations": [source]}, review(["p1b1", "p1b2"], reviewed_page_ids=["p1"]), pages
        )


def test_semantic_patch_preserves_source_value_and_never_mutates_input():
    draft = {
        "observations": [observation("Alex", field_key="approver.name", value_type="text")],
        "uncertainties": [],
    }
    fixed = observation("Alex", field_key="issuer.name", value_type="text")
    patch = review(["p1b1"], corrections=[{"observation_id": "o1", "replacement": fixed}])
    assert apply_review(draft, patch)["observations"][0]["field_key"] == "issuer.name"
    assert draft["observations"][0]["field_key"] == "approver.name"
    patch.corrections[0].replacement.raw_value = "Someone else"
    with pytest.raises(ValueError, match="preserve original"):
        apply_review(draft, patch)


@pytest.mark.asyncio
async def test_independent_review_recovers_roles_units_terms_and_repeated_identifier():
    pages = [
        page(1, "REF-X9\nA-5 Widget 4 boxes 2 8"),
        page(2, "REF-X9\nIssued by: Alex - Finance\nTerms: 21 days"),
    ]
    source = observation(
        "Alex",
        page="p2",
        block="p2b1",
        field_key="approver.name",
        value_type="text",
        quote="Issued by: Alex - Finance",
    )
    quantity = observation(
        "4",
        field_key="item.quantity",
        value_type="number",
        group_key="row1",
        quote="A-5 Widget 4 boxes 2 8",
        unit=None,
    )
    draft = {
        "document_type": "invoice",
        "observations": [observation(), source, quantity],
        "uncertainties": [],
        "page_coverage": ["p1", "p2"],
    }
    patch = review(
        ["p1b1", "p2b1"],
        corrections=[
            {
                "observation_id": "o2",
                "replacement": {**source, "field_key": "issuer.name", "group_key": "issuer"},
            },
            {"observation_id": "o3", "replacement": {**quantity, "unit": "boxes"}},
        ],
        additions=[
            observation(page="p2", block="p2b1"),
            observation(
                "Finance",
                page="p2",
                block="p2b1",
                field_key="issuer.role",
                value_type="text",
                quote="Issued by: Alex - Finance",
                group_key="issuer",
            ),
            observation(
                "21",
                page="p2",
                block="p2b1",
                field_key="payment_terms.days",
                value_type="number",
                quote="Terms: 21 days",
                unit="days",
            ),
        ],
    )
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[{"content": json.dumps(draft)}, {"content": patch.model_dump_json()}]
    )
    result = await extract_document(client, "audit", "doc", pages, {})
    assert result["observations"][1]["field_key"] == "issuer.name"
    assert result["observations"][2]["unit"] == "boxes"
    assert result["observations"][-1]["normalized_value"] == "21"
    assert result["quality"]["addition_count"] == 3
    assert not missing_identifier_occurrences(result, pages)


@pytest.mark.asyncio
async def test_review_failure_is_bounded_and_cannot_silently_accept_omissions():
    pages = [page(1, "REF-X9"), page(2, "REF-X9")]
    draft = {
        "document_type": "invoice",
        "observations": [observation()],
        "uncertainties": [],
        "page_coverage": ["p1", "p2"],
    }
    incomplete = review(["p1b1", "p2b1"])
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {"content": json.dumps(draft)},
            {"content": incomplete.model_dump_json()},
            {"content": incomplete.model_dump_json()},
        ]
    )
    with pytest.raises(ValueError, match="quality validation failed"):
        await extract_document(client, "audit", "doc", pages, {})
    assert client.complete.await_count == 3


def test_scan_review_does_not_claim_independent_text_verification():
    pages = [{"page_id": "p1", "input_method": "vision", "blocks": []}]
    validate_coverage({"observations": []}, review([], reviewed_page_ids=["p1"]), pages)


@pytest.mark.asyncio
async def test_source_read_truncation_regenerates_once_without_runaway_prefix():
    draft = {
        "document_type": "invoice",
        "observations": [observation()],
        "uncertainties": [],
        "page_coverage": ["p1"],
    }
    failure = ProviderError(
        "Output limit", "truncated_output", {"content": "RUNAWAY_CITATION_LOOP" * 100}
    )
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            failure,
            {"content": json.dumps(draft)},
            {"content": review(["p1b1"]).model_dump_json()},
        ]
    )
    checkpoint = []
    result = await extract_document(
        client, "audit", "doc", [page(1, "REF-X9")], {}, on_source_read=checkpoint.append
    )
    assert result["observations"][0]["raw_value"] == "REF-X9"
    assert len(checkpoint) == 1
    assert client.complete.await_count == 3
    retry = client.complete.call_args_list[1]
    assert retry.args[1] == "extraction_repair"
    assert "RUNAWAY_CITATION_LOOP" not in json.dumps(retry.args[3])
    assert "minimal contiguous" in retry.args[3][-1]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("code,expected_calls", [("truncated_output", 2), ("quota_exhausted", 1)])
async def test_source_read_retry_is_bounded_and_never_retries_quota(code, expected_calls):
    client = type("Client", (), {})()
    client.complete = AsyncMock(side_effect=ProviderError("Rejected output", code))
    checkpoint = []
    with pytest.raises(ProviderError):
        await extract_document(
            client, "audit", "doc", [page(1, "REF-X9")], {}, on_source_read=checkpoint.append
        )
    assert client.complete.await_count == expected_calls
    assert not checkpoint


@pytest.mark.asyncio
@pytest.mark.parametrize("code,repair", [("truncated_output", True), ("quota_exhausted", False)])
async def test_quality_truncation_repairs_once_but_quota_stops_immediately(code, repair):
    draft = {
        "document_type": "invoice",
        "observations": [observation()],
        "uncertainties": [],
        "page_coverage": ["p1"],
    }
    failure = ProviderError(
        "Provider output rejected", code, {"content": '{"corrections":' + " \n" * 100}
    )
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {"content": json.dumps(draft)},
            failure,
            {"content": review(["p1b1"]).model_dump_json()},
        ]
    )
    if repair:
        result = await extract_document(client, "audit", "doc", [page(1, "REF-X9")], {})
        assert result["schema_version"] == "extraction-v4-source-coverage"
        assert client.complete.await_count == 3
    else:
        with pytest.raises(ProviderError):
            await extract_document(client, "audit", "doc", [page(1, "REF-X9")], {})
        assert client.complete.await_count == 2


def test_coverage_repair_receives_all_mismatches_and_allows_represented_role_context():
    source = page(1, "Heading Alpha")
    source["blocks"] = [
        {"block_id": "p1b1", "text": "Heading Alpha"},
        {"block_id": "p1b2", "text": "Heading Beta"},
        {"block_id": "p1b3", "text": "REF-X9"},
    ]
    draft = {"observations": [observation(block="p1b3")]}
    proposed = review(["p1b1", "p1b2", "p1b3"], reviewed_page_ids=["p1"])
    with pytest.raises(ValueError) as error:
        validate_coverage(draft, proposed, [source])
    assert "p1b1" in str(error.value) and "p1b2" in str(error.value)
    assert "standalone section/field label" in str(error.value)
    for entry in proposed.block_coverage[:2]:
        entry.disposition = "context"
        entry.reason = "Heading for separately represented fields"
    validate_coverage(draft, proposed, [source])


@pytest.mark.asyncio
async def test_source_checkpoint_is_emitted_before_failed_quality_review():
    from unittest.mock import Mock

    reading = dict(
        document_type="invoice",
        mixed_document=False,
        observations=[observation()],
        uncertainties=[],
        page_coverage=["p1"],
    )
    bad = review(["p1b1"])
    bad.block_coverage[0].disposition = "context"
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {"content": json.dumps(reading)},
            {"content": bad.model_dump_json()},
            {"content": bad.model_dump_json()},
        ]
    )
    checkpoint = Mock()
    with pytest.raises(ValueError, match="quality validation failed"):
        await extract_document(
            client, "audit", "document", [page(1, "REF-X9")], {}, on_source_read=checkpoint
        )
    checkpoint.assert_called_once()
    saved = checkpoint.call_args.args[0]
    assert saved["observations"][0]["raw_value"] == "REF-X9"
    assert saved["observations"][0]["page_id"] == "p1"


def test_unsupported_review_extra_does_not_discard_grounded_additions_or_relax_coverage():
    from app.features.extraction.quality import grounded_additions

    pages = [page(1, "REF-X9")]
    proposal = review(
        ["p1b1"], additions=[observation(), observation("NONEXISTENT", quote="REF-X9")]
    )
    filtered, rejected = grounded_additions(proposal, pages, "d", {"p1": "p1"}, {"p1b1": "p1b1"})
    assert len(filtered.additions) == 1
    assert len(rejected) == 1
    assert len(proposal.additions) == 2
    patched = apply_review({"observations": [], "uncertainties": []}, filtered)
    validate_coverage(patched, filtered, pages)
    # Rejecting a fabricated extra cannot make an unrepresented block pass.
    with pytest.raises(ValueError, match="no cited observation"):
        validate_coverage({"observations": []}, filtered, pages)
