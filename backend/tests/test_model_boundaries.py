import json
from unittest.mock import AsyncMock

import pytest

from app.core.cloudflare import ProviderError
from app.features.audits.reviewer import grouped_item_view, review, validated_json
from app.features.extraction.service import extract_document


def contract(a, b):
    return {
        "id": "check",
        "purpose": "Compare source amounts",
        "left": {"observation_id": a},
        "right": {"observation_id": b},
        "relation": "equals",
    }


@pytest.mark.asyncio
async def test_truncated_json_uses_one_repair_and_never_accepts_partial_content():
    client = type("Client", (), {})()
    failure = ProviderError(
        "Token limit", "truncated_output", {"content": '{"title":' + " \n" * 5000}
    )
    client.complete = AsyncMock(side_effect=[failure, {"content": '{"title":"review"}'}])
    messages = [{"role": "user", "content": "source facts"}]
    result = await validated_json(
        client, "audit", "audit_findings_internal", messages, lambda x: x, 100, {}
    )
    assert result == {"title": "review"}
    assert client.complete.await_count == 2
    assert messages[1]["content"] == '{"title":'
    assert client.complete.call_args.kwargs["schema"] is None
    assert "output_schema" in client.complete.call_args.args[3][-1]["content"]
    client.complete = AsyncMock(side_effect=[failure, failure])
    with pytest.raises(ProviderError):
        await validated_json(client, "audit", "audit_findings_internal", [], lambda x: x, 100, {})
    assert client.complete.await_count == 2


def test_model_item_view_preserves_conflicting_page_occurrences():
    observations = [
        {
            "id": "one",
            "document_id": "d",
            "field_key": "item.quantity",
            "group_key": "item-A",
            "normalized_value": "10",
            "page_id": "d:p1",
        },
        {
            "id": "two",
            "document_id": "d",
            "field_key": "item.quantity",
            "group_key": "item-A",
            "normalized_value": "12",
            "page_id": "d:p2",
        },
    ]
    view = grouped_item_view(observations)
    cells = view[0]["items"][0]["cells"]["item.quantity"]
    assert [(cell["value"], cell["page_id"]) for cell in cells] == [("10", "d:p1"), ("12", "d:p2")]


@pytest.mark.asyncio
async def test_extraction_repair_and_short_id_roundtrip():
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {"content": '{"bad":true}'},
            {
                "content": '{"document_type":"invoice","mixed_document":false,"observations":[{"field_key":"total","value_type":"money","raw_value":"100","group_key":null,"page_id":"p1","block_ids":["p1b1"],"quote":"Total 100","unit":"VND"}],"uncertainties":[],"page_coverage":["p1"]}'
            },
            {
                "content": json.dumps(
                    {
                        "reviewed_page_ids": ["p1"],
                        "corrections": [],
                        "additions": [],
                        "unresolved_checks": [],
                        "block_coverage": [
                            {"block_id": "p1b1", "disposition": "extracted", "reason": "Tổng tiền"}
                        ],
                    }
                )
            },
        ]
    )
    result = await extract_document(
        client,
        "a",
        "d",
        [
            {
                "page_id": "d:p1",
                "input_method": "native_text",
                "blocks": [{"block_id": "d:p1:b1", "text": "Total 100"}],
            }
        ],
        {},
    )
    assert result["observations"][0]["page_id"] == "d:p1"
    assert result["observations"][0]["block_ids"] == ["d:p1:b1"]
    assert client.complete.await_count == 3
    repair_messages = client.complete.call_args_list[1].args[3]
    assert not any(m["role"] == "assistant" for m in repair_messages)
    assert not any(m["content"] == '{"bad":true}' for m in repair_messages)
    assert result["schema_version"] == "extraction-v4-source-coverage"


@pytest.mark.asyncio
async def test_batch_calculation_and_aliases_restore_original_evidence_ids():
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {
                "content": json.dumps(
                    {
                        "checks": [contract("o1", "o2")],
                    }
                ),
            },
            {
                "content": '{"findings":[{"category":"amount","severity":"high","kind":"numerical","title":"Mismatch","explanation":"Difference 20","observation_ids":["o1","o2"],"calculation_ids":["calc_1"],"check_ids":["check"],"policy_refs":[]}],"assessed_topics":["amount"],"unresolved_checks":[],"links":[]}'
            },
            {
                "content": json.dumps(
                    {
                        "checks": [
                            {
                                "id": "check",
                                "verdict": "valid",
                                "observation_ids": ["o1", "o2"],
                                "reason": "Same obligation",
                            }
                        ],
                        "findings": [
                            {
                                "id": "0",
                                "verdict": "supported",
                                "observation_ids": ["o1", "o2"],
                                "reason": "Explanation matches proof",
                            }
                        ],
                    }
                )
            },
        ]
    )
    observations = [
        {
            "id": f"real:o{i}",
            "document_id": "real",
            "value_type": "money",
            "normalized_value": value,
            "raw_value": value,
            "unit": "VND",
            "quote": value,
        }
        for i, value in [(1, "100"), (2, "120")]
    ]
    result = await review(client, "a", "internal", observations, {})
    assert result["findings"][0]["observation_ids"] == ["real:o1", "real:o2"]
    assert result["calculations"][0]["request"]["operands"] == ["real:o1", "real:o2"]


@pytest.mark.asyncio
async def test_missing_or_unreadable_evidence_cannot_be_fabricated():
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        return_value={
            "content": '{"document_type":"invoice","observations":[{"field_key":"total","value_type":"money","raw_value":"999","group_key":null,"page_id":"p1","quote":"Total 999"}],"uncertainties":[],"page_coverage":["p1"]}'
        }
    )
    with pytest.raises(ValueError, match="Extraction validation failed"):
        await extract_document(
            client,
            "a",
            "d",
            [
                {
                    "page_id": "d:p1",
                    "input_method": "native_text",
                    "blocks": [{"block_id": "d:p1:b1", "text": "Total 100"}],
                }
            ],
            {},
        )
    assert client.complete.await_count == 2


@pytest.mark.asyncio
async def test_cross_plan_repairs_copied_invoice_value_before_review():
    observations = [
        {
            "id": f"real:o{i}",
            "document_id": document,
            "value_type": "money",
            "normalized_value": value,
            "raw_value": value,
            "unit": "VND",
            "quote": value,
        }
        for i, document, value in [
            (1, "request", "120"),
            (2, "request", "100"),
            (3, "invoice", "100"),
        ]
    ]
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {"content": '{"links": []}'},
            {
                "content": json.dumps(
                    {
                        "checks": [contract("o1", "o2")],
                    }
                )
            },
            {
                "content": json.dumps(
                    {
                        "checks": [contract("o1", "o3")],
                    }
                )
            },
            {
                "content": json.dumps(
                    {"findings": [], "unresolved_checks": [], "links": [], "assessed_topics": []}
                )
            },
        ]
    )
    client.complete.side_effect = [
        *client.complete.side_effect,
        {
            "content": json.dumps(
                {"findings": [], "unresolved_checks": [], "links": [], "assessed_topics": []}
            )
        },
        {
            "content": json.dumps(
                {
                    "checks": [
                        {
                            "id": "check",
                            "verdict": "valid",
                            "observation_ids": ["o1", "o3"],
                            "reason": "Same related obligation",
                        }
                    ],
                    "findings": [],
                }
            )
        },
    ]
    result = await review(client, "a", "cross", observations, {})
    assert client.complete.await_count == 7
    assert result["semantic_refinement"]["status"] == "failed"
    assert result["calculations"][0]["observation_ids"] == ["real:o1", "real:o3"]


@pytest.mark.asyncio
async def test_cross_cannot_repeat_local_arithmetic_as_a_cross_check():
    observations = [
        {
            "id": f"real:o{i}",
            "document_id": "invoice",
            "value_type": "number",
            "field_key": key,
            "normalized_value": value,
            "raw_value": value,
            "quote": value,
            "unit": None,
        }
        for i, key, value in [
            (1, "item.quantity", "2"),
            (2, "item.unit_price", "3"),
            (3, "item.amount", "7"),
        ]
    ]
    client = type("Client", (), {})()
    local = {
        "checks": [
            {
                "id": "local",
                "purpose": "Local arithmetic",
                "left": {
                    "operation": "multiply",
                    "operands": [{"observation_id": "o1"}, {"observation_id": "o2"}],
                },
                "right": {"observation_id": "o3"},
                "relation": "equals",
            }
        ]
    }
    client.complete = AsyncMock(
        side_effect=[
            {"content": '{"links":[]}'},
            {"content": json.dumps(local)},
            {"content": json.dumps(local)},
        ]
    )
    with pytest.raises(ValueError, match="at least two related documents"):
        await review(client, "audit", "cross", observations, {})
    assert client.complete.await_count == 3
