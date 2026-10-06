import pytest

from app.features.audits.calculator import Calculator
from app.features.audits.reviewer import POLICY
from app.features.audits.schemas import AuditResult, Finding, Link
from app.features.audits.verification import verify_result


@pytest.mark.parametrize(
    "refs,accepted",
    [
        (["name1", "name2"], True),
        (["number1", "number2"], True),
        (["name1", "name2", "number1", "number2"], False),
        (["number_text", "number2"], True),
        (["money1", "number2"], False),
    ],
)
def test_cross_evidence_is_one_compatible_scalar_pair(refs, accepted):
    rows = [
        ("link1", "doc1", "reference", "identifier", "REF-X"),
        ("link2", "doc2", "document_number", "identifier", "REF-X"),
        ("name1", "doc1", "entity.name", "text", "Alpha"),
        ("name2", "doc2", "entity.name", "text", "Beta"),
        ("number1", "doc1", "entity.identifier", "identifier", "0017"),
        ("number2", "doc2", "entity.identifier", "identifier", "0091"),
        ("number_text", "doc1", "entity.identifier", "text", "0017"),
        ("money1", "doc1", "amount", "money", "17"),
    ]
    observations = [
        {
            "id": ref,
            "document_id": doc,
            "field_key": field,
            "value_type": kind,
            "raw_value": value,
            "normalized_value": value,
            "quote": value,
            "unit": None,
        }
        for ref, doc, field, kind, value in rows
    ]
    result = AuditResult(
        findings=[
            Finding(
                category="identity",
                severity="high",
                kind="evidence",
                title="Different values",
                explanation="Source comparison",
                observation_ids=refs,
            )
        ],
        assessed_topics=[],
        unresolved_checks=[],
        links=[
            Link(
                from_document="doc1",
                to_document="doc2",
                status="supported",
                observation_ids=["link1", "link2"],
                explanation="Explicit reference",
            )
        ],
    )
    verified = verify_result(result, Calculator(observations, POLICY), "cross")
    assert bool(verified["findings"]) == accepted
    if not accepted:
        assert verified["rejected_claims"]
