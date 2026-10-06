import json

from app.features.audits.proofs import CheckDefinition
from app.features.audits.reviewer import cross_scope_feedback


def test_scope_repair_exposes_original_and_peer_binding_without_asserting_equivalence():
    observations = {
        "request": dict(
            id="request",
            document_id="A",
            field_key="requested_amount",
            normalized_value="470",
            value_type="money",
            unit="EUR",
        ),
        "copy": dict(
            id="copy",
            document_id="A",
            field_key="invoice_value",
            normalized_value="450",
            value_type="money",
            unit="EUR",
        ),
        "actual": dict(
            id="actual",
            document_id="B",
            field_key="total",
            normalized_value="450",
            value_type="money",
            unit="EUR",
        ),
        "irrelevant": dict(
            id="irrelevant",
            document_id="C",
            field_key="quantity",
            normalized_value="450",
            value_type="number",
            unit="boxes",
        ),
    }
    check = CheckDefinition(
        id="balance",
        purpose="Compare request with balance",
        left={"observation_id": "request"},
        right={"observation_id": "copy"},
    )
    feedback = json.loads(
        cross_scope_feedback(
            [check],
            observations,
            [{"id": "A", "role": "payment_request"}, {"id": "B", "role": "invoice"}],
        )
    )[0]
    assert {o["id"] for o in feedback["sources"]} == {"request", "copy"}
    assert feedback["equal_value_peer_candidates"][0]["id"] == "actual"
    assert feedback["equal_value_peer_candidates"][0]["document_role"] == "invoice"
    assert len(feedback["equal_value_peer_candidates"]) == 1
    assert feedback["check"]["right"]["observation_id"] == "copy"
