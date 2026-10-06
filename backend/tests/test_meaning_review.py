import pytest

from app.features.audits.meaning import apply_meaning, validate_meaning


def decision(identifier, verdict="supported", reason="Source establishes obligation"):
    return {"id": identifier, "verdict": verdict, "observation_ids": ["source"], "reason": reason}


@pytest.mark.parametrize("verdict", ["invalid", "unresolved"])
def test_arithmetic_validity_does_not_override_unsupported_business_meaning(verdict):
    # No sample dates, names, amounts, field names or business-specific predicates.
    finding = {
        "title": "Unproven comparison",
        "check_ids": ["obligation"],
        "verification": "source_formula_checked",
    }
    result = {"findings": [finding], "unresolved_checks": []}
    review = validate_meaning(
        {
            "checks": [decision("obligation", verdict, "Different events")],
            "findings": [decision("0")],
        },
        {"obligation"},
        [finding],
        [{"id": "source"}],
    )
    verified = apply_meaning(result, review)
    assert not verified["findings"]
    assert verified["unresolved_checks"]
    assert verified["rejected_claims"][0]["validation_stage"] == "meaning_review"


def test_supported_arithmetic_cannot_override_an_incorrect_explanation():
    finding = {"title": "Inverted direction", "check_ids": ["check"]}
    review = validate_meaning(
        {
            "checks": [decision("check", "valid")],
            "findings": [decision("0", "unsupported", "Direction reversed")],
        },
        {"check"},
        [finding],
        [{"id": "source"}],
    )
    result = apply_meaning({"findings": [finding], "unresolved_checks": []}, review)
    assert not result["findings"]
    assert "Direction reversed" in result["unresolved_checks"][0]


def test_every_check_is_adjudicated_even_when_no_anomalies_are_proposed():
    with pytest.raises(ValueError, match="every check"):
        validate_meaning({"checks": [], "findings": []}, {"unchecked"}, [], [{"id": "source"}])
    review = validate_meaning(
        {"checks": [decision("check", "unresolved")], "findings": []},
        {"check"},
        [],
        [{"id": "source"}],
    )
    assert apply_meaning({"findings": [], "unresolved_checks": []}, review)["unresolved_checks"]


def test_supported_claim_preserves_semantic_provenance():
    finding = {"title": "Discrepancy", "check_ids": ["check"]}
    review = validate_meaning(
        {"checks": [decision("check", "valid")], "findings": [decision("0")]},
        {"check"},
        [finding],
        [{"id": "source"}],
    )
    result = apply_meaning({"findings": [finding], "unresolved_checks": []}, review)
    assert result["findings"][0]["semantic_review"]["verdict"] == "supported"


@pytest.mark.parametrize(
    "atomicity,completeness",
    [("bundled", "complete"), ("atomic", "incomplete"), ("atomic", "unresolved")],
)
def test_true_cross_claims_still_require_atomic_complete_explanations(atomicity, completeness):
    finding = {"title": "True but inadequate claim", "check_ids": ["check"]}
    review = validate_meaning(
        {
            "checks": [decision("check", "valid")],
            "findings": [
                {**decision("0"), "atomicity": atomicity, "explanation_completeness": completeness}
            ],
        },
        {"check"},
        [finding],
        [{"id": "source"}],
        cross=True,
    )
    result = apply_meaning({"findings": [finding], "unresolved_checks": []}, review)
    assert not result["findings"]
    assert result["unresolved_checks"]
