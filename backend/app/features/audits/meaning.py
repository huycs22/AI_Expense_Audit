"""Independent semantic adjudication after deterministic proof verification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class MeaningDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    verdict: Literal["supported", "unsupported", "unresolved"]
    observation_ids: list[str]
    reason: str


class CheckMeaningDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    verdict: Literal["valid", "invalid", "unresolved"]
    observation_ids: list[str]
    reason: str


class MeaningReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: list[CheckMeaningDecision]
    findings: list[MeaningDecision]


class CrossFindingDecision(MeaningDecision):
    atomicity: Literal["atomic", "bundled"]
    explanation_completeness: Literal["complete", "incomplete", "unresolved"]


class CrossMeaningReview(MeaningReview):
    findings: list[CrossFindingDecision]


def validate_meaning(
    payload: dict,
    check_ids: set[str],
    findings: list[dict],
    observations: list[dict],
    *,
    cross: bool = False,
):
    review = (CrossMeaningReview if cross else MeaningReview).model_validate(payload)
    registry = {o["id"] for o in observations}
    expected_findings = {str(i) for i in range(len(findings))}
    for decisions, expected in [(review.checks, check_ids), (review.findings, expected_findings)]:
        ids = [decision.id for decision in decisions]
        if len(ids) != len(set(ids)) or set(ids) != expected:
            raise ValueError("Semantic review must adjudicate every check/finding exactly once")
        for decision in decisions:
            if not decision.reason.strip() or not set(decision.observation_ids).issubset(registry):
                raise ValueError("Semantic decision requires a reason and registered evidence")
            if decision.verdict in {"valid", "supported"} and not decision.observation_ids:
                raise ValueError("Supported semantic decision requires source evidence")
    return review


def apply_meaning(result: dict, review: MeaningReview) -> dict:
    """Retain supported claims; disclose every excluded/uncertain obligation."""
    checks = {decision.id: decision for decision in review.checks}
    findings = {decision.id: decision for decision in review.findings}
    unresolved = list(result["unresolved_checks"])
    accepted, rejected = [], list(result.get("rejected_claims", []))
    for decision in review.checks:
        if decision.verdict != "valid":
            unresolved.append(f"Ý nghĩa phép kiểm tra {decision.id}: {decision.reason}")
    for index, finding in enumerate(result["findings"]):
        decision = findings[str(index)]
        reasons = [
            checks[ref].reason
            for ref in finding.get("check_ids", [])
            if checks[ref].verdict != "valid"
        ]
        if decision.verdict != "supported":
            reasons.append(decision.reason)
        if getattr(decision, "atomicity", "atomic") != "atomic":
            reasons.append("Nhận định gộp nhiều nghĩa vụ độc lập; cần tách từng vấn đề")
        if getattr(decision, "explanation_completeness", "complete") != "complete":
            reasons.append("Giải thích chưa đầy đủ bằng chứng hoặc các thành phần chênh lệch")
        if reasons:
            reason = "; ".join(dict.fromkeys(reasons))
            rejected.append(
                {"title": finding["title"], "reason": reason, "validation_stage": "meaning_review"}
            )
            unresolved.append(f"Nhận định chưa được xác nhận: {finding['title']}: {reason}")
        else:
            accepted.append({**finding, "semantic_review": decision.model_dump()})
    return {
        **result,
        "findings": accepted,
        "rejected_claims": rejected,
        "unresolved_checks": list(dict.fromkeys(unresolved)),
        "meaning_review": review.model_dump(),
    }
