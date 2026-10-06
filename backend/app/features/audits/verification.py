import re
from decimal import Decimal

from app.features.audits.calculator import Calculator
from app.features.audits.proofs import CheckDefinition, validate_binding
from app.features.audits.schemas import AuditResult, Finding


def failed_calculation(calculation: dict, calculator: Calculator) -> bool:
    comparison = calculation.get("comparison")
    if comparison is not None:
        return comparison["status"] == "fail"
    return calculation["request"]["operation"] == "subtract" and abs(
        Decimal(calculation["result"])
    ) > Decimal(calculator.policy[calculation["request"]["tolerance_policy_ref"]]["value"])


def proof_dependencies(roots: list[dict], calculator: Calculator) -> set[str]:
    """Only terminal comparisons prove checks; their intermediate DAG nodes support them."""
    visited, pending = set(), [root["id"] for root in roots]
    while pending:
        ref = pending.pop()
        if ref in visited:
            continue
        visited.add(ref)
        pending.extend(
            operand
            for operand in calculator.ledger[ref]["request"]["operands"]
            if operand in calculator.ledger
        )
    return visited


def verify_result(result: AuditResult, calculator: Calculator, scope: str) -> dict:
    observations = calculator.observations
    links = verify_links(result, observations)
    related = {}
    for link in links:
        if link["status"] == "supported":
            related.setdefault(link["from_document"], set()).add(link["to_document"])
            related.setdefault(link["to_document"], set()).add(link["from_document"])

    def connected(documents):
        visited, pending = set(), [next(iter(documents))]
        while pending:
            document = pending.pop()
            if document not in visited:
                visited.add(document)
                pending.extend(related.get(document, set()) - visited)
        return documents.issubset(visited)

    accepted, rejected, passing = [], [], []
    for finding in result.findings:
        if finding.kind == "numerical" and not finding.calculation_ids:
            # Model chooses source-bound checks; Python attaches the executed proof.
            finding = finding.model_copy(
                update={
                    "calculation_ids": [
                        item["id"]
                        for item in calculator.ledger.values()
                        if item["request"].get("check_id") in finding.check_ids
                    ]
                }
            )
        item = finding.model_dump()
        # Calculations already carry immutable source IDs. Attach their full provenance
        # instead of asking the model to copy those same IDs without omission.
        if finding.kind == "numerical" and all(
            ref in calculator.ledger for ref in finding.calculation_ids
        ):
            calculation_sources = [
                ref
                for calc_id in finding.calculation_ids
                for ref in calculator.ledger[calc_id]["observation_ids"]
            ]
            finding = finding.model_copy(
                update={
                    "observation_ids": list(
                        dict.fromkeys(finding.observation_ids + calculation_sources)
                    )
                }
            )
            item = finding.model_dump()
        reason = None
        if (
            scope == "cross"
            and finding.kind == "evidence"
            and not finding.policy_refs
            and len(finding.observation_ids) >= 2
            and all(
                ref in observations and observations[ref].get("normalized_value") is not None
                for ref in finding.observation_ids
            )
            and len({observations[ref]["normalized_value"] for ref in finding.observation_ids}) == 1
        ):
            # Equal observed values prove this comparison passes; preserve it as an assessed check.
            passing.append(item)
            continue
        if any(
            ref not in observations
            or not observations[ref].get("quote")
            or observations[ref].get("raw_value") is None
            for ref in finding.observation_ids
        ):
            reason = "Finding cites unknown/unreadable evidence"
        elif (
            scope == "cross"
            and len({observations[ref]["document_id"] for ref in finding.observation_ids}) < 2
        ):
            reason = "Cross finding must cite at least two documents"
        elif (
            scope == "cross"
            and finding.kind == "evidence"
            and (
                len(finding.observation_ids) != 2
                or not compatible_scalar_types(
                    {observations[ref]["value_type"] for ref in finding.observation_ids}
                )
            )
        ):
            reason = (
                "Each evidence finding compares exactly one scalar observation from each of two "
                "documents, with compatible value types. Split multiple attributes into separate "
                "finding objects; do not combine name and account comparisons or add context IDs. "
                "Source quotes and registered observations already provide context."
            )
        elif scope == "cross" and not connected(
            {observations[ref]["document_id"] for ref in finding.observation_ids}
        ):
            reason = "Cross finding lacks a supported document-reference relationship"
        elif any(ref not in calculator.policy for ref in finding.policy_refs):
            reason = "Unknown policy reference"
        elif finding.kind == "policy" and not finding.policy_refs:
            reason = "Policy finding needs explicit policy"
        elif any(ref not in calculator.ledger for ref in finding.calculation_ids):
            reason = "Unknown calculation ID"
        elif mislabeled_item(finding, observations):
            reason = "Finding names an item code that does not belong to its cited item rows"
        elif finding.kind == "numerical":
            calcs = [calculator.ledger[c] for c in finding.calculation_ids]
            terminals = [c for c in calcs if c["request"].get("check_id") is not None]
            binding_errors = [validate_binding(c, calculator) for c in terminals]
            bound_checks = {c["request"]["check_id"] for c in terminals}
            failed_checks = {
                c["request"]["check_id"] for c in terminals if failed_calculation(c, calculator)
            }
            sources = {ref for c in calcs for ref in c["observation_ids"]}
            if not finding.check_ids or set(finding.check_ids) != bound_checks:
                reason = "Numerical claim must cite exactly the check contracts proved by its calculations"
            elif any(binding_errors):
                reason = next(error for error in binding_errors if error)
            elif not {c["id"] for c in calcs}.issubset(proof_dependencies(terminals, calculator)):
                reason = "Cited intermediate calculation is not a dependency of the declared check"
            elif not set(finding.check_ids).issubset(failed_checks) or not sources.issubset(
                set(finding.observation_ids)
            ):
                reason = "Numerical finding lacks a cited, reproducible mismatch calculation"
            elif (
                scope == "cross"
                and len(
                    {
                        frozenset(observations[ref]["document_id"] for ref in c["observation_ids"])
                        for c in terminals
                    }
                )
                > 1
            ):
                reason = (
                    "A numerical finding must describe one document comparison scope. "
                    "Split check contracts involving different document sets into separate findings; "
                    "related component checks within the same scope may explain an aggregate."
                )
        if reason:
            rejected.append({"finding": item, "reason": reason})
        else:
            accepted.append(
                {
                    **item,
                    "scope": scope,
                    "verification": "source_formula_checked"
                    if finding.kind == "numerical"
                    else "references_checked",
                    "verified_checks": [
                        calculator.checks[ref].model_dump()
                        for ref in finding.check_ids
                        if ref in calculator.checks
                    ],
                }
            )
    unresolved = list(result.unresolved_checks)
    covered = {ref for finding in accepted for ref in finding.get("check_ids", [])}
    failed = {
        calculation["request"].get("check_id")
        for calculation in calculator.ledger.values()
        if failed_calculation(calculation, calculator)
        and validate_binding(calculation, calculator) is None
    }
    unresolved.extend(
        "Phép kiểm tra chưa có kết luận được xác minh: " + calculator.checks[ref].purpose
        for ref in sorted(failed - covered)
    )
    unresolved.extend(f"Không xác minh được kết luận: {r['reason']}" for r in rejected)
    unresolved.extend(
        "Chưa xác minh được quan hệ chứng từ: " + link["explanation"]
        for link in links
        if link["status"] != "supported"
    )
    return {
        "findings": accepted,
        "rejected_claims": rejected,
        "assessed_topics": list(
            dict.fromkeys(result.assessed_topics + [f["category"] for f in passing])
        ),
        "excluded_passing_checks": passing,
        "not_applicable_topics": result.not_applicable_topics,
        "unresolved_checks": unresolved,
        "uncovered_check_ids": sorted(failed - covered),
        "links": links,
        "calculations": list(calculator.ledger.values()),
        "check_definitions": [check.model_dump() for check in calculator.checks.values()],
    }


def compatible_scalar_types(types: set[str]) -> bool:
    """Text and identifiers preserve strings; never coerce numeric/date values into identities.

    This checks representation compatibility, not semantic equivalence of field roles.
    The independent meaning review still verifies that the compared attributes match.
    """
    return len(types) == 1 or types.issubset({"text", "identifier"})


def revalidate_review(payload: dict, observations: list[dict], policy: dict, scope: str) -> dict:
    """Recompute saved proofs with current verification, retaining immutable stage outputs."""
    calculator = Calculator(observations, policy)
    calculator.register_checks(
        [
            CheckDefinition.model_validate(check)
            for check in payload.get(
                "check_definitions", payload.get("calculation_plan", {}).get("checks", [])
            )
        ]
    )
    for saved in payload.get("calculations", []):
        result = calculator.calculate(saved["request"])
        if result["id"] != saved["id"]:
            raise ValueError("Saved calculation order does not match its evidence ledger")
    finding_keys = set(Finding.model_fields)
    structured = AuditResult.model_validate(
        {
            **{
                key: payload[key]
                for key in AuditResult.model_fields
                if key != "findings" and key in payload
            },
            "findings": [
                {k: v for k, v in f.items() if k in finding_keys} for f in payload["findings"]
            ],
        }
    )
    verified = verify_result(structured, calculator, scope)
    verified["excluded_passing_checks"] = (
        payload.get("excluded_passing_checks", []) + verified["excluded_passing_checks"]
    )
    verified["rejected_claims"] = payload.get("rejected_claims", []) + verified["rejected_claims"]
    verified["unresolved_checks"] = list(dict.fromkeys(verified["unresolved_checks"]))
    # Recomputing arithmetic must not discard the separate semantic adjudication.
    semantic_decisions = {
        (f["title"], tuple(f.get("check_ids", [])), tuple(f["observation_ids"])): f[
            "semantic_review"
        ]
        for f in payload["findings"]
        if "semantic_review" in f
    }
    for finding in verified["findings"]:
        key = (
            finding["title"],
            tuple(finding.get("check_ids", [])),
            tuple(finding["observation_ids"]),
        )
        if key in semantic_decisions:
            finding["semantic_review"] = semantic_decisions[key]
    return {**payload, **verified}


def mislabeled_item(finding, observations: dict) -> bool:
    """Check source-row identity without a catalog of vendor/sample item codes."""
    cited_rows = {
        (observations[ref]["document_id"], observations[ref].get("group_key"))
        for ref in finding.observation_ids
        if observations[ref].get("field_key", "").startswith("item.")
        and observations[ref].get("group_key") is not None
    }
    if not cited_rows:
        return False
    codes = [
        o
        for o in observations.values()
        if o.get("field_key") == "item.code"
        and o.get("normalized_value")
        and len(o["normalized_value"]) >= 2
    ]
    related = {
        o["normalized_value"] for o in codes if (o["document_id"], o.get("group_key")) in cited_rows
    }
    text = finding.title + " " + finding.explanation
    mentioned = {
        o["normalized_value"]
        for o in codes
        if re.search(r"(?<!\w)" + re.escape(o["normalized_value"]) + r"(?!\w)", text)
    }
    return bool(mentioned - related)


def verify_links(result: AuditResult, observations: dict) -> list[dict]:
    links = []
    for link in result.links:
        if any(ref not in observations for ref in link.observation_ids):
            raise ValueError("Link cites unknown observations")
        if link.status != "unresolved":
            involved = {observations[ref]["document_id"] for ref in link.observation_ids}
            if (
                not {link.from_document, link.to_document}.issubset(involved)
                or link.from_document == link.to_document
            ):
                raise ValueError(
                    f"Link {link.from_document} -> {link.to_document} lacks evidence from both documents. "
                    f"Cited sources: {[(ref, observations[ref]['document_id'], observations[ref].get('field_key')) for ref in link.observation_ids]}. "
                    "Choose the document-number observation from one document and its matching reference from the other."
                )
            # Supported explicit references must agree; linguistic party matching alone is insufficient.
            identifiers = [
                observations[ref]["normalized_value"]
                for ref in link.observation_ids
                if observations[ref]["value_type"] == "identifier"
                and is_document_reference(observations[ref])
            ]
            if link.status == "supported" and (
                len(link.observation_ids) != 2
                or len(identifiers) != 2
                or any(value is None for value in identifiers)
                or len(set(identifiers)) != 1
            ):
                raise ValueError(
                    "Supported link needs equal explicit document/reference identifiers"
                )
        links.append(link.model_dump())
    return links


def is_document_reference(observation: dict) -> bool:
    key = observation.get("field_key", "").casefold()
    if any(
        term in key
        for term in ("account", "bank", "party", "supplier", "buyer", "item.", "approval")
    ):
        return False
    return bool(
        re.search(
            r"(^|[._])(document|invoice|po|purchase_order|payment_request|request|reference|ref|number)([._]|$)",
            key,
        )
    )
