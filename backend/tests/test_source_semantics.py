import json
from unittest.mock import AsyncMock

import pytest

from app.features.extraction.semantics import (
    SemanticInventory,
    parse_semantic_inventory,
    reconcile_semantics,
    review_source_semantics,
)


def fact(value, key, quote, group="actor", value_type="text", unit=None, block="d:p1:b1"):
    return {
        "field_key": key,
        "raw_value": value,
        "quote": quote,
        "value_type": value_type,
        "unit": unit,
        "group_key": group,
        "page_id": "d:p1",
        "block_ids": [block],
        "role": None,
        "meaning": "term_number"
        if value_type == "number"
        else ("actor_role" if key.endswith(".role") else "actor_name"),
    }


def evidence():
    return [
        {
            "page_id": "d:p1",
            "input_method": "native_text",
            "blocks": [
                {"block_id": "d:p1:b1", "text": "Prepared by: Taylor - Operations"},
                {"block_id": "d:p1:b2", "text": "Settlement terms: 37 days"},
            ],
        }
    ]


def test_source_only_inventory_corrects_meaning_and_adds_numeric_terms_with_traceability():
    quote = "Prepared by: Taylor - Operations"
    wrong = fact("Taylor", "approver.name", quote)
    draft = {
        "document_type": "invoice",
        "observations": [wrong],
        "uncertainties": [],
        "page_coverage": ["d:p1"],
    }
    inventory = SemanticInventory(
        facts=[
            fact("Taylor", "preparer.name", quote),
            fact("Operations", "preparer.role", quote),
            fact(
                "37",
                "terms.duration",
                "Settlement terms: 37 days",
                group="terms",
                value_type="number",
                unit="days",
                block="d:p1:b2",
            ),
        ],
        reviewed_page_ids=["d:p1"],
        unresolved_checks=[],
    )
    result = reconcile_semantics(draft, inventory, evidence(), "d")
    assert draft["observations"][0]["field_key"] == "approver.name"
    assert [obs["field_key"] for obs in result["observations"]] == [
        "preparer.name",
        "preparer.role",
        "terms.duration",
    ]
    assert result["observations"][-1]["normalized_value"] == "37"
    assert result["semantic_review"]["changes"][0]["before"]["field_key"] == "approver.name"


def test_inventory_must_be_grounded_and_does_not_merge_different_physical_roles():
    pages = evidence()
    pages[0]["blocks"].append({"block_id": "d:p1:b3", "text": "Approved by: Taylor - Manager"})
    first = fact("Taylor", "approver.name", "Prepared by: Taylor - Operations")
    second = fact("Taylor", "approver.name", "Approved by: Taylor - Manager", block="d:p1:b3")
    draft = {"observations": [first, second], "uncertainties": [], "page_coverage": ["d:p1"]}
    inventory = SemanticInventory(
        facts=[fact("Taylor", "preparer.name", first["quote"])],
        reviewed_page_ids=["d:p1"],
        unresolved_checks=[],
    )
    result = reconcile_semantics(draft, inventory, pages, "d")
    assert [obs["field_key"] for obs in result["observations"]] == [
        "preparer.name",
        "approver.name",
    ]
    inventory.facts[0].raw_value = "An invented name"
    with pytest.raises(ValueError, match="raw_value"):
        reconcile_semantics(draft, inventory, pages, "d")


def test_semantic_scope_cannot_overwrite_table_cells_or_erase_row_grouping():
    row = fact(
        "7", "item.quantity", "Widget 7 boxes", group="row-a", value_type="number", unit="boxes"
    )
    pages = [
        {
            "page_id": "d:p1",
            "input_method": "native_text",
            "blocks": [{"block_id": "d:p1:b1", "text": row["quote"]}],
        }
    ]
    inventory = SemanticInventory(
        facts=[fact("7", "terms.quantity", row["quote"], value_type="number", unit="boxes")],
        reviewed_page_ids=["d:p1"],
        unresolved_checks=[],
    )
    draft = {"observations": [row], "uncertainties": [], "page_coverage": ["d:p1"]}
    with pytest.raises(ValueError, match="scope excludes"):
        reconcile_semantics(draft, inventory, pages, "d")
    assert draft["observations"][0]["group_key"] == "row-a"


@pytest.mark.asyncio
async def test_semantic_model_sees_original_source_without_draft_labels():
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        return_value={
            "content": json.dumps(
                {"facts": [], "reviewed_page_ids": ["p1"], "unresolved_checks": ["Vai trò chưa rõ"]}
            )
        }
    )
    draft = {
        "document_type": "invoice",
        "observations": [fact("Taylor", "wrong_draft_label", "Prepared by: Taylor - Operations")],
        "uncertainties": [],
        "page_coverage": ["d:p1"],
    }
    result = await review_source_semantics(client, "audit", "d", draft, evidence(), {})
    messages = client.complete.call_args.args[3]
    assert "wrong_draft_label" not in json.dumps(messages)
    assert "Prepared by" in messages[1]["content"]
    assert result["uncertainties"] == ["Vai trò chưa rõ"]


@pytest.mark.parametrize("separate_groups", [False, True])
def test_duplicate_actor_labels_on_one_source_are_resolved_but_distinct_records_stay_ambiguous(
    separate_groups,
):
    quote = "Prepared by: Taylor - Operations"
    draft = dict(
        document_type="invoice",
        observations=[
            fact("Taylor", "approver.name", quote, group="first" if separate_groups else None),
            fact("Taylor", "issuer.name", quote, group="second" if separate_groups else None),
        ],
        uncertainties=[],
        page_coverage=["d:p1"],
    )
    inventory = SemanticInventory(
        facts=[fact("Taylor", "preparer.name", quote)],
        reviewed_page_ids=["d:p1"],
        unresolved_checks=[],
    )
    result = reconcile_semantics(draft, inventory, evidence(), "d")
    assert not result["uncertainties"]
    assert len(result["observations"]) == 2
    assert all(
        o["field_key"] == "preparer.name" and o["raw_value"] == "Taylor"
        for o in result["observations"]
    )
    assert len(result["semantic_review"]["changes"]) == 2
    assert draft["observations"][0]["field_key"] == "approver.name"


def test_duplicate_narrow_and_broad_citations_share_one_unique_physical_actor():
    pages = evidence()
    quote = pages[0]["blocks"][0]["text"]
    wide = fact("Taylor", "approver.name", quote, group=None)
    wide["block_ids"] = [b["block_id"] for b in pages[0]["blocks"]]
    narrow = fact("Taylor", "issuer.name", "Taylor", group="untrusted-draft-group")
    draft = {"observations": [wide, narrow], "uncertainties": [], "page_coverage": ["d:p1"]}
    inventory = SemanticInventory(
        facts=[fact("Taylor", "preparer.name", quote)],
        reviewed_page_ids=["d:p1"],
        unresolved_checks=[],
    )
    result = reconcile_semantics(draft, inventory, pages, "d")
    assert not result["uncertainties"]
    assert all(o["field_key"] == "preparer.name" for o in result["observations"])


def test_out_of_scope_identifier_cannot_abort_or_weaken_actor_validation():
    payload = dict(
        facts=[
            fact("Taylor", "preparer.name", "Prepared by: Taylor - Operations"),
            fact("DOC-Z8", "document_number", "Document DOC-Z8", value_type="identifier"),
        ],
        reviewed_page_ids=["d:p1"],
        unresolved_checks=[],
    )
    inventory, rejected = parse_semantic_inventory(payload)
    assert len(inventory.facts) == 1 and len(rejected) == 1
    assert len(payload["facts"]) == 2
    payload["facts"][0]["field_key"] = "invalid_actor_field"
    with pytest.raises(ValueError, match="Actor fields"):
        parse_semantic_inventory(payload)
