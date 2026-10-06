"""Source-bound proof contracts, independent of vendor fields and sample values.

The model declares a question as a formula over observations. The verifier expands
executed calculation dependencies and requires that exact formula, not just the
same units, source set, or numerical result. This is a proof of the declared check;
it does not certify the model's business interpretation of arbitrary prose.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Operation = Literal["sum", "multiply", "subtract", "divide", "date_add_days"]


class SourceExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str


class OperationExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Operation
    operands: list["SourceExpression | OperationExpression"] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def source_or_operation(self):
        if self.operation in {"subtract", "divide", "date_add_days"} and len(self.operands) != 2:
            raise ValueError("This expression operation needs exactly two operands")
        elif self.operation == "multiply" and len(self.operands) < 2:
            raise ValueError("Multiplication needs at least two operands")
        return self


Expression = SourceExpression | OperationExpression


class CheckDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=500)
    left: Expression
    right: Expression
    relation: Literal["equals", "lte", "gte"] = "equals"


class CheckPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: list[CheckDefinition] = Field(max_length=24)
    unresolved_checks: list[str] = Field(default_factory=list)
    not_applicable_topics: list[str] = Field(default_factory=list)

    @field_validator("unresolved_checks", "not_applicable_topics")
    @classmethod
    def explanatory_scope_notes(cls, notes):
        if any(not note.strip() or not re.search(r"\s", note.strip()) for note in notes):
            raise ValueError(
                "Scope notes must explain the evidence/policy reason in readable language, "
                "not a bare check ID. Optional hypotheses with no established obligation "
                "belong in not_applicable_topics; genuinely blocked checks stay unresolved."
            )
        return notes


def execute_checks(checks: list[CheckDefinition], calculator) -> list[dict]:
    """Compile source formulas into a ledger; the model cannot select calc_N inputs."""
    calculator.register_checks(checks)
    cache = {}

    def compile_expression(expression):
        if isinstance(expression, SourceExpression):
            return expression.observation_id
        signature = expression_signature(expression, calculator.observations)
        if signature not in cache:
            result = calculator.calculate(
                {
                    "operation": expression.operation,
                    "operands": [compile_expression(child) for child in expression.operands],
                }
            )
            cache[signature] = result["id"]
        return cache[signature]

    for check in checks:
        try:
            result = calculator.calculate(
                {
                    "operation": "compare",
                    "operands": [compile_expression(check.left), compile_expression(check.right)],
                    "relation": check.relation,
                    "check_id": check.id,
                }
            )
        except (ValueError, ArithmeticError) as exc:
            refs = expression_sources(check.left) | expression_sources(check.right)
            facts = [
                {
                    key: calculator.observations[ref].get(key)
                    for key in ("id", "document_id", "field_key", "unit", "value_type")
                }
                for ref in sorted(refs)
            ]
            raise ValueError(f"Check {check.id}: {exc}; source fields: {facts}") from None
        error = validate_binding(result, calculator)
        if error:
            raise ValueError(error)
    return list(calculator.ledger.values())


def expression_sources(expression: Expression) -> set[str]:
    if isinstance(expression, SourceExpression):
        return {expression.observation_id}
    return {ref for child in expression.operands for ref in expression_sources(child)}


def expression_signature(expression: Expression, observations: dict, depth=0) -> tuple:
    if depth > 8:
        raise ValueError("Proof expression nesting exceeds the limit")
    if isinstance(expression, SourceExpression):
        ref = expression.observation_id
        if ref not in observations or observations[ref].get("normalized_value") is None:
            raise ValueError("Proof expression cites unknown/unreadable observations")
        return ("source", ref)
    return operation_signature(
        expression.operation,
        [expression_signature(child, observations, depth + 1) for child in expression.operands],
    )


def operation_signature(operation, operands) -> tuple:
    # Order may change only for commutative operations. No numerical substitution:
    # two unrelated equal-valued observations remain distinct evidence.
    if operation in {"sum", "multiply"}:
        operands = sorted(operands, key=repr)
    return (operation, tuple(operands))


def reference_signature(reference: str, calculator, visiting=None) -> tuple:
    if reference in calculator.observations:
        return ("source", reference)
    visiting = set() if visiting is None else visiting
    if reference in visiting or reference not in calculator.ledger:
        raise ValueError("Unknown/cyclic calculation dependency")
    request = calculator.ledger[reference]["request"]
    if request["operation"] == "compare":
        raise ValueError("A comparison's difference cannot be reused as a source amount")
    return operation_signature(
        request["operation"],
        [
            reference_signature(ref, calculator, visiting | {reference})
            for ref in request["operands"]
        ],
    )


def calculation_signature(calculation: dict, calculator) -> tuple:
    request = calculation["request"]
    operands = [reference_signature(ref, calculator) for ref in request["operands"]]
    if request["operation"] == "compare":
        left, right = operands
    elif request.get("reported_observation_id"):
        left = operation_signature(request["operation"], operands)
        right = reference_signature(request["reported_observation_id"], calculator)
    elif request["operation"] == "subtract":
        left, right = operands
        if request["relation"] != "equals":
            raise ValueError("Explanatory differences require relation=equals")
    else:
        raise ValueError("An intermediate result does not prove a discrepancy")
    return comparison_signature(left, right, request["relation"])


def comparison_signature(left, right, relation) -> tuple:
    if relation == "equals":
        left, right = sorted([left, right], key=repr)
    return (relation, left, right)


def check_signature(check: CheckDefinition, observations: dict) -> tuple:
    return comparison_signature(
        expression_signature(check.left, observations),
        expression_signature(check.right, observations),
        check.relation,
    )


def validate_binding(calculation: dict, calculator) -> str | None:
    check_id = calculation["request"].get("check_id")
    if check_id not in calculator.checks:
        return "Discrepancy calculation needs a registered check contract"
    try:
        if calculation_signature(calculation, calculator) != check_signature(
            calculator.checks[check_id], calculator.observations
        ):
            return "Calculation does not prove the declared source formula (operand, dependency or relation mismatch)"
    except ValueError as exc:
        return str(exc)
    return None
