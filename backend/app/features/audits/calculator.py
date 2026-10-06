from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.features.audits.proofs import CheckDefinition, check_signature
from app.features.extraction.normalization import inferred_unit


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["sum", "multiply", "subtract", "divide", "compare", "date_add_days"]
    operands: list[str] = Field(min_length=1, max_length=100)
    check_id: str | None = None
    reported_observation_id: str | None = None
    relation: Literal["equals", "lte", "gte"] = "equals"
    tolerance_policy_ref: Literal["amount_tolerance"] = "amount_tolerance"

    @model_validator(mode="after")
    def distinct_reported_result(self):
        if self.operation == "multiply" and len(self.operands) < 2:
            raise ValueError("Multiplication needs at least two operands")
        if self.operation != "compare" and self.reported_observation_id in self.operands:
            raise ValueError(
                "A derived result must be compared to a separate reported observation, not one of its operands; use compare for direct comparisons or null for an explanatory difference"
            )
        return self


class Calculator:
    def __init__(self, observations: list[dict], policy: dict):
        self.observations = {o["id"]: o for o in observations}
        self.policy = policy
        self.ledger: dict[str, dict] = {}
        self.checks: dict[str, CheckDefinition] = {}

    def register_checks(self, checks: list[CheckDefinition]):
        if len({check.id for check in checks}) != len(checks):
            raise ValueError("Check contract IDs must be unique")
        for check in checks:
            check_signature(check, self.observations)
        self.checks = {check.id: check for check in checks}

    def resolve(
        self, reference: str, allow_identity: bool = False
    ) -> tuple[str, str | None, list[str]]:
        if reference in self.observations:
            obs = self.observations[reference]
            value = obs.get("normalized_value")
            if value is None:
                raise ValueError("Operand is not readable/normalized")
            allowed = {"number", "money", "date"} | (
                {"identifier", "text"} if allow_identity else set()
            )
            if obs["value_type"] not in allowed:
                raise ValueError(
                    f"Operand {reference} ({obs.get('field_key')}) has type {obs['value_type']}; arithmetic requires number, money or date"
                )
            return value, inferred_unit(obs), [reference]
        if reference in self.ledger:
            item = self.ledger[reference]
            return item["result"], item["unit"], item["observation_ids"]
        raise ValueError("Unknown operand ID")

    def calculate(self, args: dict) -> dict:
        if len(self.ledger) >= 40:
            raise ValueError("Calculation limit exceeded")
        request = CalculationRequest.model_validate(args)
        resolved = [
            self.resolve(ref, allow_identity=request.operation == "compare")
            for ref in request.operands
        ]
        date_operands = [
            (ref in self.observations and self.observations[ref]["value_type"] == "date")
            or (ref in self.ledger and self.ledger[ref]["unit"] == "date")
            for ref in request.operands
        ]
        date_comparison = request.operation == "compare" and any(date_operands)
        if date_comparison and (len(date_operands) != 2 or not all(date_operands)):
            raise ValueError("Date comparison requires two calendar-date operands")
        if any(date_operands) and request.operation not in {"compare", "date_add_days"}:
            raise ValueError(
                "Calendar dates require date_add_days or date comparison, not numeric arithmetic"
            )
        units = {unit for _, unit, _ in resolved if unit}
        operation = request.operation
        if (
            operation in {"sum", "subtract", "compare", "divide"}
            and len(units) > 1
            and not date_comparison
        ):
            raise ValueError("Incompatible currency/units")
        sources = sorted({obs_id for _, _, obs_ids in resolved for obs_id in obs_ids})
        unit = next(iter(units), None) if len(units) <= 1 else None
        identity_comparison = operation == "compare" and any(
            ref in self.observations
            and self.observations[ref]["value_type"] in {"identifier", "text"}
            for ref in request.operands
        )
        if date_comparison:
            result = str(
                (date.fromisoformat(resolved[0][0]) - date.fromisoformat(resolved[1][0])).days
            )
            unit = "days"
        elif identity_comparison:
            if (
                len(resolved) != 2
                or request.relation != "equals"
                or not all(
                    ref in self.observations
                    and self.observations[ref]["value_type"] in {"identifier", "text"}
                    for ref in request.operands
                )
            ):
                raise ValueError(
                    "Identity comparison requires two text/identifier observations and relation=equals"
                )
            result = "0" if resolved[0][0] == resolved[1][0] else "1"
            unit = "identity"
        elif operation == "date_add_days":
            if len(resolved) != 2 or not date_operands[0] or date_operands[1]:
                raise ValueError("date_add_days needs date and day-count observations")
            if any(self.observations[ref]["value_type"] != "number" for ref in resolved[1][2]):
                raise ValueError(
                    "Date offsets require numeric duration sources, never money or identifiers"
                )
            days = Decimal(resolved[1][0])
            if days != days.to_integral_value() or abs(days) > 36500:
                raise ValueError("Invalid day count")
            result = (date.fromisoformat(resolved[0][0]) + timedelta(days=int(days))).isoformat()
            unit = "date"
        else:
            try:
                values = [Decimal(v) for v, _, _ in resolved]
            except InvalidOperation:
                raise ValueError("Non-numeric operand") from None
            if not all(v.is_finite() and abs(v) < Decimal("1e30") for v in values):
                raise ValueError("Invalid numeric operand")
            if operation in {"subtract", "divide", "compare"} and len(values) != 2:
                raise ValueError("Operation needs exactly two operands")
            if operation == "sum":
                number = sum(values, Decimal(0))
            elif operation == "multiply":
                number = Decimal(1)
                for value in values:
                    number *= value
                monetary = {
                    self.observations[ref]["unit"]
                    for _, _, refs in resolved
                    for ref in refs
                    if self.observations[ref]["value_type"] == "money"
                    and self.observations[ref].get("unit")
                }
                if len(monetary) > 1:
                    raise ValueError("Cannot multiply incompatible currencies")
                unit = next(iter(monetary), unit)
                if "%" in units:
                    number /= 100
            elif operation in {"subtract", "compare"}:
                number = values[0] - values[1]
            else:
                if values[1] == 0:
                    raise ValueError("Division by zero")
                number = values[0] / values[1]
                unit = None
            result = format(number, "f")
        comparison = None
        tolerance = (
            Decimal(0)
            if date_comparison
            else Decimal(self.policy[request.tolerance_policy_ref]["value"])
        )
        # Compare already evaluates operand A against B. A redundant reported ID
        # must never compare their difference to the original amount.
        if operation == "compare":
            difference = Decimal(result)
            passed = (
                (result == "0")
                if identity_comparison
                else (
                    abs(difference) <= tolerance
                    if request.relation == "equals"
                    else (
                        difference <= tolerance
                        if request.relation == "lte"
                        else difference >= -tolerance
                    )
                )
            )
            comparison = {
                "difference": None if identity_comparison else result,
                "status": "pass" if passed else "fail",
            }
        elif request.reported_observation_id:
            reported, reported_unit, refs = self.resolve(request.reported_observation_id)
            if unit and reported_unit and unit != reported_unit:
                raise ValueError("Reported value has incompatible unit")
            sources = sorted(set(sources + refs))
            if unit == "date":
                difference = Decimal(
                    (date.fromisoformat(result) - date.fromisoformat(reported)).days
                )
            else:
                difference = Decimal(result) - Decimal(reported)
            passed = (
                abs(difference) <= tolerance
                if request.relation == "equals"
                else (
                    difference <= tolerance
                    if request.relation == "lte"
                    else difference >= -tolerance
                )
            )
            comparison = {
                "reported": reported,
                "difference": format(difference, "f"),
                "status": "pass" if passed else "fail",
            }
        calc_id = f"calc_{len(self.ledger) + 1}"
        item = {
            "id": calc_id,
            "request": request.model_dump(),
            "result": result,
            "unit": unit,
            "observation_ids": sources,
            "comparison": comparison,
        }
        self.ledger[calc_id] = item
        return item
