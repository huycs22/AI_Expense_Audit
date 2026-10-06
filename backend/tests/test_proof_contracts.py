import random
from copy import deepcopy
from decimal import Decimal

import pytest

from app.features.audits.calculator import Calculator
from app.features.audits.consolidation import consolidate_findings
from app.features.audits.proofs import CheckDefinition, execute_checks, validate_binding
from app.features.audits.reviewer import POLICY
from app.features.audits.schemas import AuditResult
from app.features.audits.verification import revalidate_review, verify_result


def source(ref):
    return {"observation_id": ref}


def expression(operation, *refs):
    return {
        "operation": operation,
        "operands": [source(ref) if isinstance(ref, str) else ref for ref in refs],
    }


def observation(ref, value, group=None, field="value"):
    return {
        "id": ref,
        "document_id": "doc",
        "field_key": field,
        "group_key": group,
        "normalized_value": str(value),
        "raw_value": str(value),
        "quote": str(value),
        "value_type": "money",
        "unit": "USD",
    }


@pytest.mark.parametrize("seed", range(12))
def test_wrong_intermediate_never_proves_balance_check_with_arbitrary_values(seed):
    rng = random.Random(seed)
    total, paid, po, requested = [Decimal(rng.randint(1, 100000)) / 100 for _ in range(4)]
    calc = Calculator(
        [
            observation(ref, value)
            for ref, value in zip(
                ["invoice", "paid", "po", "requested"], [total, paid, po, requested]
            )
        ],
        POLICY,
    )
    calc.register_checks(
        [
            CheckDefinition(
                id="balance",
                purpose="Requested amount against outstanding balance",
                left=source("requested"),
                right=expression("subtract", "invoice", "paid"),
                relation="lte",
            )
        ]
    )
    variance = calc.calculate({"operation": "subtract", "operands": ["invoice", "po"]})
    wrong = calc.calculate(
        {
            "operation": "compare",
            "operands": ["requested", variance["id"]],
            "relation": "lte",
            "check_id": "balance",
        }
    )
    assert validate_binding(wrong, calc)
    balance = calc.calculate({"operation": "subtract", "operands": ["invoice", "paid"]})
    correct = calc.calculate(
        {
            "operation": "compare",
            "operands": ["requested", balance["id"]],
            "relation": "lte",
            "check_id": "balance",
        }
    )
    assert validate_binding(correct, calc) is None
    assert Decimal(correct["result"]) == requested - (total - paid)


def test_equal_results_and_same_source_set_do_not_prove_different_formula():
    calc = Calculator([observation("a", 100), observation("b", 0), observation("c", 0)], POLICY)
    calc.register_checks(
        [
            CheckDefinition(
                id="check",
                purpose="Reconciliation",
                left=expression("subtract", "a", expression("subtract", "b", "c")),
                right=source("a"),
            )
        ]
    )
    first = calc.calculate({"operation": "subtract", "operands": ["a", "b"]})
    wrong = calc.calculate(
        {
            "operation": "subtract",
            "operands": [first["id"], "c"],
            "reported_observation_id": "a",
            "check_id": "check",
        }
    )
    assert wrong["comparison"]["status"] == "pass"
    assert validate_binding(wrong, calc)


def test_numerical_claim_cannot_borrow_another_checks_failed_proof():
    calc = Calculator([observation("a", 100), observation("b", 120)], POLICY)
    calc.register_checks(
        [
            CheckDefinition(
                id="amount", purpose="Compare amounts", left=source("a"), right=source("b")
            )
        ]
    )
    proof = calc.calculate({"operation": "compare", "operands": ["a", "b"], "check_id": "amount"})
    finding = {
        "kind": "numerical",
        "severity": "high",
        "category": "arbitrary_category",
        "title": "Mismatch",
        "explanation": "A mismatch",
        "observation_ids": ["a", "b"],
        "calculation_ids": [proof["id"]],
        "check_ids": ["unrelated"],
    }
    result = AuditResult(findings=[finding], assessed_topics=[], unresolved_checks=[])
    assert verify_result(result, calc, "internal")["rejected_claims"]
    finding["check_ids"] = ["amount"]
    verified = verify_result(
        AuditResult(findings=[finding], assessed_topics=[], unresolved_checks=[]), calc, "internal"
    )
    assert len(verified["findings"]) == 1
    assert revalidate_review(verified, list(calc.observations.values()), POLICY, "internal")[
        "findings"
    ]
    legacy = deepcopy(verified)
    legacy.pop("check_definitions")
    legacy["findings"][0].pop("check_ids")
    assert revalidate_review(legacy, list(calc.observations.values()), POLICY, "internal")[
        "unresolved_checks"
    ]


@pytest.mark.parametrize(
    "citations", ["terminal", "dependencies", "checks_only", "unrelated", "intermediate_only"]
)
def test_terminal_proofs_distinguish_valid_dependencies_from_unrelated_calculations(citations):
    observations = [
        observation("count", 7),
        observation("price", 13),
        observation("reported", 95),
        observation("other", 8),
    ]
    calc = Calculator(observations, POLICY)
    check = CheckDefinition(
        id="row",
        purpose="Row arithmetic",
        left=expression("multiply", "count", "price"),
        right=source("reported"),
    )
    results = execute_checks([check], calc)
    unrelated = calc.calculate({"operation": "sum", "operands": ["price", "other"]})
    refs = {
        "terminal": [results[-1]["id"]],
        "dependencies": [item["id"] for item in results],
        "checks_only": [],
        "unrelated": [results[-1]["id"], unrelated["id"]],
        "intermediate_only": [results[0]["id"]],
    }
    proposed = {
        "kind": "numerical",
        "severity": "high",
        "category": "arbitrary",
        "title": "Row mismatch",
        "explanation": "The reported amount does not reconcile",
        "observation_ids": ["count", "price", "reported"],
        "check_ids": ["row"],
        "calculation_ids": refs[citations],
    }
    verified = verify_result(
        AuditResult(findings=[proposed], assessed_topics=[], unresolved_checks=[]), calc, "internal"
    )
    if citations in {"terminal", "dependencies", "checks_only"}:
        assert len(verified["findings"]) == 1
        assert not verified["unresolved_checks"]
        assert revalidate_review(verified, observations, POLICY, "internal")["findings"]
    else:
        assert verified["rejected_claims"]


def finding(refs, category="amount", kind="numerical", scope="cross", checks=None):
    return {
        "scope": scope,
        "kind": kind,
        "category": category,
        "severity": "high",
        "title": category,
        "explanation": category,
        "observation_ids": refs,
        "calculation_ids": [],
        "check_ids": [],
        "policy_refs": [],
        "verified_checks": checks or [],
    }


def test_same_policy_record_merges_different_citations_but_separate_obligations_do_not():
    observations = [
        observation("state", "pending", "record-a", "state"),
        observation("name", "Taylor", "record-a", "person"),
        observation("other", "pending", "record-b", "state"),
    ]
    first = finding(["state"], kind="policy", scope="internal")
    first["policy_refs"] = ["explicit_rule"]
    second = {**first, "observation_ids": ["name", "state"]}
    separate_record = {**first, "observation_ids": ["other"]}
    separate_policy = {**second, "policy_refs": ["different_rule"]}
    merged = consolidate_findings([first, second, separate_record, separate_policy], observations)
    assert len(merged) == 3
    assert merged[0]["supporting_findings"]
    assert set(merged[0]["observation_ids"]) == {"state", "name"}


def test_row_grouping_preserves_different_rows_and_separate_identity_concerns():
    observations = [
        observation("qty", 5, "row-x", "item.quantity"),
        observation("amount", 50, "row-x", "item.amount"),
        observation("other", 100, "row-y", "item.amount"),
        observation("name", "Supplier", field="beneficiary_name"),
        observation("account", "0012", field="bank.account_number"),
    ]
    findings = [
        finding(["qty"], "quantity"),
        finding(["amount"], "line_value"),
        finding(["other"], "other_item"),
        finding(["name"], "name", "evidence"),
        finding(["account"], "account", "evidence"),
    ]
    saved = deepcopy(findings)
    result = consolidate_findings(findings, observations)
    assert len(result) == 4
    assert len(result[0]["supporting_findings"]) == 1
    assert set(result[0]["observation_ids"]) == {"qty", "amount"}
    assert findings == saved


def test_same_proof_merges_different_wording_but_distinct_checks_remain_linked():
    check = CheckDefinition(
        id="one", purpose="Variance", left=source("a"), right=source("b")
    ).model_dump()
    findings = [
        finding(["a", "b"], "wording_one", checks=[check]),
        finding(["a", "b"], "wording_two", checks=[{**check, "id": "two"}]),
        finding(["a"], "local", scope="internal", checks=[check]),
    ]
    result = consolidate_findings(findings, [observation("a", 1), observation("b", 2)])
    assert len(result) == 2
    assert len(result[0]["supporting_findings"]) == 1
    assert result[0]["related_issues"][0]["case_id"] == result[1]["case_id"]


def test_passing_subtraction_cannot_support_a_mismatch_and_omitted_failure_is_incomplete():
    calc = Calculator(
        [observation("a", 100), observation("b", 20), observation("expected", 80)], POLICY
    )
    calc.register_checks(
        [
            CheckDefinition(
                id="balance",
                purpose="Reconcile balance",
                left=expression("subtract", "a", "b"),
                right=source("expected"),
            )
        ]
    )
    proof = calc.calculate(
        {
            "operation": "subtract",
            "operands": ["a", "b"],
            "reported_observation_id": "expected",
            "check_id": "balance",
        }
    )
    claim = {
        "kind": "numerical",
        "severity": "high",
        "category": "balance",
        "title": "Mismatch",
        "explanation": "False mismatch",
        "observation_ids": ["a", "b", "expected"],
        "calculation_ids": [proof["id"]],
        "check_ids": ["balance"],
    }
    assert verify_result(
        AuditResult(findings=[claim], assessed_topics=[], unresolved_checks=[]), calc, "internal"
    )["rejected_claims"]
    calc.observations["expected"]["normalized_value"] = "90"
    calc.ledger.clear()
    calc.calculate(proof["request"])
    result = verify_result(
        AuditResult(findings=[], assessed_topics=[], unresolved_checks=[]), calc, "internal"
    )
    assert result["unresolved_checks"]


def test_formula_compiler_uses_sources_not_model_calculation_aliases():
    calc = Calculator(
        [
            observation("invoice", "100.15"),
            observation("paid", "30.05"),
            observation("request", "80.20"),
        ],
        POLICY,
    )
    results = execute_checks(
        [
            CheckDefinition(
                id="payment",
                purpose="Balance comparison",
                left=source("request"),
                right=expression("subtract", "invoice", "paid"),
                relation="lte",
            )
        ],
        calc,
    )
    assert [result["result"] for result in results] == ["70.10", "10.10"]
    assert results[-1]["request"]["check_id"] == "payment"
    assert validate_binding(results[-1], calc) is None
    with pytest.raises(ValueError, match="unknown/unreadable"):
        execute_checks(
            [
                CheckDefinition(
                    id="bad",
                    purpose="Invalid dependency",
                    left=source("request"),
                    right=source("calc_1"),
                )
            ],
            calc,
        )


@pytest.mark.parametrize("combined,accepted", [(False, True), (True, False)])
def test_cross_numerical_findings_keep_independent_document_scopes_separate(combined, accepted):
    rows = [observation(ref, value) for ref, value in [("a", 100), ("b", 120), ("c", 140)]]
    for row, doc in zip(rows, ["doc1", "doc2", "doc3"]):
        row["document_id"] = doc
    for ref, doc in [("link1", "doc1"), ("link2", "doc2"), ("link3", "doc3")]:
        row = observation(ref, "REF")
        row.update(
            document_id=doc,
            field_key="document_number" if doc == "doc2" else "reference",
            value_type="identifier",
            unit=None,
        )
        rows.append(row)
    calc = Calculator(rows, POLICY)
    execute_checks(
        [
            CheckDefinition(
                id="first", purpose="Compare first pair", left=source("a"), right=source("b")
            ),
            CheckDefinition(
                id="second", purpose="Compare second pair", left=source("b"), right=source("c")
            ),
        ],
        calc,
    )
    finding = dict(
        kind="numerical",
        severity="high",
        category="variance",
        title="Mismatch",
        explanation="Mismatch",
        observation_ids=["a", "b"],
        check_ids=["first", "second"] if combined else ["first"],
    )
    links = [
        dict(
            from_document=doc,
            to_document="doc2",
            status="supported",
            observation_ids=[ref, "link2"],
            explanation="Reference",
        )
        for doc, ref in [("doc1", "link1"), ("doc3", "link3")]
    ]
    verified = verify_result(
        AuditResult(findings=[finding], links=links, assessed_topics=[], unresolved_checks=[]),
        calc,
        "cross",
    )
    assert bool(verified["findings"]) == accepted
    if not accepted:
        assert "comparison scope" in verified["rejected_claims"][0]["reason"]
