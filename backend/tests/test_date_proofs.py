import pytest

from app.features.audits.calculator import Calculator
from app.features.audits.proofs import CheckDefinition, execute_checks, validate_binding
from app.features.audits.reviewer import POLICY


def obs(ref, value, kind, unit=None):
    return {
        "id": ref,
        "normalized_value": value,
        "value_type": kind,
        "unit": unit,
        "raw_value": value,
        "quote": value,
        "document_id": "d",
        "field_key": "source",
    }


@pytest.mark.parametrize(
    "reported,status,difference", [("2028-03-02", "pass", "0"), ("2028-03-03", "fail", "-1")]
)
def test_date_formula_compares_calendar_dates_and_preserves_dependencies(
    reported, status, difference
):
    calc = Calculator(
        [
            obs("start", "2028-02-27", "date"),
            obs("duration", "4", "number", "days"),
            obs("reported", reported, "date"),
        ],
        POLICY,
    )
    check = CheckDefinition(
        id="calendar",
        purpose="Explicit date and duration",
        left={
            "operation": "date_add_days",
            "operands": [{"observation_id": "start"}, {"observation_id": "duration"}],
        },
        right={"observation_id": "reported"},
    )
    results = execute_checks([check], calc)
    assert results[-1]["comparison"] == {"status": status, "difference": difference}
    assert results[-1]["unit"] == "days"
    assert validate_binding(results[-1], calc) is None


@pytest.mark.parametrize(
    "relation,expected", [("equals", "fail"), ("lte", "pass"), ("gte", "fail")]
)
def test_date_ordering_does_not_borrow_money_tolerance(relation, expected):
    policy = {**POLICY, "amount_tolerance": {"value": "100"}}
    calc = Calculator([obs("a", "2027-01-01", "date"), obs("b", "2027-01-02", "date")], policy)
    result = calc.calculate({"operation": "compare", "operands": ["a", "b"], "relation": relation})
    assert result["comparison"]["status"] == expected


def test_dates_cannot_be_used_as_numbers_or_compared_against_money():
    calc = Calculator(
        [obs("date", "2027-01-01", "date"), obs("money", "20", "money", "USD")], POLICY
    )
    with pytest.raises(ValueError, match="Calendar dates"):
        calc.calculate({"operation": "sum", "operands": ["date", "money"]})
    with pytest.raises(ValueError, match="two calendar-date"):
        calc.calculate({"operation": "compare", "operands": ["date", "money"]})
    with pytest.raises(ValueError, match="duration"):
        calc.calculate({"operation": "date_add_days", "operands": ["date", "money"]})
