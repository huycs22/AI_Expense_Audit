import json
from unittest.mock import AsyncMock

import pytest

from app.features.audits.qualitative import (
    restore_identity_references,
    review_identity_coverage,
    validate_identity_plan,
)


def observations():
    return [
        dict(
            id="source:A",
            document_id="A",
            field_key="document_number",
            value_type="identifier",
            raw_value="DOC-X",
            normalized_value="DOC-X",
            quote="Document DOC-X",
        ),
        dict(
            id="source:B",
            document_id="B",
            field_key="invoice_reference",
            value_type="identifier",
            raw_value="DOC-X",
            normalized_value="DOC-X",
            quote="Reference DOC-X",
        ),
        dict(
            id="source:C",
            document_id="A",
            field_key="account_holder",
            value_type="text",
            raw_value="Example Company",
            normalized_value="Example Company",
            quote="Account holder Example Company",
        ),
        dict(
            id="source:D",
            document_id="B",
            field_key="beneficiary",
            value_type="text",
            raw_value="Alex",
            normalized_value="Alex",
            quote="Beneficiary Alex",
        ),
    ]


def links():
    return [
        dict(
            from_document="A",
            to_document="B",
            status="supported",
            observation_ids=["source:A", "source:B"],
            explanation="Explicit reference",
        )
    ]


@pytest.mark.parametrize(
    "refs", [["source:A", "missing"], ["source:A", "source:C"], ["source:A", "source:A"]]
)
def test_coverage_plan_never_accepts_unknown_local_or_duplicate_sources(refs):
    with pytest.raises(ValueError):
        validate_identity_plan(
            dict(comparisons=[dict(purpose="Compare", observation_ids=refs)], unresolved_checks=[]),
            observations(),
            links(),
        )


@pytest.mark.asyncio
async def test_identity_coverage_restores_source_and_relationship_provenance():
    proposal = dict(
        category="identity",
        severity="medium",
        kind="evidence",
        title="Different beneficiary",
        explanation="Different source names",
        observation_ids=["s3", "s4"],
        check_ids=[],
        calculation_ids=[],
        policy_refs=[],
    )
    client = type("Client", (), {})()
    client.complete = AsyncMock(
        side_effect=[
            {
                "content": json.dumps(
                    dict(
                        comparisons=[
                            dict(purpose="Account-holder comparison", observation_ids=["s3", "s4"])
                        ],
                        unresolved_checks=[],
                    )
                )
            },
            {
                "content": json.dumps(
                    dict(
                        findings=[proposal],
                        assessed_topics=["identity"],
                        unresolved_checks=[],
                        links=[],
                    )
                )
            },
            {
                "content": json.dumps(
                    dict(
                        checks=[],
                        findings=[
                            dict(
                                id="0",
                                verdict="supported",
                                atomicity="atomic",
                                explanation_completeness="complete",
                                observation_ids=["s3", "s4"],
                                reason="Same payment identity dimension",
                            )
                        ],
                    )
                )
            },
        ]
    )
    result = await review_identity_coverage(
        client,
        "audit",
        observations(),
        [{"id": "A", "role": "invoice"}, {"id": "B", "role": "payment_request"}],
        {"links": links(), "findings": []},
    )
    assert not result["unresolved_checks"]
    assert result["findings"][0]["observation_ids"] == ["source:C", "source:D"]
    assert result["links"][0]["observation_ids"] == ["source:A", "source:B"]
    assert result["meaning_review"]["findings"][0]["observation_ids"] == ["source:C", "source:D"]
    assert client.complete.await_count == 3


def test_restore_citations_is_idempotent_and_preserves_quoted_text():
    payload = {"observation_ids": ["s3", "source:D"], "quote": "Account named s3"}
    restored = restore_identity_references(payload, observations())
    assert restored == {"observation_ids": ["source:C", "source:D"], "quote": "Account named s3"}
    assert restore_identity_references(restored, observations()) == restored
    assert payload["observation_ids"] == ["s3", "source:D"]
    with pytest.raises(ValueError, match="unknown source"):
        restore_identity_references({"observation_ids": ["missing"]}, observations())
