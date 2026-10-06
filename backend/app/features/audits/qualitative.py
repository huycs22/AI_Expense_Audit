"""Legacy standalone identity runner for historical evaluations.

Production now plans and adjudicates these pairs within the main cross review.
"""

import json

from app.core.config import get_settings
from app.features.audits.calculator import Calculator
from app.features.audits.comparisons import (  # noqa: F401
    IdentityComparison,
    IdentityPlan,
    validate_identity_plan,
)
from app.features.audits.meaning import CrossMeaningReview, apply_meaning, validate_meaning
from app.features.audits.reviewer import (
    POLICY,
    explicit_output_schema,
    phase_prompt,
    validated_json,
)
from app.features.audits.schemas import AuditResult
from app.features.audits.verification import verify_result


def restore_identity_references(payload, observations):
    """Restore transport IDs in every structured citation, including review metadata."""
    eligible = identity_observations(observations)
    reverse = {f"s{i + 1}": o["id"] for i, o in enumerate(eligible)}
    registered = {o["id"] for o in observations}

    def restore(value):
        if isinstance(value, list):
            return [restore(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key == "observation_ids":
                refs = [ref if ref in registered else reverse.get(ref) for ref in item]
                if any(ref is None for ref in refs):
                    raise ValueError("Identity result cites an unknown source")
                result[key] = refs
            else:
                result[key] = restore(item)
        return result

    return restore(payload)


def identity_observations(observations):
    return [
        o
        for o in observations
        if o["value_type"] in {"text", "identifier"}
        and o.get("raw_value")
        and o.get("quote")
        and not o["field_key"].startswith("item.")
    ]




async def review_identity_coverage(client, audit_id, observations, documents, cross):
    eligible = identity_observations(observations)
    aliases = {o["id"]: f"s{i + 1}" for i, o in enumerate(eligible)}
    links = [
        {**link, "observation_ids": [aliases[ref] for ref in link["observation_ids"]]}
        for link in cross["links"]
    ]
    doc_aliases = {doc["id"]: f"d{i + 1}" for i, doc in enumerate(documents)}
    roles = {doc["id"]: doc["role"] for doc in documents}
    quotes = {
        quote: f"q{i + 1}" for i, quote in enumerate(dict.fromkeys(o["quote"] for o in eligible))
    }
    evidence = [
        {
            "id": aliases[o["id"]],
            "document_id": doc_aliases[o["document_id"]],
            "document_role": roles[o["document_id"]],
            "quote_id": quotes[o["quote"]],
            **{
                k: o.get(k)
                for k in ("field_key", "raw_value", "group_key", "role")
                if o.get(k) is not None
            },
        }
        for o in eligible
    ]
    aliased = [{**o, "id": aliases[o["id"]]} for o in eligible]
    model = get_settings().cloudflare_cross_model
    covered = [
        [aliases[ref] for ref in f["observation_ids"]]
        for f in cross["findings"]
        if f["kind"] == "evidence" and all(ref in aliases for ref in f["observation_ids"])
    ]
    context = {
        "documents": [{**doc, "id": doc_aliases[doc["id"]]} for doc in documents],
        "verified_links": [
            {
                **link,
                "from_document": doc_aliases[link["from_document"]],
                "to_document": doc_aliases[link["to_document"]],
            }
            for link in links
        ],
        "source_observations": evidence,
        "source_quotes": {alias: text for text, alias in quotes.items()},
        "already_assessed_pairs": covered,
    }
    prompt = phase_prompt("identity_coverage")
    plan = await validated_json(
        client,
        audit_id,
        "audit_identity_plan",
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        lambda p: validate_identity_plan(p, aliased, cross["links"]),
        1800,
        explicit_output_schema(IdentityPlan.model_json_schema()),
        model,
    )
    plan.comparisons = [
        c for c in plan.comparisons if set(c.observation_ids) not in [set(pair) for pair in covered]
    ]
    planned_pairs = {frozenset(c.observation_ids) for c in plan.comparisons}
    calculator = Calculator(aliased, POLICY)

    def focused_context(refs):
        selected = [o for o in evidence if o["id"] in refs]
        quote_ids = {o["quote_id"] for o in selected}
        return {
            **context,
            "source_observations": selected,
            "source_quotes": {
                ref: value for ref, value in context["source_quotes"].items() if ref in quote_ids
            },
        }

    final_schema = AuditResult.model_json_schema()
    final_schema["properties"].pop("links")
    final_schema["$defs"]["Finding"]["properties"]["observation_ids"].update(minItems=2, maxItems=2)
    final_schema["$defs"]["Finding"]["properties"]["kind"] = {"type": "string", "const": "evidence"}

    def validate_findings(payload):
        result = AuditResult.model_validate({**payload, "links": links})
        for finding in result.findings:
            if (
                finding.kind != "evidence"
                or frozenset(finding.observation_ids) not in planned_pairs
            ):
                raise ValueError(
                    "Select exactly ONE registered pair per evidence finding; extra corroborating documents must not expand that pair. "
                    + "Invalid refs: "
                    + json.dumps(finding.observation_ids)
                    + "; allowed pairs: "
                    + json.dumps([c.observation_ids for c in plan.comparisons])
                )
        checked = verify_result(result, calculator, "cross")
        if checked["rejected_claims"]:
            raise ValueError(json.dumps(checked["rejected_claims"], ensure_ascii=False))
        checked["unresolved_checks"] += plan.unresolved_checks
        return checked

    checked = await validated_json(
        client,
        audit_id,
        "audit_identity_findings",
        [
            {
                "role": "system",
                "content": prompt
                + "\nInterpret EVERY planned pair. Return evidence findings for material discrepancies only. Passing pairs are assessed topics, not anomalies. Numeric/policy findings are outside this stage. Do not infer fraud or payment prohibitions.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        **focused_context(
                            {ref for c in plan.comparisons for ref in c.observation_ids}
                        ),
                        "comparison_plan": plan.model_dump(),
                        "policy": POLICY,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        validate_findings,
        1800,
        explicit_output_schema(final_schema),
        model,
    )
    decisions = await validated_json(
        client,
        audit_id,
        "audit_identity_meaning",
        [
            {
                "role": "system",
                "content": phase_prompt("meaning") + "\n" + phase_prompt("meaning_cross"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        **focused_context(
                            {ref for f in checked["findings"] for ref in f["observation_ids"]}
                        ),
                        "check_definitions": [],
                        "proposed_findings": [
                            {"id": str(i), **f} for i, f in enumerate(checked["findings"])
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        lambda p: validate_meaning(p, set(), checked["findings"], aliased, cross=True),
        min(2400, max(500, len(checked["findings"]) * 250 + 100)),
        explicit_output_schema(CrossMeaningReview.model_json_schema()),
        model,
    )
    result = apply_meaning(checked, decisions)
    result["comparison_plan"] = [
        {"purpose": c.purpose, "observation_ids": c.observation_ids}
        for c in plan.comparisons
    ]
    return restore_identity_references(result, observations)
