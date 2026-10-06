"""Consolidation retains qualitative coverage and independent meaning checks."""

import json
from unittest.mock import AsyncMock

import pytest

from app.features.audits.calculator import Calculator
from app.features.audits.proofs import CheckDefinition
from app.features.audits.reviewer import (
    POLICY,
    compact_evidence,
    compact_ledger,
    focused_evidence,
    review,
    review_ledger,
    validate_item_subjects,
)
from app.features.audits.schemas import Finding


def test_scope_notes_explain_blockers_and_keep_optional_topics_separate():
    from app.features.audits.proofs import CheckPlan

    with pytest.raises(ValueError, match="not a bare check ID"):
        CheckPlan(checks=[], unresolved_checks=["check_future_event"])
    plan = CheckPlan(
        checks=[],
        unresolved_checks=["Required evidence cannot be read"],
        not_applicable_topics=["Future activity has no source obligation"],
    )
    assert plan.unresolved_checks == ["Required evidence cannot be read"]
    assert plan.not_applicable_topics == ["Future activity has no source obligation"]


def test_aggregate_review_keeps_unplanned_financial_components_as_counter_evidence():
    observations = [
        {
            "id": "total",
            "document_id": "doc",
            "field_key": "total",
            "value_type": "money",
            "normalized_value": "44",
            "quote": "Total 44",
        },
        {
            "id": "base",
            "document_id": "doc",
            "field_key": "base",
            "value_type": "money",
            "normalized_value": "40",
            "quote": "Base 40",
        },
        {
            "id": "tax",
            "document_id": "doc",
            "field_key": "tax",
            "value_type": "money",
            "normalized_value": "4",
            "quote": "Tax 4",
        },
        {
            "id": "unrelated",
            "document_id": "other",
            "field_key": "tax",
            "value_type": "money",
            "normalized_value": "99",
            "quote": "Tax 99",
        },
    ]
    assert {o["id"] for o in focused_evidence(observations, {"total"})["observations"]} == {
        "total",
        "base",
        "tax",
    }


def test_focused_review_retains_cross_page_counter_evidence_and_complete_item_records():
    observations = [
        {
            "id": "total_1",
            "document_id": "doc",
            "page_id": "p1",
            "field_key": "total",
            "normalized_value": "60",
            "quote": "Total 60",
        },
        {
            "id": "total_2",
            "document_id": "doc",
            "page_id": "p2",
            "field_key": "total",
            "normalized_value": "70",
            "quote": "Total 70",
        },
        {
            "id": "code_1",
            "document_id": "doc",
            "page_id": "p1",
            "field_key": "item.code",
            "group_key": "row1",
            "normalized_value": "SKU-X",
            "quote": "SKU-X 2",
        },
        {
            "id": "qty_1",
            "document_id": "doc",
            "page_id": "p1",
            "field_key": "item.quantity",
            "group_key": "row1",
            "normalized_value": "2",
            "quote": "SKU-X 2",
        },
        {
            "id": "code_2",
            "document_id": "doc",
            "page_id": "p2",
            "field_key": "item.code",
            "group_key": "row2",
            "normalized_value": "SKU-X",
            "quote": "SKU-X 3",
        },
        {
            "id": "qty_2",
            "document_id": "doc",
            "page_id": "p2",
            "field_key": "item.quantity",
            "group_key": "row2",
            "normalized_value": "3",
            "quote": "SKU-X 3",
        },
        {
            "id": "unrelated",
            "document_id": "other",
            "page_id": "p1",
            "field_key": "total",
            "normalized_value": "90",
            "quote": "Total 90",
        },
    ]
    evidence = focused_evidence(observations, {"total_1", "qty_1"})
    assert {o["id"] for o in evidence["observations"]} == {
        "total_1",
        "total_2",
        "qty_1",
        "qty_2",
        "code_1",
        "code_2",
    }
    assert set(evidence["source_quotes"].values()) == {"Total 60", "Total 70", "SKU-X 2", "SKU-X 3"}


def test_compaction_preserves_occurrences_quotes_and_calculation_outcomes():
    observations = [
        {
            "id": "a",
            "page_id": "p1",
            "raw_value": "00042",
            "normalized_value": "00042",
            "quote": "Account 00042",
        },
        {
            "id": "b",
            "page_id": "p2",
            "raw_value": "00042",
            "normalized_value": "00042",
            "quote": "Account 00042",
        },
    ]
    compact = compact_evidence(observations)
    assert len(compact["observations"]) == 2
    assert len(compact["source_quotes"]) == 1
    assert {o["page_id"] for o in compact["observations"]} == {"p1", "p2"}
    assert all(o["normalized_value"] == "00042" for o in compact["observations"])
    result = {
        "id": "calc_1",
        "result": "-7",
        "request": {"check_id": "c"},
        "comparison": {"status": "fail", "difference": "-7"},
    }
    assert compact_ledger([result]) == [result]


def test_terminal_review_values_preserve_arithmetic_and_full_saved_dependencies():
    from app.features.audits.proofs import execute_checks

    observations = [
        {"id": "quantity", "value_type": "number", "normalized_value": "3", "unit": "items"},
        {"id": "price", "value_type": "money", "normalized_value": "11", "unit": "EUR"},
        {"id": "reported", "value_type": "money", "normalized_value": "35", "unit": "EUR"},
    ]
    calculator = Calculator(observations, POLICY)
    check = CheckDefinition.model_validate(
        {
            "id": "line",
            "purpose": "Check line amount",
            "left": {
                "operation": "multiply",
                "operands": [{"observation_id": "quantity"}, {"observation_id": "price"}],
            },
            "right": {"observation_id": "reported"},
        }
    )
    execute_checks([check], calculator)
    compact = review_ledger(calculator)
    assert len(compact) == 1
    assert compact[0]["left_value"] == "33"
    assert compact[0]["right_value"] == "35"
    assert compact[0]["comparison"] == {"status": "fail", "difference": "-2"}
    assert set(compact[0]["observation_ids"]) == {"quantity", "price", "reported"}
    assert len(calculator.ledger) == 2


@pytest.mark.asyncio
async def test_account_comparison_is_planned_reported_and_adjudicated_in_main_cross_calls():
    observations = [
        {
            "id": "ref_a",
            "document_id": "A",
            "field_key": "document_number",
            "value_type": "identifier",
            "raw_value": "DOC-Z",
            "normalized_value": "DOC-Z",
            "quote": "Invoice DOC-Z",
        },
        {
            "id": "ref_b",
            "document_id": "B",
            "field_key": "invoice_reference",
            "value_type": "identifier",
            "raw_value": "DOC-Z",
            "normalized_value": "DOC-Z",
            "quote": "Invoice reference DOC-Z",
        },
        {
            "id": "account_a",
            "document_id": "A",
            "field_key": "bank.account",
            "value_type": "identifier",
            "raw_value": "00123",
            "normalized_value": "00123",
            "quote": "Supplier account 00123",
        },
        {
            "id": "account_b",
            "document_id": "B",
            "field_key": "beneficiary.account",
            "value_type": "identifier",
            "raw_value": "00456",
            "normalized_value": "00456",
            "quote": "Beneficiary account 00456",
        },
    ]
    for observation in observations:
        observation["grounding"] = "text_verified"
    payloads = [
        {
            "links": [
                {
                    "from_document": "d1",
                    "to_document": "d2",
                    "status": "supported",
                    "observation_ids": ["o1", "o2"],
                    "explanation": "Explicit reference",
                }
            ]
        },
        {
            "checks": [],
            "unresolved_checks": [],
        },
        {
            "comparisons": [
                {"purpose": "Compare payment accounts", "observation_ids": ["o3", "o4"]}
            ],
            "unresolved_checks": [],
        },
        {
            "findings": [
                {
                    "category": "account",
                    "kind": "evidence",
                    "severity": "high",
                    "title": "Account discrepancy",
                    "explanation": "Different accounts",
                    "observation_ids": ["o3", "o4"],
                    "check_ids": [],
                    "policy_refs": [],
                }
            ],
            "assessed_topics": ["accounts"],
            "unresolved_checks": [],
        },
        {
            "checks": [],
            "findings": [
                {
                    "id": "0",
                    "verdict": "supported",
                    "observation_ids": ["o3", "o4"],
                    "reason": "Different accounts",
                    "atomicity": "atomic",
                    "explanation_completeness": "complete",
                }
            ],
        },
    ]
    client = type("Client", (), {})()
    client.complete = AsyncMock(side_effect=[{"content": json.dumps(p)} for p in payloads])
    result = await review(client, "audit", "cross", observations, {})
    assert client.complete.await_count == 5
    assert [call.args[1] for call in client.complete.await_args_list] == [
        "audit_relationships",
        "audit_plan_cross",
        "audit_identity_plan",
        "audit_findings_cross",
        "audit_meaning_cross",
    ]
    assert result["findings"][0]["observation_ids"] == ["account_a", "account_b"]
    assert result["findings"][0]["semantic_review"]["verdict"] == "supported"
    assert result["comparison_plan"][0]["observation_ids"] == ["account_a", "account_b"]
    assert result["unresolved_checks"] == []
    meaning_input = json.loads(client.complete.await_args_list[-1].args[3][1]["content"])
    assert meaning_input["qualitative_comparisons"][0]["observation_ids"] == ["o3", "o4"]
    assert meaning_input["check_definitions"] == []


def test_independent_item_subjects_require_separate_claims_but_aggregates_remain_valid():
    observations = []
    checks = []
    for index, code in enumerate(["PRODUCT-A", "PRODUCT-B"]):
        for doc in ["A", "B"]:
            observations.extend(
                [
                    {
                        "id": f"{doc}_code_{index}",
                        "document_id": doc,
                        "field_key": "item.code",
                        "value_type": "identifier",
                        "normalized_value": code,
                        "group_key": str(index),
                    },
                    {
                        "id": f"{doc}_qty_{index}",
                        "document_id": doc,
                        "field_key": "item.quantity",
                        "value_type": "number",
                        "normalized_value": "4",
                        "group_key": str(index),
                    },
                ]
            )
        checks.append(
            CheckDefinition.model_validate(
                {
                    "id": f"row_{index}",
                    "purpose": "Compare item quantity",
                    "left": {"observation_id": f"A_qty_{index}"},
                    "right": {"observation_id": f"B_qty_{index}"},
                }
            )
        )
    calculator = Calculator(observations, POLICY)
    calculator.register_checks(checks)
    finding = Finding(
        category="items",
        kind="numerical",
        title="Bundled rows",
        explanation="Two independent products",
        severity="high",
        observation_ids=["A_qty_0", "B_qty_0", "A_qty_1", "B_qty_1"],
        check_ids=["row_0", "row_1"],
    )
    with pytest.raises(ValueError, match="Split independent item subjects"):
        validate_item_subjects(finding, calculator)
    validate_item_subjects(finding.model_copy(update={"check_ids": ["row_0"]}), calculator)
    aggregate = CheckDefinition.model_validate(
        {
            "id": "aggregate",
            "purpose": "Compare total quantity",
            "left": {
                "operation": "sum",
                "operands": [{"observation_id": "A_qty_0"}, {"observation_id": "A_qty_1"}],
            },
            "right": {
                "operation": "sum",
                "operands": [{"observation_id": "B_qty_0"}, {"observation_id": "B_qty_1"}],
            },
        }
    )
    calculator.register_checks([*checks, aggregate])
    validate_item_subjects(finding.model_copy(update={"check_ids": ["aggregate"]}), calculator)
