from decimal import Decimal

import pytest

from app.features.audits.calculator import Calculator
from app.features.audits.proofs import CheckDefinition
from app.features.audits.reviewer import POLICY
from app.features.audits.schemas import AuditResult, Finding
from app.features.audits.verification import mislabeled_item, verify_result
from app.features.extraction.normalization import ground, normalize


def obs(id, value, unit="VND", doc="d1", type="money"):
    return {
        "id": id,
        "document_id": doc,
        "value_type": type,
        "normalized_value": value,
        "raw_value": value,
        "unit": unit,
        "quote": value,
        "grounding": "text_verified",
        "field_key": "document_number" if type == "identifier" else "amount",
    }


def test_identifier_comparison_preserves_leading_zeroes_and_does_not_use_amount_tolerance():
    calculator = Calculator(
        [obs("a", "00123", None, type="identifier"), obs("b", "123", None, type="identifier")],
        {"amount_tolerance": {"value": "100"}},
    )
    result = calculator.calculate({"operation": "compare", "operands": ["a", "b"]})
    assert result["unit"] == "identity"
    assert result["comparison"] == {"status": "fail", "difference": None}
    with pytest.raises(ValueError):
        calculator.calculate({"operation": "subtract", "operands": ["a", "b"]})
    with pytest.raises(ValueError):
        calculator.calculate({"operation": "compare", "operands": ["a", "b"], "relation": "lte"})


def test_item_label_must_match_cited_rows_but_aggregate_can_cover_multiple_rows():
    registry = {
        "code_a": {
            **obs("code_a", "A-1", type="identifier"),
            "field_key": "item.code",
            "group_key": "a",
        },
        "amount_a": {**obs("amount_a", "100"), "field_key": "item.amount", "group_key": "a"},
        "code_b": {
            **obs("code_b", "B-2", type="identifier"),
            "field_key": "item.code",
            "group_key": "b",
        },
        "amount_b": {**obs("amount_b", "120"), "field_key": "item.amount", "group_key": "b"},
    }
    finding = Finding(
        category="amount",
        severity="high",
        kind="numerical",
        title="B-2 mismatch",
        explanation="Reported amount differs",
        observation_ids=["amount_a"],
    )
    assert mislabeled_item(finding, registry)
    finding.title = "A-1 mismatch"
    assert not mislabeled_item(finding, registry)
    finding.title = "A-1 and B-2 contribute to total"
    finding.observation_ids = ["amount_a", "amount_b"]
    assert not mislabeled_item(finding, registry)


@pytest.mark.parametrize(
    "raw,type,expected",
    [
        ("52,250,000", "money", "52250000"),
        ("1.250.000", "money", "1250000"),
        ("0.10", "number", "0.10"),
        ("1,25", "number", None),
        ("888800001042", "identifier", "888800001042"),
        ("2026-09-28", "date", "2026-09-28"),
        ("NaN", "number", None),
    ],
)
def test_conservative_normalization(raw, type, expected):
    assert normalize(raw, type) == expected


def test_exact_arithmetic_and_chained_calculations():
    calculator = Calculator(
        [obs("q", "20", "piece", type="number"), obs("p", "150000"), obs("reported", "3200000")],
        POLICY,
    )
    line = calculator.calculate(
        {"operation": "multiply", "operands": ["q", "p"], "reported_observation_id": "reported"}
    )
    assert Decimal(line["result"]) == Decimal("3000000")
    assert line["comparison"] == {"reported": "3200000", "difference": "-200000", "status": "fail"}
    diff = calculator.calculate({"operation": "subtract", "operands": ["reported", line["id"]]})
    assert diff["result"] == "200000"
    assert set(diff["observation_ids"]) == {"q", "p", "reported"}


def test_invalid_derived_comparisons_are_rejected_before_execution():
    calculator = Calculator([obs("total", "100"), obs("tax", "10")], POLICY)
    with pytest.raises(ValueError, match="at least two operands"):
        calculator.calculate(
            {"operation": "multiply", "operands": ["total"], "reported_observation_id": "tax"}
        )
    with pytest.raises(ValueError, match="separate reported observation"):
        calculator.calculate(
            {
                "operation": "subtract",
                "operands": ["total", "tax"],
                "reported_observation_id": "total",
            }
        )
    assert not calculator.ledger


def test_explicit_percentage_text_is_typed_with_original_value_preserved():
    extraction = {
        "observations": [
            {
                "field_key": "tax_rate",
                "value_type": "text",
                "raw_value": "10%",
                "page_id": "p1",
                "block_ids": [],
                "quote": "Tax 10%",
                "group_key": None,
                "unit": None,
            }
        ],
        "page_coverage": ["p1"],
        "uncertainties": [],
    }
    result = ground(
        extraction,
        [
            {
                "page_id": "p1",
                "input_method": "native_text",
                "blocks": [{"block_id": "b1", "text": "Tax 10%"}],
            }
        ],
        "d1",
    )
    rate = result["observations"][0]
    assert (rate["raw_value"], rate["normalized_value"], rate["unit"]) == ("10%", "10", "%")
    assert rate["extracted_value_type"] == "text"
    assert rate["value_type"] == "number"


def test_money_inherits_only_an_unambiguous_declared_currency_with_provenance():
    observations = [
        {
            "field_key": "currency",
            "value_type": "text",
            "raw_value": "JPY",
            "page_id": "p1",
            "quote": "JPY",
            "block_ids": [],
            "group_key": None,
            "unit": None,
        },
        {
            "field_key": "total",
            "value_type": "money",
            "raw_value": "100",
            "page_id": "p1",
            "quote": "100",
            "block_ids": [],
            "group_key": None,
            "unit": None,
        },
    ]
    pages = [
        {
            "page_id": "p1",
            "input_method": "native_text",
            "blocks": [{"block_id": "b1", "text": "JPY 100 USD"}],
        }
    ]
    extraction = {"observations": observations, "page_coverage": ["p1"], "uncertainties": []}
    result = ground(extraction, pages, "d1")
    assert result["observations"][1]["unit"] == "JPY"
    assert result["observations"][1]["unit_observation_ids"] == ["d1:o1"]
    observations.append({**observations[0], "raw_value": "USD", "quote": "USD"})
    assert ground(extraction, pages, "d1")["observations"][1]["unit"] is None


def test_matching_bank_accounts_cannot_establish_document_relationship():
    observations = [
        {**obs("a", "123456", None, "d1", "identifier"), "field_key": "bank.account"},
        {**obs("b", "123456", None, "d2", "identifier"), "field_key": "bank.account"},
    ]
    result = AuditResult(
        findings=[],
        assessed_topics=[],
        unresolved_checks=[],
        links=[
            {
                "from_document": "d1",
                "to_document": "d2",
                "status": "supported",
                "observation_ids": ["a", "b"],
                "explanation": "Matching accounts",
            }
        ],
    )
    with pytest.raises(ValueError, match="explicit document/reference identifiers"):
        verify_result(result, Calculator(observations, POLICY), "cross")


def test_equal_value_cross_evidence_is_preserved_as_passing_check():
    observations = [
        obs("name1", "Supplier", None, "d1", "text"),
        obs("name2", "Supplier", None, "d2", "text"),
    ]
    result = AuditResult(
        findings=[
            Finding(
                category="beneficiary_name",
                severity="low",
                kind="evidence",
                title="Matching names",
                explanation="Both observed names agree",
                observation_ids=["name1", "name2"],
            )
        ],
        assessed_topics=[],
        unresolved_checks=[],
        links=[],
    )
    verified = verify_result(result, Calculator(observations, POLICY), "cross")
    assert not verified["findings"]
    assert not verified["unresolved_checks"]
    assert verified["assessed_topics"] == ["beneficiary_name"]
    assert len(verified["excluded_passing_checks"]) == 1


@pytest.mark.parametrize("raw,quote", [("10%", "VAT 10%"), ("10", "VAT 10 %")])
def test_percentage_inference_does_not_multiply_tax_by_one_hundred(raw, quote):
    rate = obs("rate", "10", None, type="number")
    rate.update(raw_value=raw, quote=quote)
    calculator = Calculator([obs("net", "100", "JPY"), rate, obs("tax", "10", "JPY")], POLICY)
    result = calculator.calculate(
        {"operation": "multiply", "operands": ["net", "rate"], "reported_observation_id": "tax"}
    )
    assert result["result"] == "10"
    assert result["unit"] == "JPY"
    assert result["comparison"]["status"] == "pass"


def test_compare_never_compares_a_difference_against_an_original_value():
    calculator = Calculator([obs("a", "100"), obs("b", "100"), obs("c", "120")], POLICY)
    passing = calculator.calculate(
        {"operation": "compare", "operands": ["a", "b"], "reported_observation_id": "a"}
    )
    assert passing["comparison"] == {"difference": "0", "status": "pass"}
    failing = calculator.calculate({"operation": "compare", "operands": ["c", "a"]})
    assert failing["comparison"] == {"difference": "20", "status": "fail"}


def test_decimal_zero_difference_does_not_support_a_mismatch_finding():
    calculator = Calculator([obs("a", "0.10"), obs("b", "0.1")], POLICY)
    calculation = calculator.calculate({"operation": "subtract", "operands": ["a", "b"]})
    result = AuditResult.model_validate(
        {
            "findings": [
                {
                    "category": "amount",
                    "severity": "high",
                    "kind": "numerical",
                    "title": "Mismatch",
                    "explanation": "Amounts differ",
                    "observation_ids": ["a", "b"],
                    "calculation_ids": [calculation["id"]],
                }
            ],
            "assessed_topics": [],
            "unresolved_checks": [],
        }
    )
    assert verify_result(result, calculator, "internal")["findings"] == []


@pytest.mark.parametrize(
    "calculation_request",
    [
        {"operation": "sum", "operands": ["unknown"]},
        {"operation": "divide", "operands": ["vnd", "zero"]},
        {"operation": "sum", "operands": ["vnd", "usd"]},
        {"operation": "__import__", "operands": ["vnd"]},
        {"operation": "sum", "operands": ["unreadable"]},
    ],
)
def test_invalid_tool_requests(calculation_request):
    calculator = Calculator(
        [obs("vnd", "5"), obs("usd", "5", "USD"), obs("zero", "0"), obs("unreadable", None)], POLICY
    )
    with pytest.raises(ValueError):
        calculator.calculate(calculation_request)


def test_date_calculation():
    calculator = Calculator(
        [obs("date", "2026-09-28", None, type="date"), obs("days", "15", "days", type="number")],
        POLICY,
    )
    assert (
        calculator.calculate({"operation": "date_add_days", "operands": ["date", "days"]})["result"]
        == "2026-10-13"
    )


def extracted_observation(raw="100", page_id="d:p1", quote="Total 100"):
    return {
        "field_key": "total",
        "value_type": "money",
        "raw_value": raw,
        "page_id": page_id,
        "block_ids": [],
        "quote": quote,
        "group_key": None,
        "role": None,
        "unit": "VND",
    }


def test_page_conflicts_are_preserved():
    pages = [
        {
            "page_id": "d:p1",
            "input_method": "native_text",
            "blocks": [{"block_id": "b1", "text": "Total 100"}],
        },
        {
            "page_id": "d:p2",
            "input_method": "native_text",
            "blocks": [{"block_id": "b2", "text": "Total 200"}],
        },
    ]
    payload = {
        "observations": [
            extracted_observation(),
            extracted_observation("200", "d:p2", "Total 200"),
        ],
        "uncertainties": [],
        "page_coverage": ["d:p1", "d:p2"],
    }
    result = ground(payload, pages, "d")
    assert [o["normalized_value"] for o in result["observations"]] == ["100", "200"]
    assert len({o["id"] for o in result["observations"]}) == 2


@pytest.mark.parametrize("change", ["quote", "page", "coverage", "value"])
def test_ungrounded_extraction_rejected(change):
    pages = [
        {
            "page_id": "d:p1",
            "input_method": "native_text",
            "blocks": [{"block_id": "b1", "text": "Total 100"}],
        }
    ]
    observation = extracted_observation()
    payload = {"observations": [observation], "uncertainties": [], "page_coverage": ["d:p1"]}
    if change == "quote":
        observation["quote"] = "fabricated 100"
    if change == "page":
        observation["page_id"] = "unknown"
    if change == "coverage":
        payload["page_coverage"] = []
    if change == "value":
        observation["raw_value"] = "200"
    with pytest.raises(ValueError):
        ground(payload, pages, "d")


def test_visual_evidence_is_not_marked_text_verified():
    result = ground(
        {"observations": [extracted_observation()], "uncertainties": [], "page_coverage": ["d:p1"]},
        [{"page_id": "d:p1", "input_method": "vision", "blocks": []}],
        "d",
    )
    assert result["observations"][0]["grounding"] == "visual_unverified"


def test_numerical_finding_requires_calculation_and_cross_evidence():
    calculator = Calculator(
        [
            obs("a", "100", doc="d1"),
            obs("b", "120", doc="d2"),
            obs("number", "INV-A", None, doc="d1", type="identifier"),
            obs("reference", "INV-A", None, doc="d2", type="identifier"),
        ],
        POLICY,
    )
    payload = {
        "findings": [
            {
                "category": "amount",
                "severity": "high",
                "kind": "numerical",
                "title": "Mismatch",
                "explanation": "Amounts differ",
                "observation_ids": ["a", "b"],
                "calculation_ids": [],
                "policy_refs": [],
            }
        ],
        "assessed_topics": ["amounts"],
        "unresolved_checks": [],
        "links": [
            {
                "from_document": "d1",
                "to_document": "d2",
                "status": "supported",
                "observation_ids": ["number", "reference"],
                "explanation": "Matching invoice reference",
            }
        ],
    }
    assert verify_result(AuditResult.model_validate(payload), calculator, "cross")[
        "rejected_claims"
    ]

    calculator.register_checks(
        [
            CheckDefinition(
                id="amount",
                purpose="Compare amounts",
                left={"observation_id": "a"},
                right={"observation_id": "b"},
            )
        ]
    )
    calc = calculator.calculate(
        {"operation": "compare", "operands": ["a", "b"], "check_id": "amount"}
    )
    payload["findings"][0]["check_ids"] = ["amount"]
    payload["findings"][0]["calculation_ids"] = [calc["id"]]
    assert (
        len(verify_result(AuditResult.model_validate(payload), calculator, "cross")["findings"])
        == 1
    )
    payload["findings"][0]["observation_ids"] = ["a"]
    verified = verify_result(AuditResult.model_validate(payload), calculator, "cross")
    assert verified["rejected_claims"] == []
    assert verified["findings"][0]["observation_ids"] == ["a", "b"]
    payload["findings"][0]["observation_ids"] = ["unknown"]
    assert verify_result(AuditResult.model_validate(payload), calculator, "cross")[
        "rejected_claims"
    ]


def test_unreadable_or_empty_extraction_is_explicitly_incomplete():
    result = ground(
        {"observations": [], "uncertainties": [], "page_coverage": ["scan:p1"]},
        [{"page_id": "scan:p1", "input_method": "vision", "blocks": []}],
        "scan",
    )
    assert result["uncertainties"]


def test_cross_document_claims_require_related_documents_even_with_correct_math():
    calculator = Calculator([obs("a", "100", doc="d1"), obs("b", "120", doc="d2")], POLICY)
    calc = calculator.calculate({"operation": "compare", "operands": ["a", "b"]})
    result = AuditResult.model_validate(
        {
            "findings": [
                {
                    "category": "amount",
                    "kind": "numerical",
                    "severity": "high",
                    "title": "Different amounts",
                    "explanation": "Do not assume a transaction",
                    "observation_ids": ["a", "b"],
                    "calculation_ids": [calc["id"]],
                }
            ],
            "assessed_topics": [],
            "unresolved_checks": [],
            "links": [],
        }
    )
    verified = verify_result(result, calculator, "cross")
    assert verified["findings"] == []
    assert "relationship" in verified["rejected_claims"][0]["reason"]
