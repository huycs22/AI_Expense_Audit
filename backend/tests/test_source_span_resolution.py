import pytest

from app.features.extraction.normalization import ground, unique_source_span


def test_exact_multiblock_quote_resolves_location_and_preserves_values():
    blocks = [
        {"block_id": "b1", "text": "Payment in 21 days."},
        {"block_id": "b2", "text": "Delivery by 14/11/2027."},
        {"block_id": "b3", "text": "Freight included."},
    ]
    quote = "Payment in 21 days. Delivery by 14/11/2027."
    extraction = {
        "observations": [
            {
                "field_key": "terms",
                "value_type": "text",
                "raw_value": quote,
                "quote": quote,
                "page_id": "p1",
                "block_ids": ["b1"],
                "group_key": None,
            }
        ],
        "page_coverage": ["p1"],
        "uncertainties": [],
    }
    result = ground(
        extraction, [{"page_id": "p1", "input_method": "native_text", "blocks": blocks}], "d"
    )
    observation = result["observations"][0]
    assert observation["block_ids"] == ["b1", "b2"]
    assert observation["raw_value"] == quote
    assert observation["citation_resolution"]["original_block_ids"] == ["b1"]
    assert extraction["observations"][0]["block_ids"] == ["b1"]


@pytest.mark.parametrize("quote", ["", "Invented", "Repeated"])
def test_empty_absent_or_repeated_quotes_cannot_be_relocated(quote):
    blocks = [{"block_id": "a", "text": "Repeated"}, {"block_id": "b", "text": "Repeated"}]
    assert unique_source_span(quote, blocks) is None


def test_two_occurrences_inside_one_block_are_ambiguous():
    assert (
        unique_source_span("Taylor", [{"block_id": "a", "text": "Taylor approves Taylor"}]) is None
    )


def test_broad_citations_narrow_only_for_a_unique_exact_quote():
    blocks = [
        {"block_id": "b1", "text": "Context"},
        {"block_id": "b2", "text": "Holder Alex"},
        {"block_id": "b3", "text": "Unrelated"},
    ]
    draft = {
        "page_coverage": ["p"],
        "uncertainties": [],
        "observations": [
            {
                "field_key": "holder",
                "value_type": "text",
                "raw_value": "Alex",
                "quote": "Holder Alex",
                "page_id": "p",
                "block_ids": ["b1", "b2", "b3"],
            }
        ],
    }
    pages = [{"page_id": "p", "input_method": "native_text", "blocks": blocks}]
    assert ground(draft, pages, "doc")["observations"][0]["block_ids"] == ["b1", "b2", "b3"]
    result = ground(draft, pages, "doc", narrow_citations=True)["observations"][0]
    assert result["block_ids"] == ["b2"]
    assert result["raw_value"] == "Alex"
    assert result["citation_resolution"]["original_block_ids"] == ["b1", "b2", "b3"]
    blocks.append({"block_id": "b4", "text": "Holder Alex"})
    assert ground(draft, pages, "doc", narrow_citations=True)["observations"][0]["block_ids"] == [
        "b1",
        "b2",
        "b3",
    ]


def test_noncontiguous_header_row_quote_is_rejected_with_specific_feedback():
    draft = {
        "page_coverage": ["p"],
        "uncertainties": [],
        "observations": [
            {
                "field_key": "signer",
                "value_type": "text",
                "raw_value": "Sam",
                "quote": "Signatures Sam Approved",
                "page_id": "p",
                "block_ids": ["b1", "b3"],
            }
        ],
    }
    pages = [
        {
            "page_id": "p",
            "input_method": "native_text",
            "blocks": [
                {"block_id": "b1", "text": "Signatures"},
                {"block_id": "b2", "text": "Alex Submitted"},
                {"block_id": "b3", "text": "Sam Approved"},
            ],
        }
    ]
    with pytest.raises(ValueError, match=r"Observation #1 \(signer\).*b3.*nonadjacent"):
        ground(draft, pages, "doc")
